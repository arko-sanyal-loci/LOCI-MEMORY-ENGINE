#!/usr/bin/env python3
"""
Loci Memory Engine - Model Context Protocol (MCP) Server Daemon
JSON-RPC 2.0 stdio transport exposing Unified Core governance,
thermodynamic budgeting, and SQLite WAL storage operations.
"""

import sys
import json
import logging
from typing import Dict, Any

from loci_engine.unified_core import (
    NonOffsettingGoodwillLedger,
    StickPrincipleValenceGate,
    DynamicTokenCoupledSnippetEngine
)
from loci_engine.storage import StorageEngine

storage = StorageEngine()

def handle_rpc_request(req: Dict[str, Any], ledger: NonOffsettingGoodwillLedger) -> Dict[str, Any]:
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"status": "healthy", "engine": "loci-unified-core"}}

    elif method == "score_action":
        k = params.get("knowledge_k", "operational_default")
        p = params.get("application_point", "routine_administrative_task")
        intent = float(params.get("intent", 0.0))
        consent = float(params.get("consent", 1.0))
        vuln = float(params.get("target_vulnerability", 0.0))
        cid = float(params.get("c_id", 0.85))

        res = StickPrincipleValenceGate.score_vexec(
            knowledge_k=k,
            application_point=p,
            intent=intent,
            consent=consent,
            target_vulnerability=vuln,
            c_id=cid
        )
        return {"jsonrpc": "2.0", "id": req_id, "result": res}

    elif method == "record_goodwill":
        aid = params.get("action_id", "act_default")
        actor = params.get("actor", "operator")
        delta = float(params.get("delta", 0.0))
        is_formative = bool(params.get("is_formative", False))

        rec = ledger.record_goodwill_action(action_id=aid, actor=actor, delta=delta, is_formative=is_formative)
        return {"jsonrpc": "2.0", "id": req_id, "result": rec}

    elif method == "resolve_budget":
        score = float(params.get("confidence_score", 0.85))
        base = int(params.get("baseline_bytes", 60))
        budget = DynamicTokenCoupledSnippetEngine.calculate_snippet_budget(confidence_score=score, baseline_bytes=base)
        return {"jsonrpc": "2.0", "id": req_id, "result": budget}

    elif method == "memory.ingest_fact":
        fact_id = params.get("id")
        ns = params.get("namespace", "general")
        text = params.get("text", "")
        heat = float(params.get("heat", 0.85))
        supersedes = params.get("supersedes_id")

        res_id = storage.insert_fact(
            item_id=fact_id,
            namespace=ns,
            canonical_text=text,
            heat=heat,
            supersedes_id=supersedes
        )
        return {"jsonrpc": "2.0", "id": req_id, "result": {"stored_id": res_id, "status": "active"}}

    elif method == "memory.search_lexical":
        query = params.get("query", "")
        limit = int(params.get("limit", 5))
        records = storage.lexical_search(query=query, limit=limit)
        return {"jsonrpc": "2.0", "id": req_id, "result": {"matches": records}}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method '{method}' not found"}
    }

def main():
    ledger = NonOffsettingGoodwillLedger()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_rpc_request(req, ledger)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error or internal exception: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
