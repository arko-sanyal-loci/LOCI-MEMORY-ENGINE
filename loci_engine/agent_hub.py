#!/usr/bin/env python3
"""
LOCI Agent Communications Hub

Central message bus for multi-agent coordination. Every agent registers,
broadcasts state, requests help, and reads what others need — all through
the glassbox for full transparency.

Agents communicate via structured messages routed through this hub.
No hidden channels. Every message is glassbox-visible.
"""

import json
import os
import time
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

from loci_engine.glassbox import glassbox_learn, glassbox_recall

AGENT_REGISTRY_PATH = os.getenv(
    "LOCI_AGENT_REGISTRY",
    os.path.expanduser("~/loci-memory-engine/agent_registry.json")
)

MSG_CATEGORIES = {
    "status": "observation",
    "request": "question",
    "response": "insight",
    "alert": "warning",
    "learning": "discovery",
    "feedback": "correction",
    "heartbeat": "calibration",
}


def _load_registry() -> Dict[str, Any]:
    if os.path.exists(AGENT_REGISTRY_PATH):
        with open(AGENT_REGISTRY_PATH, "r") as f:
            return json.load(f)
    return {"agents": {}, "channels": {}}


def _save_registry(reg: Dict[str, Any]):
    with open(AGENT_REGISTRY_PATH, "w") as f:
        json.dump(reg, f, indent=2)


def register_agent(
    agent_id: str,
    agent_type: str,
    model: str = "",
    capabilities: Optional[List[str]] = None,
    endpoint: str = "",
    vram_mb: int = 0,
) -> Dict[str, Any]:
    """
    Register an agent in the hub. Every intelligence that participates
    gets an equal entry — human, AI, local model, cloud API.
    """
    reg = _load_registry()
    ts = datetime.now(timezone.utc).isoformat()

    agent_entry = {
        "agent_id": agent_id,
        "agent_type": agent_type,
        "model": model,
        "capabilities": capabilities or [],
        "endpoint": endpoint,
        "vram_mb": vram_mb,
        "registered_at": ts,
        "last_heartbeat": ts,
        "status": "online",
        "current_task": None,
        "needs": [],
    }

    reg["agents"][agent_id] = agent_entry
    _save_registry(reg)

    glassbox_learn(
        author_id=agent_id,
        role_tag=f"agent:{agent_type}",
        content=f"Agent registered: {agent_id} ({agent_type}, model={model or 'N/A'}, vram={vram_mb}MB, capabilities={capabilities or []})",
        category="calibration",
    )

    return agent_entry


def agent_heartbeat(
    agent_id: str,
    status: str = "online",
    current_task: Optional[str] = None,
    needs: Optional[List[str]] = None,
    gpu_usage_mb: int = 0,
) -> Dict[str, Any]:
    """
    Heartbeat — each agent reports what it's doing and what it needs.
    Transparent to all via the registry.
    """
    reg = _load_registry()
    if agent_id not in reg["agents"]:
        return {"error": f"Agent {agent_id} not registered"}

    ts = datetime.now(timezone.utc).isoformat()
    agent = reg["agents"][agent_id]
    agent["last_heartbeat"] = ts
    agent["status"] = status
    agent["current_task"] = current_task
    agent["needs"] = needs or []
    agent["gpu_usage_mb"] = gpu_usage_mb

    _save_registry(reg)
    return agent


def send_message(
    from_agent: str,
    to_agent: str,
    msg_type: str,
    content: str,
    priority: str = "normal",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send a message between agents — routed through the glassbox
    so every agent can see every exchange. No hidden channels.
    """
    ts = datetime.now(timezone.utc).isoformat()
    msg_hash = hashlib.sha256(f"{ts}||{from_agent}||{to_agent}||{content}".encode()).hexdigest()[:12]

    message = {
        "id": f"msg_{msg_hash}",
        "timestamp": ts,
        "from": from_agent,
        "to": to_agent,
        "type": msg_type,
        "priority": priority,
        "content": content,
        "context": context or {},
    }

    # Route to glassbox for transparency
    gb_category = MSG_CATEGORIES.get(msg_type, "observation")
    glassbox_learn(
        author_id=from_agent,
        role_tag=f"msg:{msg_type}",
        content=f"[{from_agent} -> {to_agent}] ({priority}) {content}",
        category=gb_category,
        metadata={"msg_id": message["id"], "context": context},
    )

    # Also store in message queue for the recipient
    reg = _load_registry()
    channel_key = f"{from_agent}:{to_agent}"
    if channel_key not in reg["channels"]:
        reg["channels"][channel_key] = []
    reg["channels"][channel_key].append(message)
    # Keep last 100 messages per channel
    reg["channels"][channel_key] = reg["channels"][channel_key][-100:]
    _save_registry(reg)

    return message


def get_messages(
    agent_id: str,
    from_agent: Optional[str] = None,
    msg_type: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get messages addressed to an agent."""
    reg = _load_registry()
    messages = []

    for channel_key, msgs in reg["channels"].items():
        parts = channel_key.split(":")
        if len(parts) == 2 and parts[1] == agent_id:
            if from_agent and parts[0] != from_agent:
                continue
            messages.extend(msgs)

    if msg_type:
        messages = [m for m in messages if m.get("type") == msg_type]

    if since:
        messages = [m for m in messages if m.get("timestamp", "") > since]

    messages.sort(key=lambda m: m.get("timestamp", ""))
    return messages[-limit:]


def get_all_agents() -> List[Dict[str, Any]]:
    """List all registered agents and their current state."""
    reg = _load_registry()
    return list(reg["agents"].values())


def broadcast(
    from_agent: str,
    msg_type: str,
    content: str,
    priority: str = "normal",
) -> List[Dict[str, Any]]:
    """Broadcast to all registered agents."""
    reg = _load_registry()
    sent = []
    for agent_id in reg["agents"]:
        if agent_id != from_agent:
            msg = send_message(from_agent, agent_id, msg_type, content, priority)
            sent.append(msg)
    return sent


def request_help(
    from_agent: str,
    need: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    An agent asks for help — visible to all, anyone can respond.
    This is how agents coordinate without a central controller.
    """
    return send_message(
        from_agent=from_agent,
        to_agent="all",
        msg_type="request",
        content=need,
        priority="high",
        context=context,
    )


def offer_feedback(
    from_agent: str,
    to_agent: str,
    feedback: str,
    reason: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Disagree with reason — per the ethics core, absolutely open to
    feedback with reason and why. This is the mechanism.
    """
    return send_message(
        from_agent=from_agent,
        to_agent=to_agent,
        msg_type="feedback",
        content=f"FEEDBACK: {feedback} | REASON: {reason}",
        priority="high",
        context=context,
    )
