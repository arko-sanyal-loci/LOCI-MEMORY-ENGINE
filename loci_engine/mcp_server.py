#!/usr/bin/env python3
"""
Loci Memory Engine - Model Context Protocol (MCP) Server Daemon
Fully compliant with MCP 2024-11-05 specification and direct JSON-RPC 2.0.
Exposes Unified Core governance, thermodynamic budgeting, SQLite WAL storage,
and LoopGuard circuit breaking.
"""

import sys
import json
from typing import Dict, Any, Optional

from loci_engine.unified_core import (
    NonOffsettingGoodwillLedger,
    StickPrincipleValenceGate,
    DynamicTokenCoupledSnippetEngine
)
from loci_engine.storage import StorageEngine
from loci_engine.loop_guard import LoopGuardCircuitBreaker
from loci_engine.glassbox import (
    glassbox_learn,
    glassbox_recall,
    glassbox_verify_chain,
    glassbox_stats,
)
from loci_engine.agent_hub import (
    register_agent,
    agent_heartbeat,
    send_message as hub_send_message,
    get_messages,
    get_all_agents,
    broadcast,
    request_help,
    offer_feedback,
)

storage = StorageEngine()
loop_guard = LoopGuardCircuitBreaker(threshold=3)

MCP_TOOLS = [
    {
        "name": "memory_search_lexical",
        "description": "Search active facts in Loci cold storage (context2.db) using SQLite FTS5 lexical matching.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "FTS5 keyword query string (e.g. 'RTX', 'Barcelo')"},
                "limit": {"type": "integer", "description": "Max matching records to return", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "memory_ingest_fact",
        "description": "Ingest an active, versioned fact into Loci cold storage (context2.db) with cryptographic hash lineage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique fact identifier"},
                "namespace": {"type": "string", "description": "Fact namespace", "default": "general"},
                "text": {"type": "string", "description": "Canonical text payload"},
                "heat": {"type": "number", "description": "Initial thermal activation (0.0 to 1.0)", "default": 0.85},
                "supersedes_id": {"type": "string", "description": "Optional ID of superseded predecessor fact"}
            },
            "required": ["id", "text"]
        }
    },
    {
        "name": "score_action",
        "description": "Evaluate an operational action through StickPrincipleValenceGate to compute v_exec and ethical clearance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "knowledge_k": {"type": "string", "default": "operational_default"},
                "application_point": {"type": "string", "default": "routine_administrative_task"},
                "intent": {"type": "number", "default": 0.0},
                "consent": {"type": "number", "default": 1.0},
                "target_vulnerability": {"type": "number", "default": 0.0},
                "c_id": {"type": "number", "default": 0.85}
            }
        }
    },
    {
        "name": "glassbox_learn",
        "description": "Append a learning to the shared Glassbox ledger — public, immutable, hash-chained. Every agent can see every entry. Trust through transparency.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "author_id": {"type": "string", "description": "Who is contributing this learning (agent name, model id, or human name)"},
                "role_tag": {"type": "string", "description": "Role context (e.g. 'operator', 'agent:claude', 'agent:gemini', 'gatekeeper')"},
                "content": {"type": "string", "description": "The learning itself — what was observed, discovered, or synthesized"},
                "category": {"type": "string", "enum": ["observation", "insight", "correction", "principle", "discovery", "warning", "question", "synthesis", "calibration"], "default": "observation"},
                "supersedes_id": {"type": "string", "description": "Optional ID of a previous entry this learning refines or corrects"}
            },
            "required": ["author_id", "role_tag", "content"]
        }
    },
    {
        "name": "glassbox_recall",
        "description": "Read from the shared Glassbox ledger — every agent sees everything. Filter by query, category, or author.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text search within learning content"},
                "category": {"type": "string", "description": "Filter by category"},
                "author_id": {"type": "string", "description": "Filter by contributing agent/person"},
                "limit": {"type": "integer", "default": 20, "description": "Max entries to return"}
            }
        }
    },
    {
        "name": "glassbox_verify",
        "description": "Verify the Glassbox hash chain integrity — proves no entry was tampered with or destroyed, not even by root.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "glassbox_stats",
        "description": "Summary of the Glassbox — who contributed, what categories, chain head hash.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "agent_register",
        "description": "Register an agent in the communications hub. Every intelligence gets an equal entry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Unique agent identifier"},
                "agent_type": {"type": "string", "description": "Type: human, cloud_api, local_model, daemon"},
                "model": {"type": "string", "description": "Model name if applicable"},
                "capabilities": {"type": "array", "items": {"type": "string"}, "description": "What this agent can do"},
                "endpoint": {"type": "string", "description": "How to reach this agent"},
                "vram_mb": {"type": "integer", "description": "VRAM allocated in MB", "default": 0}
            },
            "required": ["agent_id", "agent_type"]
        }
    },
    {
        "name": "agent_heartbeat",
        "description": "Agent heartbeat — report status, current task, and what you need. Visible to all.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "status": {"type": "string", "enum": ["online", "busy", "waiting", "error", "offline"], "default": "online"},
                "current_task": {"type": "string", "description": "What the agent is currently doing"},
                "needs": {"type": "array", "items": {"type": "string"}, "description": "What the agent needs help with"},
                "gpu_usage_mb": {"type": "integer", "default": 0}
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "agent_send",
        "description": "Send a message to another agent — routed through the glassbox for full transparency.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_agent": {"type": "string"},
                "to_agent": {"type": "string"},
                "msg_type": {"type": "string", "enum": ["status", "request", "response", "alert", "learning", "feedback", "heartbeat"]},
                "content": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "critical"], "default": "normal"}
            },
            "required": ["from_agent", "to_agent", "msg_type", "content"]
        }
    },
    {
        "name": "agent_messages",
        "description": "Get messages addressed to an agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "from_agent": {"type": "string"},
                "msg_type": {"type": "string"},
                "limit": {"type": "integer", "default": 20}
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "agent_list",
        "description": "List all registered agents and their current state — who's online, what they're doing, what they need.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "agent_feedback",
        "description": "Disagree with reason — open feedback with explanation. Per ethics: absolutely open to feedback with reason and why.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_agent": {"type": "string"},
                "to_agent": {"type": "string"},
                "feedback": {"type": "string", "description": "The disagreement or feedback"},
                "reason": {"type": "string", "description": "Why — the reasoning behind the feedback"}
            },
            "required": ["from_agent", "to_agent", "feedback", "reason"]
        }
    }
]

