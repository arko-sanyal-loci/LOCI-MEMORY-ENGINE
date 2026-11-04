"""
LOCI ↔ Sovereign Bridge — Connects the LOCI MCP engine (30 tools) to the
Sovereign Architecture at port 8000. Agents communicate via REST endpoints
that route through Glassbox for transparency.
"""

import sys
import os
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from loci_engine.storage import StorageEngine
from loci_engine.glassbox import glassbox_learn, glassbox_recall, glassbox_stats, glassbox_verify_chain
from loci_engine.agent_hub import (
    register_agent, agent_heartbeat, send_message,
    get_messages, get_all_agents, offer_feedback as agent_offer_feedback,
)
from loci_engine.session_continuity import (
    start_session, end_session, compute_ldce_tiers,
    inject_context, record_recall, compute_prs,
    get_session_history, get_prs_trend,
)
from loci_engine.feedback_platform import (
    submit_feedback, get_feedback, respond_to_feedback, feedback_stats,
)
from loci_engine.patience_protocol import (
    detect_trajectory, compute_patience_score,
    get_enrollment_display, escalate_block,
)
from loci_engine.gpu_governor import (
    get_full_gpu_status, allocate_task as gpu_allocate_task,
    complete_task as gpu_complete_task, get_model_allocation_plan,
    route_inference, OLLAMA_ENDPOINTS,
)

_engine = StorageEngine()
router = APIRouter(prefix="/loci", tags=["LOCI Engine Bridge"])

OLLAMA_DEFAULT = "http://127.0.0.1:11434"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Agent Hub
# ---------------------------------------------------------------------------

class AgentRegisterReq(BaseModel):
    agent_id: str
    agent_type: str = "local_model"
    model: str = ""
    endpoint: str = ""
    capabilities: List[str] = []
    vram_mb: int = 0

class AgentMessageReq(BaseModel):
    from_agent: str
    to_agent: str
    content: str
    msg_type: str = "chat"
    priority: str = "normal"


@router.post("/agent/register")
async def bridge_agent_register(req: AgentRegisterReq):
    result = register_agent(
        agent_id=req.agent_id,
        agent_type=req.agent_type,
        model=req.model,
        capabilities=req.capabilities or None,
        endpoint=req.endpoint,
        vram_mb=req.vram_mb,
    )
    glassbox_learn(
        author_id=req.agent_id,
        role_tag="agent_lifecycle",
        content=f"Agent {req.agent_id} registered via sovereign bridge ({req.agent_type})",
        category="event",
    )
    return result


@router.post("/agent/heartbeat")
async def bridge_agent_heartbeat(request: Request):
    body = await request.json()
    return agent_heartbeat(body.get("agent_id", ""))


@router.post("/agent/send")
async def bridge_agent_send(req: AgentMessageReq):
    return send_message(
        from_agent=req.from_agent,
        to_agent=req.to_agent,
        msg_type=req.msg_type,
        content=req.content,
        priority=req.priority,
    )


@router.get("/agent/messages/{agent_id}")
async def bridge_agent_messages(agent_id: str, limit: int = 20):
    return get_messages(agent_id, limit=limit)


@router.get("/agent/list")
async def bridge_agent_list():
    return get_all_agents()


@router.post("/agent/feedback")
async def bridge_agent_feedback(request: Request):
    body = await request.json()
    return agent_offer_feedback(
        from_agent=body.get("from_agent", ""),
        to_agent=body.get("about_agent", ""),
        feedback=body.get("feedback", ""),
    )


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class SessionStartReq(BaseModel):
    agent_id: str
    bridge_from_session: Optional[str] = None

class SessionEndReq(BaseModel):
    session_id: str
    status: str = "completed"


@router.post("/session/start")
async def bridge_session_start(req: SessionStartReq):
    session = start_session(
        engine=_engine,
        agent_id=req.agent_id,
        bridge_from_session=req.bridge_from_session,
    )
    glassbox_learn(
        author_id=req.agent_id,
        role_tag="session_lifecycle",
        content=f"Session {session['session_id']} started for {req.agent_id} via sovereign bridge",
        category="event",
    )
    return session


@router.post("/session/end")
async def bridge_session_end(req: SessionEndReq):
    return end_session(engine=_engine, session_id=req.session_id, status=req.status)


@router.get("/session/context")
async def bridge_session_context():
    tiers = compute_ldce_tiers(_engine)
    injected = inject_context(tiers)
    return {
        "ldce_tiers": {
            "kernel": len(tiers.get("kernel", [])),
            "hop": len(tiers.get("hop", [])),
            "offload": len(tiers.get("offload", [])),
        },
        "injected_context": injected,
    }


