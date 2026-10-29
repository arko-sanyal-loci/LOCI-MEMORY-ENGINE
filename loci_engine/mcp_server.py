#!/usr/bin/env python3
"""
Loci Memory Engine - Model Context Protocol (MCP) Daemon Entrypoint
Exposes unified core primitives over standard I/O (JSON-RPC) and local sockets.
"""

import sys
import json
import logging
from typing import Dict, Any

from loci_engine.unified_core import (
    NonOffsettingGoodwillLedger,
    StickPrincipleValenceGate,
    DynamicTokenCoupledSnippetEngine,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [loci-mcp] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("loci-mcp")

def handle_rpc_request(req: Dict[str, Any], ledger: NonOffsettingGoodwillLedger) -> Dict[str, Any]:
    method = req.get("method")
    params = req.get("params", {})
    req_id = req.get("id")

    try:
        if method == "ping":
            result = {"status": "healthy", "service": "loci-memory-engine"}

        elif method == "score_action":
            # Valence & Ethics verification gate
            result = StickPrincipleValenceGate.score_vexec(
                knowledge_k=params.get("knowledge_k", "generic_context"),
                application_point=params.get("application_point", "routine_administrative_task"),
                intent=float(params.get("intent", 0.0)),
                consent=float(params.get("consent", 1.0)),
                target_vulnerability=float(params.get("target_vulnerability", 0.0)),
                c_id=params.get("c_id")
            )

        elif method == "record_goodwill":
            ledger.record_goodwill(
                delta=float(params.get("delta", 0.0)),
                current_day=float(params.get("current_day", 0.0)),
                weight=float(params.get("weight", 1.0)),
                is_formative=bool(params.get("is_formative", False))
            )
            result = {"v_good": ledger.compute_active_v_good(float(params.get("current_day", 0.0)))}

        elif method == "resolve_budget":
            result = DynamicTokenCoupledSnippetEngine.resolve_snippet_budget(
                top_score=float(params.get("top_score", 1.0)),
                runner_up_score=float(params.get("runner_up_score", 0.0)),
                tokens_already_consumed=int(params.get("tokens_already_consumed", 0))
            )

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"}
            }

        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    except Exception as e:
        logger.error(f"Error handling method {method}: {e}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32000, "message": str(e)}
        }

def main():
    logger.info("Initializing Loci MCP Server Daemon...")
    ledger = NonOffsettingGoodwillLedger()
    logger.info("Substrate core verified. Awaiting JSON-RPC commands.")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_rpc_request(req, ledger)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