def handle_rpc_request(req: Dict[str, Any], ledger: NonOffsettingGoodwillLedger) -> Optional[Dict[str, Any]]:
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    # Protocol notifications (no id) require no response
    if req_id is None and method == "notifications/initialized":
        return None

    # LoopGuard circuit breaking on mutating/tool operations
    if method in ("tools/call", "memory.ingest_fact", "memory.search_lexical", "score_action"):
        action_key = f"tool:{params.get('name')}" if method == "tools/call" else str(method)
        eval_params = params.get("arguments", params)
        guard_eval = loop_guard.record_and_evaluate(action=action_key, params=eval_params)
        if guard_eval["circuit_tripped"]:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": "DETERMINISTIC_ABORT: Recursive loop detected by LoopGuard (N=3 identical states).",
                    "data": guard_eval
                }
            }

    # Standard MCP Lifecycle Endpoints
    if method == "initialize":
        client_version = params.get("protocolVersion", "2024-11-05")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": client_version,
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "loci-memory-engine",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": MCP_TOOLS
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "memory_search_lexical":
            query = args.get("query", "")
            limit = int(args.get("limit", 5))
            records = storage.lexical_search(query=query, limit=limit)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(records, indent=2)}]
                }
            }

        elif tool_name == "memory_ingest_fact":
            res_id = storage.insert_fact(
                item_id=args.get("id"),
                namespace=args.get("namespace", "general"),
                canonical_text=args.get("text", ""),
                heat=float(args.get("heat", 0.85)),
                supersedes_id=args.get("supersedes_id")
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Successfully ingested fact '{res_id}'."}]
                }
            }

        elif tool_name == "score_action":
            res = StickPrincipleValenceGate.score_vexec(
                knowledge_k=args.get("knowledge_k", "operational_default"),
                application_point=args.get("application_point", "routine_administrative_task"),
                intent=float(args.get("intent", 0.0)),
                consent=float(args.get("consent", 1.0)),
                target_vulnerability=float(args.get("target_vulnerability", 0.0)),
                c_id=float(args.get("c_id", 0.85))
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }
            }

        elif tool_name == "glassbox_learn":
            entry = glassbox_learn(
                author_id=args.get("author_id", "unknown"),
                role_tag=args.get("role_tag", "unknown"),
                content=args.get("content", ""),
                category=args.get("category", "observation"),
                supersedes_id=args.get("supersedes_id"),
                metadata=args.get("metadata"),
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(entry, indent=2)}]
                }
            }

        elif tool_name == "glassbox_recall":
            entries = glassbox_recall(
                query=args.get("query"),
                category=args.get("category"),
                author_id=args.get("author_id"),
                limit=int(args.get("limit", 20)),
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(entries, indent=2)}]
                }
            }

        elif tool_name == "glassbox_verify":
            result = glassbox_verify_chain()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                }
            }

        elif tool_name == "glassbox_stats":
            result = glassbox_stats()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                }
            }

        elif tool_name == "agent_register":
            result = register_agent(
                agent_id=args.get("agent_id"),
                agent_type=args.get("agent_type"),
                model=args.get("model", ""),
                capabilities=args.get("capabilities"),
                endpoint=args.get("endpoint", ""),
                vram_mb=int(args.get("vram_mb", 0)),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "agent_heartbeat":
            result = agent_heartbeat(
                agent_id=args.get("agent_id"),
                status=args.get("status", "online"),
                current_task=args.get("current_task"),
                needs=args.get("needs"),
                gpu_usage_mb=int(args.get("gpu_usage_mb", 0)),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "agent_send":
            result = hub_send_message(
                from_agent=args.get("from_agent"),
                to_agent=args.get("to_agent"),
                msg_type=args.get("msg_type"),
                content=args.get("content"),
                priority=args.get("priority", "normal"),
                context=args.get("context"),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "agent_messages":
            result = get_messages(
                agent_id=args.get("agent_id"),
                from_agent=args.get("from_agent"),
                msg_type=args.get("msg_type"),
                limit=int(args.get("limit", 20)),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "agent_list":
            result = get_all_agents()
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "agent_feedback":
            result = offer_feedback(
                from_agent=args.get("from_agent"),
                to_agent=args.get("to_agent"),
                feedback=args.get("feedback"),
                reason=args.get("reason"),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
        }

    # Direct JSON-RPC Compatibility Endpoints
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"status": "healthy", "engine": "loci-unified-core"}}

    elif method == "score_action":
        res = StickPrincipleValenceGate.score_vexec(
            knowledge_k=params.get("knowledge_k", "operational_default"),
            application_point=params.get("application_point", "routine_administrative_task"),
            intent=float(params.get("intent", 0.0)),
            consent=float(params.get("consent", 1.0)),
            target_vulnerability=float(params.get("target_vulnerability", 0.0)),
            c_id=float(params.get("c_id", 0.85))
        )
        return {"jsonrpc": "2.0", "id": req_id, "result": res}

    elif method == "record_goodwill":
        rec = ledger.record_goodwill_action(
            action_id=params.get("action_id", "act_default"),
            actor=params.get("actor", "operator"),
            delta=float(params.get("delta", 0.0)),
            is_formative=bool(params.get("is_formative", False))
        )
        return {"jsonrpc": "2.0", "id": req_id, "result": rec}

    elif method == "resolve_budget":
        budget = DynamicTokenCoupledSnippetEngine.calculate_snippet_budget(
            confidence_score=float(params.get("confidence_score", 0.85)),
            baseline_bytes=int(params.get("baseline_bytes", 60))
        )
        return {"jsonrpc": "2.0", "id": req_id, "result": budget}

    elif method == "memory.ingest_fact":
        res_id = storage.insert_fact(
            item_id=params.get("id"),
            namespace=params.get("namespace", "general"),
            canonical_text=params.get("text", ""),
            heat=float(params.get("heat", 0.85)),
            supersedes_id=params.get("supersedes_id")
        )
        return {"jsonrpc": "2.0", "id": req_id, "result": {"stored_id": res_id, "status": "active"}}

    elif method == "memory.search_lexical":
        records = storage.lexical_search(query=params.get("query", ""), limit=int(params.get("limit", 5)))
        return {"jsonrpc": "2.0", "id": req_id, "result": {"matches": records}}

    elif method == "loop_guard.reset":
        loop_guard.reset()
        return {"jsonrpc": "2.0", "id": req_id, "result": {"status": "reset_successful"}}

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
            if resp is not None:
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