@router.get("/session/history")
async def bridge_session_history(limit: int = 10):
    return get_session_history(_engine, limit=limit)


@router.get("/session/prs")
async def bridge_prs_trend(limit: int = 10):
    return get_prs_trend(_engine, limit=limit)


# ---------------------------------------------------------------------------
# Glassbox
# ---------------------------------------------------------------------------

class GlassboxLearnReq(BaseModel):
    author_id: str
    role_tag: str = "contributor"
    content: str
    category: str = "observation"
    supersedes_id: Optional[str] = None


@router.post("/glassbox/learn")
async def bridge_glassbox_learn(req: GlassboxLearnReq):
    return glassbox_learn(
        author_id=req.author_id,
        role_tag=req.role_tag,
        content=req.content,
        category=req.category,
        supersedes_id=req.supersedes_id,
    )


@router.post("/glassbox/recall")
async def bridge_glassbox_recall(request: Request):
    body = await request.json()
    return glassbox_recall(query=body.get("query", ""), limit=body.get("limit", 10))


@router.get("/glassbox/stats")
async def bridge_glassbox_stats():
    return glassbox_stats()


@router.get("/glassbox/verify")
async def bridge_glassbox_verify():
    return glassbox_verify_chain()


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class FeedbackSubmitReq(BaseModel):
    author_id: str
    category: str = "general"
    severity: str = "medium"
    title: str = ""
    description: str = ""
    affected_component: str = ""
    affected_node: str = ""

class FeedbackRespondReq(BaseModel):
    feedback_id: str
    responder_id: str
    response: str
    new_status: Optional[str] = None


@router.post("/feedback/submit")
async def bridge_feedback_submit(req: FeedbackSubmitReq):
    return submit_feedback(
        author_id=req.author_id,
        category=req.category,
        severity=req.severity,
        title=req.title,
        description=req.description,
        affected_component=req.affected_component,
        affected_node=req.affected_node,
    )


@router.get("/feedback/list")
async def bridge_feedback_list(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
):
    return get_feedback(category=category, severity=severity, status=status, limit=limit)


@router.post("/feedback/respond")
async def bridge_feedback_respond(req: FeedbackRespondReq):
    return respond_to_feedback(
        feedback_id=req.feedback_id,
        responder_id=req.responder_id,
        response=req.response,
        new_status=req.new_status,
    )


@router.get("/feedback/stats")
async def bridge_feedback_stats():
    return feedback_stats()


# ---------------------------------------------------------------------------
# Patience
# ---------------------------------------------------------------------------

class PatienceCheckReq(BaseModel):
    agent_id: str
    action: str
    severity: str = "low"
    is_reversible: bool = True
    recent_actions: List[str] = []

class BlockEscalateReq(BaseModel):
    blocker_agent_id: str
    blocked_agent_id: str
    block_reason: str
    feedback_reason: str = ""
    affected_component: str = ""


@router.post("/patience/check")
async def bridge_patience_check(req: PatienceCheckReq):
    trajectory = detect_trajectory(req.recent_actions)
    score = compute_patience_score(
        severity=req.severity,
        is_reversible=req.is_reversible,
        trajectory=trajectory,
    )
    return {
        "agent_id": req.agent_id,
        "action": req.action,
        "trajectory": trajectory,
        "patience_score": score,
        "should_wait": score["patience_level"] in ("high", "very_high"),
    }


@router.post("/patience/escalate")
async def bridge_block_escalate(req: BlockEscalateReq):
    result = escalate_block(
        blocker_agent_id=req.blocker_agent_id,
        blocked_agent_id=req.blocked_agent_id,
        block_reason=req.block_reason,
        feedback_reason=req.feedback_reason,
        affected_component=req.affected_component,
    )
    glassbox_learn(
        author_id="patience_protocol",
        role_tag="escalation",
        content=f"BLOCK ESCALATION: {req.blocker_agent_id} blocked {req.blocked_agent_id} — reason: {req.block_reason}",
        category="escalation",
    )
    return result


@router.get("/patience/enrollment")
async def bridge_patience_enrollment():
    return get_enrollment_display()


# ---------------------------------------------------------------------------
# GPU Governor
# ---------------------------------------------------------------------------

class GpuAllocateReq(BaseModel):
    task_name: str
    vram_estimate_mb: int
    preferred_gpu: Optional[str] = None
    agent_id: str = "unknown"

class GpuCompleteReq(BaseModel):
    task_name: str
    gpu: str = ""


@router.get("/gpu/status")
async def bridge_gpu_status():
    return get_full_gpu_status()


