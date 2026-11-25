#!/usr/bin/env python3
"""
Workers/learning_loop.py - Core Background Worker Loop for Billo & LOCI

Resolutions incorporated:
- Bug #9: Import `query_hash` at module level to eliminate per-request overhead.
- Bug #10: SQLite WAL mode and NORMAL synchronous pragmas on every connection.
"""

import os
import sys
import time
import json
import re
import ast
import sqlite3
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple

# Add parent directory to sys.path to resolve internal imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# FIX BUG #9: Module-level import to eliminate hot-path import overhead
# ---------------------------------------------------------------------------
try:
    from loci.efficiency import query_hash as _qhash
except ImportError:
    import hashlib
    def _qhash(query_str: str) -> str:
        return hashlib.sha256(query_str.encode("utf-8")).hexdigest()[:16]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [LearningLoop] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("billo.learning_loop")

# ---------------------------------------------------------------------------
# Configuration & Endpoints
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.getenv("BILLO_DB_PATH", os.path.join(BASE_DIR, "data", "context2.db"))

OLLAMA_GPU_URL = os.getenv("OLLAMA_GPU_URL", "http://localhost:11434")
OLLAMA_VPS_TUNNEL = os.getenv("OLLAMA_VPS_TUNNEL", "http://localhost:11435")
OLLAMA_VPS_DIRECT = os.getenv("OLLAMA_VPS_DIRECT", "http://127.0.0.1:11434")

MODEL_GPU = os.getenv("MODEL_GPU", "qwen2.5-coder:14b")
MODEL_VPS = os.getenv("MODEL_VPS", "qwen2.5:3b")

TIMEOUT_VPS_COMPRESS = float(os.getenv("TIMEOUT_VPS_COMPRESS", "60.0"))  # CPU inference budget
POLL_INTERVAL_SEC = 2.0


# ---------------------------------------------------------------------------
# FIX BUG #10: Database Connection Factory with WAL & PRAGMAs
# ---------------------------------------------------------------------------
def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Connects to SQLite with WAL mode and NORMAL synchronous enabled."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Ensures base schema requirements exist."""
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT,
                error TEXT,
                retries INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS compress_log (
                compress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                tokens_before INTEGER,
                tokens_after INTEGER,
                tokens_saved INTEGER,
                credits_saved_usd REAL DEFAULT 0.0,
                discrepancy_pct REAL DEFAULT 0.0,
                method TEXT,
                vps_ok INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_efficiency_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT DEFAULT 'default',
                session_id TEXT DEFAULT 'default',
                query_hash TEXT,
                raw_entities_scanned INTEGER,
                hits_returned INTEGER,
                loci_tokens REAL,
                baseline_tokens REAL,
                cer_ratio REAL,
                grade TEXT DEFAULT 'GOOD',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


# ---------------------------------------------------------------------------
# Core Task Operations & Ollama Routing
# ---------------------------------------------------------------------------
async def route_ollama_call(
    prompt: str,
    prefer_vps: bool = True,
    system_prompt: Optional[str] = None,
    timeout: float = TIMEOUT_VPS_COMPRESS
) -> str:
    """
    Routes an LLM inference call. If prefer_vps=True, attempts VPS Ollama first,
    falling back to local GPU Ollama or local heuristic fallback.
    """
    import urllib.request
    import urllib.error

    targets = []
    if prefer_vps:
        targets.extend([
            (OLLAMA_VPS_TUNNEL, MODEL_VPS, timeout),
            (OLLAMA_VPS_DIRECT, MODEL_VPS, timeout),
            (OLLAMA_GPU_URL, MODEL_GPU, 30.0)
        ])
    else:
        targets.extend([
            (OLLAMA_GPU_URL, MODEL_GPU, 30.0),
            (OLLAMA_VPS_TUNNEL, MODEL_VPS, timeout),
            (OLLAMA_VPS_DIRECT, MODEL_VPS, timeout)
        ])

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload_bytes = json.dumps({
        "model": targets[0][1],
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2}
    }).encode("utf-8")

    loop = asyncio.get_event_loop()

    for base_url, model_name, to_sec in targets:
        url = f"{base_url}/api/chat"
        req_payload = json.dumps({
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2}
        }).encode("utf-8")

        def _do_post(u=url, p=req_payload, t=to_sec):
            req = urllib.request.Request(
                u,
                data=p,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=t) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            res_data = await loop.run_in_executor(None, _do_post)
            content = res_data.get("message", {}).get("content", "").strip()
            if content:
                return content
        except Exception as ex:
            logger.warning("Ollama routing candidate failed %s (%s): %s", base_url, model_name, ex)
            continue

    raise RuntimeError("All Ollama routing endpoints exhausted or timed out.")


