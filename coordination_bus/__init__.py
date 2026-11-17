"""Secure, local-first inter-agent coordination bus for LOCI-style multi-agent projects."""

from .bus import (
    AgentPolicy,
    AuthorizationError,
    CoordinationError,
    EventEnvelope,
    LeaseError,
    ProtocolError,
    ReplayError,
    ReviewGateError,
    SecureEventBus,
    TaskBoard,
)

__all__ = [
    "AgentPolicy",
    "AuthorizationError",
    "CoordinationError",
    "EventEnvelope",
    "LeaseError",
    "ProtocolError",
    "ReplayError",
    "ReviewGateError",
    "SecureEventBus",
    "TaskBoard",
]