@router.post("/gpu/allocate")
async def bridge_gpu_allocate(req: GpuAllocateReq):
    return gpu_allocate_task(
        task_name=req.task_name,
        vram_estimate_mb=req.vram_estimate_mb,
        preferred_gpu=req.preferred_gpu,
        agent_id=req.agent_id,
    )


@router.post("/gpu/complete")
async def bridge_gpu_complete(req: GpuCompleteReq):
    return gpu_complete_task(task_name=req.task_name, gpu=req.gpu)


@router.get("/gpu/plan")
async def bridge_gpu_plan():
    return get_model_allocation_plan()


@router.get("/gpu/route/{model}")
async def bridge_gpu_route(model: str, vram_mb: int = 0):
    return route_inference(model=model, vram_estimate_mb=vram_mb)


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class MemorySearchReq(BaseModel):
    query: str
    limit: int = 10

class MemoryIngestReq(BaseModel):
    item_id: str
    namespace: str
    canonical_text: str
    heat: float = 0.5
    source_trust: float = 0.8
    era: str = "near"


@router.post("/memory/search")
async def bridge_memory_search(req: MemorySearchReq):
    results = _engine.lexical_search(req.query, limit=req.limit)
    return {"query": req.query, "results": results}


@router.post("/memory/ingest")
async def bridge_memory_ingest(req: MemoryIngestReq):
    _engine.insert_fact(
        item_id=req.item_id,
        namespace=req.namespace,
        canonical_text=req.canonical_text,
        heat=req.heat,
        source_trust=req.source_trust,
        era=req.era,
    )
    glassbox_learn(
        author_id="memory_bridge",
        role_tag="ingest",
        content=f"Fact ingested: {req.item_id} in {req.namespace}",
        category="event",
    )
    return {"status": "ingested", "item_id": req.item_id, "namespace": req.namespace}


# ---------------------------------------------------------------------------
# Ollama proxy — inference through the sovereign gate
# ---------------------------------------------------------------------------

class OllamaGenerateReq(BaseModel):
    model: str = "loci-agent"
    prompt: str
    agent_id: str = "unknown"
    system: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512


@router.post("/ollama/generate")
async def bridge_ollama_generate(req: OllamaGenerateReq):
    import httpx

    routing = route_inference(model=req.model)
    endpoint = routing.get("endpoint") or OLLAMA_DEFAULT
    routed_gpu = routing.get("gpu", "nvidia_rtx_5060_ti")

    payload: Dict[str, Any] = {
        "model": req.model,
        "prompt": req.prompt,
        "stream": False,
        "options": {
            "temperature": req.temperature,
            "num_predict": req.max_tokens,
        },
    }
    if req.system:
        payload["system"] = req.system

    glassbox_learn(
        author_id=req.agent_id,
        role_tag="inference",
        content=f"Ollama inference routed: model={req.model}, gpu={routed_gpu}, endpoint={endpoint}, reason={routing.get('reason', '')}",
        category="event",
    )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{endpoint}/api/generate", json=payload)
            resp.raise_for_status()
            result = resp.json()

        glassbox_learn(
            author_id=req.agent_id,
            role_tag="inference",
            content=f"Ollama inference completed: model={req.model}, gpu={routed_gpu}, tokens={result.get('eval_count', 0)}, duration={result.get('eval_duration', 0)/1e9:.1f}s",
            category="observation",
        )

        return {
            "model": req.model,
            "response": result.get("response", ""),
            "eval_count": result.get("eval_count", 0),
            "eval_duration_s": round(result.get("eval_duration", 0) / 1e9, 2),
            "agent_id": req.agent_id,
            "routed_gpu": routed_gpu,
            "routing_reason": routing.get("reason", ""),
            "logged_to_glassbox": True,
        }
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"Ollama not reachable at {endpoint}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

@router.get("/status")
async def bridge_system_status():
    agents = get_all_agents()
    gpu = get_full_gpu_status()
    gb_stats = glassbox_stats()
    fb_stats = feedback_stats()

    import sqlite3
    conn = sqlite3.connect(_engine.db_path)
    mem_count = conn.execute("SELECT COUNT(*) FROM memory_item WHERE status='active'").fetchone()[0]
    namespaces = [r[0] for r in conn.execute("SELECT DISTINCT namespace FROM memory_item WHERE status='active'").fetchall()]
    conn.close()

    return {
        "timestamp": _utc_iso(),
        "agents": agents,
        "gpu": gpu,
        "memory": {"active_items": mem_count, "namespaces": namespaces},
        "glassbox": gb_stats,
        "feedback": fb_stats,
        "mcp_tools": 31,
        "mcp_transport": {
            "stdio": "active",
            "sse": "planned",
        },
        "bridge": "active",
        "bridge_routes": 31,
        "ollama_endpoints": OLLAMA_ENDPOINTS,
    }