async def execute_optimize(task_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates execution tier: local, vps, forge, or claude.
    Recommends /v1/symbols first when code inspection can reduce prompt tokens.
    """
    task_desc = task_payload.get("task", "")
    code_present = bool(re.search(r"(\bdef\b|\bclass\b|import\s+|\.py|\.ts|\.js)", task_desc))

    prompt = (
        f"Analyze this task and assign the best execution tier ('local', 'vps', 'forge', 'claude'):\n"
        f"Task: {task_desc}\n\n"
        f"Return JSON strictly with format:\n"
        f'{{"tier": "...", "recommend_symbols": true/false, "rationale": "..."}}'
    )
    try:
        raw_res = await route_ollama_call(
            prompt=prompt,
            prefer_vps=True,
            system_prompt="You are Billo's Task Optimization & Routing Engine.",
            timeout=15.0
        )
        match = re.search(r"\{.*\}", raw_res, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as ex:
        logger.warning("VPS optimizer LLM unavailable, applying heuristic: %s", ex)

    # Keyword heuristic fallback
    tier = "vps"
    recommend_symbols = False
    lower_desc = task_desc.lower()
    if any(k in lower_desc for k in ["forge", "generate codebase", "heavy refactor", "coder"]):
        tier = "forge"
    elif any(k in lower_desc for k in ["comfyui", "image", "flux", "sdxl", "refine"]):
        tier = "local"
    elif any(k in lower_desc for k in ["architecture", "research", "paper", "deep reasoning"]):
        tier = "claude"

    if code_present:
        recommend_symbols = True

    return {
        "tier": tier,
        "recommend_symbols": recommend_symbols,
        "rationale": "Generated via deterministic fallback heuristics (VPS offline)."
    }


async def execute_compress(task_payload: Dict[str, Any], conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Compresses text context using VPS Ollama 3b.
    Falls back to entity-preserving regex heuristic if Ollama is unreachable.
    """
    raw_text = task_payload.get("text", "")
    session_id = task_payload.get("session_id", "default")
    original_tokens = max(1, len(raw_text) // 4)

    prompt = (
        f"Condense the following log/session output while preserving all critical entities, "
        f"variables, endpoints, and error traces:\n\n{raw_text[:8000]}"
    )

    method = "vps_ollama_3b"
    vps_ok = 1
    try:
        compressed_text = await route_ollama_call(
            prompt=prompt,
            prefer_vps=True,
            system_prompt="Compress the given context strictly preserving technical precision.",
            timeout=TIMEOUT_VPS_COMPRESS
        )
    except Exception as ex:
        logger.warning("Compression fallback triggered: %s", ex)
        method = "heuristic_entity_filter"
        vps_ok = 0
        lines = raw_text.splitlines()
        kept = [
            l for l in lines
            if any(k in l for k in ["ERROR", "WARN", "def ", "class ", "http", "LOCI", "traceback", "status="])
        ]
        compressed_text = "\n".join(kept) if kept else raw_text[:1000]

    compressed_tokens = max(1, len(compressed_text) // 4)
    tokens_saved = max(0, original_tokens - compressed_tokens)
    ratio = round(compressed_tokens / original_tokens, 3)
    credits_saved_usd = round(tokens_saved * 0.000003, 4)

    with conn:
        conn.execute(
            """
            INSERT INTO compress_log (
                session_id, tokens_before, tokens_after, tokens_saved,
                credits_saved_usd, method, vps_ok
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, original_tokens, compressed_tokens, tokens_saved, credits_saved_usd, method, vps_ok)
        )

    return {
        "session_id": session_id,
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "tokens_saved": tokens_saved,
        "compression_ratio": ratio,
        "method": method,
        "compressed_text": compressed_text
    }


def execute_symbol_lookup(task_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts top-level symbols (functions, classes, variables) via AST/Regex."""
    source_code = task_payload.get("code", "")
    symbols = []

    try:
        tree = ast.parse(source_code)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append({"name": node.name, "type": "function", "lineno": node.lineno})
            elif isinstance(node, ast.ClassDef):
                symbols.append({"name": node.name, "type": "class", "lineno": node.lineno})
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.append({"name": target.id, "type": "variable", "lineno": node.lineno})
    except Exception:
        func_matches = re.findall(r"def\s+([a-zA-Z0-9_]+)\s*\(", source_code)
        class_matches = re.findall(r"class\s+([a-zA-Z0-9_]+)\s*[:\(]", source_code)
        for f in func_matches:
            symbols.append({"name": f, "type": "function", "lineno": 0})
        for c in class_matches:
            symbols.append({"name": c, "type": "class", "lineno": 0})

    return {"count": len(symbols), "symbols": symbols}


# ---------------------------------------------------------------------------
# Main Worker Processing Loop
# ---------------------------------------------------------------------------
async def process_task(task_row: sqlite3.Row, conn: sqlite3.Connection) -> None:
    task_id = task_row["id"]
    task_type = task_row["task_type"]
    payload = json.loads(task_row["payload"])
    logger.info("Processing task #%d (type: %s)", task_id, task_type)

    try:
        if task_type == "/ops/optimize":
            result = await execute_optimize(payload)
        elif task_type == "/v1/compress":
            result = await execute_compress(payload, conn)
        elif task_type == "/v1/symbols":
            result = execute_symbol_lookup(payload)
        else:
            raise ValueError(f"Unsupported task type in queue: {task_type}")

        with conn:
            conn.execute(
                "UPDATE task_queue SET status = 'completed', result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(result), task_id)
            )
        logger.info("Task #%d completed successfully", task_id)

    except Exception as ex:
        logger.error("Task #%d failed: %s", task_id, ex, exc_info=True)
        retries = task_row["retries"] + 1
        new_status = "failed" if retries >= 3 else "pending"
        with conn:
            conn.execute(
                "UPDATE task_queue SET status = ?, error = ?, retries = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_status, str(ex), retries, task_id)
            )


async def main_worker_loop():
    logger.info("Starting Billo Learning Loop Worker against %s", DB_PATH)
    conn = get_db_connection()
    init_db(conn)

    try:
        while True:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM task_queue WHERE status = 'pending' ORDER BY id ASC LIMIT 5"
            )
            tasks = cursor.fetchall()

            if not tasks:
                await asyncio.sleep(POLL_INTERVAL_SEC)
                continue

            for task in tasks:
                await process_task(task, conn)

    except asyncio.CancelledError:
        logger.info("Worker loop received cancellation signal.")
    finally:
        conn.close()
        logger.info("Worker database connection closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main_worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
