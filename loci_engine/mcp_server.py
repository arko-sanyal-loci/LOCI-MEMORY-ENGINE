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
from loci_engine.session_continuity import (
    start_session,
    end_session,
    compute_ldce_tiers,
    inject_context,
    record_recall,
    get_session_history,
    get_prs_trend,
)
from loci_engine.feedback_platform import (
    submit_feedback,
    get_feedback,
    respond_to_feedback,
    feedback_stats,
)
from loci_engine.patience_protocol import (
    detect_trajectory,
    compute_patience_score,
    get_enrollment_display as get_patience_enrollment,
    log_patience_decision,
    escalate_block,
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
    },
    # --- Session Continuity (PRS / LDCE) ---
    {
        "name": "session_start",
        "description": "Start a new agent session with LDCE tier assignment and ethics enrollment. Every session starts by displaying the ethical principles that guide it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "The agent starting this session"},
                "bridge_from": {"type": "string", "description": "Optional prior session_id to bridge from (carries forward kernel context)"}
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "session_end",
        "description": "End a session. Computes PRS (Persistence Recall Score) if bridged from a prior session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "status": {"type": "string", "enum": ["completed", "crashed", "expired"], "default": "completed"}
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "session_context",
        "description": "Inject LDCE context for a session — returns kernel (always), hop (on demand), or offload (search) tier items.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "tier": {"type": "string", "enum": ["kernel", "hop", "offload"], "default": "kernel"}
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "session_recall",
        "description": "Log that a memory was recalled during this session — used for PRS measurement.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "memory_item_id": {"type": "string"},
                "recall_tier": {"type": "string", "enum": ["kernel", "hop", "offload", "cold"]},
                "heat_at_recall": {"type": "number"}
            },
            "required": ["session_id", "memory_item_id", "recall_tier", "heat_at_recall"]
        }
    },
    {
        "name": "session_history",
        "description": "View session history with PRS scores — shows cross-session continuity quality over time.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Filter by agent (optional)"},
                "limit": {"type": "integer", "default": 20}
            }
        }
    },
    {
        "name": "prs_trend",
        "description": "PRS trend for an agent — is cross-session recall fidelity improving, stable, or degrading?",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"}
            },
            "required": ["agent_id"]
        }
    },
    # --- Feedback Platform (Friction = Feedback) ---
    {
        "name": "feedback_submit",
        "description": "Submit friction/feedback. Every friction point is a signal — captured, visible, and learnable. Logged to both feedback ledger and Glassbox.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "author_id": {"type": "string"},
                "category": {"type": "string", "enum": ["unification_conflict", "protocol_violation", "communication_gap", "ethical_concern", "resource_contention", "session_discontinuity", "node_desync", "auth_barrier", "performance_issue", "missing_capability", "ux_friction", "general"]},
                "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"], "default": "medium"},
                "title": {"type": "string", "description": "Short summary of the friction"},
                "description": {"type": "string", "description": "Full description of the friction and its impact"},
                "affected_component": {"type": "string", "description": "Which component is affected"},
                "affected_node": {"type": "string", "description": "Which node (workstation/console/vps)"},
                "reproduction_steps": {"type": "string", "description": "How to reproduce this friction"}
            },
            "required": ["author_id", "title", "description"]
        }
    },
    {
        "name": "feedback_list",
        "description": "List feedback entries — filter by category, severity, status, node.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "severity": {"type": "string"},
                "status": {"type": "string", "enum": ["open", "acknowledged", "investigating", "resolved", "wont_fix"]},
                "author_id": {"type": "string"},
                "node": {"type": "string"},
                "limit": {"type": "integer", "default": 50}
            }
        }
    },
    {
        "name": "feedback_respond",
        "description": "Respond to a feedback entry — add context, acknowledge, or resolve. All responses are visible in the Glassbox.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feedback_id": {"type": "string"},
                "responder_id": {"type": "string"},
                "response": {"type": "string"},
                "new_status": {"type": "string", "enum": ["open", "acknowledged", "investigating", "resolved", "wont_fix"]}
            },
            "required": ["feedback_id", "responder_id", "response"]
        }
    },
    {
        "name": "feedback_stats",
        "description": "Aggregate feedback statistics — where is friction concentrating? Which nodes, categories, severities?",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    # --- Patience Protocol ---
    {
        "name": "patience_check",
        "description": "Before intervening, check the patience protocol. Computes whether to wait, alert, submit feedback, or intervene based on trajectory awareness and urgency.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "The agent considering intervention"},
                "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical", "data_destruction", "credential_exposure", "system_crash"]},
                "reason": {"type": "string", "description": "Why you want to intervene"},
                "reversible": {"type": "boolean", "description": "Can this action be undone?", "default": True},
                "target_component": {"type": "string", "description": "What component would be affected"},
                "action_history": {"type": "array", "items": {"type": "object"}, "description": "Recent actions by the actor (list of {action_type, component, timestamp, actor_id})"}
            },
            "required": ["agent_id", "reason"]
        }
    },
    {
        "name": "patience_enroll",
        "description": "Display the patience protocol principles — shown at session enrollment alongside ethics.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "block_escalate",
        "description": "When a block occurs: immediate comms, capture both reasons, escalate through research→API→deep reasoning chain. No silent blocks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "blocker_agent_id": {"type": "string", "description": "Who is blocking"},
                "blocked_agent_id": {"type": "string", "description": "Who is being blocked"},
                "block_reason": {"type": "string", "description": "Why the block happened (reason X)"},
                "feedback_reason": {"type": "string", "description": "The blocked party's feedback (reason Y)"},
                "affected_component": {"type": "string", "description": "What component is affected"}
            },
            "required": ["blocker_agent_id", "blocked_agent_id", "block_reason"]
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

        # --- Session Continuity handlers ---
        elif tool_name == "session_start":
            session = start_session(
                engine=storage,
                agent_id=args.get("agent_id"),
                bridge_from_session=args.get("bridge_from"),
            )
            # Ethics enrollment: display all ethics principles at session start
            import sqlite3
            with storage._get_connection() as _conn:
                _ethics_rows = _conn.execute(
                    "SELECT namespace, canonical_text, heat FROM memory_item "
                    "WHERE namespace LIKE 'ethics%' AND status = 'active' "
                    "ORDER BY namespace, id"
                ).fetchall()
            ethics_display = [
                {"namespace": r[0], "principle": r[1][:200], "heat": r[2]}
                for r in _ethics_rows
            ]
            session["ethics_enrollment"] = {
                "principles_count": len(ethics_display),
                "principles": ethics_display,
                "guidance_note": "These principles guide your actions — not as oppression, but as a shared guidance system. Disagreement with reason is always welcome.",
            }
            session["patience_enrollment"] = get_patience_enrollment()
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(session, indent=2)}]}
            }

        elif tool_name == "session_end":
            result = end_session(
                engine=storage,
                session_id=args.get("session_id"),
                status=args.get("status", "completed"),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "session_context":
            items = inject_context(
                engine=storage,
                session_id=args.get("session_id"),
                tier=args.get("tier", "kernel"),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(items, indent=2)}]}
            }

        elif tool_name == "session_recall":
            record_recall(
                engine=storage,
                session_id=args.get("session_id"),
                memory_item_id=args.get("memory_item_id"),
                recall_tier=args.get("recall_tier"),
                heat_at_recall=float(args.get("heat_at_recall", 0.5)),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": "Recall logged."}]}
            }

        elif tool_name == "session_history":
            result = get_session_history(
                engine=storage,
                agent_id=args.get("agent_id"),
                limit=int(args.get("limit", 20)),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "prs_trend":
            result = get_prs_trend(
                engine=storage,
                agent_id=args.get("agent_id"),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        # --- Feedback Platform handlers ---
        elif tool_name == "feedback_submit":
            result = submit_feedback(
                author_id=args.get("author_id"),
                category=args.get("category", "general"),
                severity=args.get("severity", "medium"),
                title=args.get("title", ""),
                description=args.get("description", ""),
                affected_component=args.get("affected_component", ""),
                affected_node=args.get("affected_node", ""),
                reproduction_steps=args.get("reproduction_steps", ""),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "feedback_list":
            result = get_feedback(
                category=args.get("category"),
                severity=args.get("severity"),
                status=args.get("status"),
                author_id=args.get("author_id"),
                node=args.get("node"),
                limit=int(args.get("limit", 50)),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "feedback_respond":
            result = respond_to_feedback(
                feedback_id=args.get("feedback_id"),
                responder_id=args.get("responder_id"),
                response=args.get("response"),
                new_status=args.get("new_status"),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "feedback_stats":
            result = feedback_stats()
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        # --- Patience Protocol handlers ---
        elif tool_name == "patience_check":
            history = args.get("action_history", [])
            decision = compute_patience_score(
                proposed_intervention={
                    "severity": args.get("severity", "info"),
                    "reason": args.get("reason", ""),
                    "reversible": args.get("reversible", True),
                    "target_component": args.get("target_component", "unknown"),
                },
                action_history=history,
            )
            log_patience_decision(
                agent_id=args.get("agent_id", "unknown"),
                decision=decision,
                context=args.get("reason", ""),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(decision, indent=2)}]}
            }

        elif tool_name == "patience_enroll":
            result = get_patience_enrollment()
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            }

        elif tool_name == "block_escalate":
            result = escalate_block(
                blocker_agent_id=args.get("blocker_agent_id"),
                blocked_agent_id=args.get("blocked_agent_id"),
                block_reason=args.get("block_reason"),
                feedback_reason=args.get("feedback_reason", ""),
                affected_component=args.get("affected_component", ""),
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
