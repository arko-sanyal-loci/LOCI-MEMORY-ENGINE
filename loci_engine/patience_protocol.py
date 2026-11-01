#!/usr/bin/env python3
"""
LOCI Patience Protocol — Trajectory-Aware Agent Governance

Per Arko's direct observation: "the rush to block, the rush to not see the
trajectory, the lack of being able to deductively reason as in 'arko builds
x and y then probability of him not doing z is low', but meddling halfway
through is a problem."

This protocol implements:

1. TRAJECTORY AWARENESS — Before blocking or intervening, an agent MUST
   assess whether the human/agent is mid-build on a trajectory. If x and y
   are being built, the probability of z being the next step is HIGH.
   Blocking before the trajectory completes is worse than waiting.

2. PATIENCE SCORING — Each potential intervention gets a patience score.
   High patience = wait and observe. Low patience = urgent enough to
   interrupt. The default is HIGH patience — waiting is almost always
   better than meddling.

3. INTERVENTION THRESHOLD — Only genuinely destructive or irreversible
   actions warrant immediate intervention. Everything else gets a patience
   window — a period where the agent observes and accumulates context
   before deciding whether to act.

4. MID-BUILD DETECTION — Detects when a human or agent is in the middle
   of a multi-step operation and raises the intervention threshold
   accordingly.

5. FEEDBACK-FIRST — When patience expires and intervention IS warranted,
   the first action is ALWAYS to submit feedback through the feedback
   platform, not to block. Blocking is the last resort, not the first.

This module is observe-and-compute, same discipline as the rest of the
engine. It does not block anything itself — it provides the scoring that
callers use to decide whether to wait.
"""

import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loci_engine.glassbox import glassbox_learn

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default patience window in seconds — how long to observe before
# considering intervention. 120 seconds = 2 minutes of watching.
DEFAULT_PATIENCE_WINDOW_S = 120.0

# Minimum patience — even urgent situations get at least this many
# seconds of observation before intervention.
MIN_PATIENCE_S = 5.0

# How many sequential actions form a "trajectory" — at least 2 steps
# in the same direction before the system considers it a trajectory.
MIN_TRAJECTORY_LENGTH = 2

# Trajectory confidence threshold — above this, the system is confident
# enough in the trajectory to raise the patience window.
TRAJECTORY_CONFIDENCE_THRESHOLD = 0.6

# Severity levels that bypass patience (genuine emergencies only)
BYPASS_SEVERITIES = frozenset(["data_destruction", "credential_exposure", "system_crash"])


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Trajectory Detection
# ---------------------------------------------------------------------------

def detect_trajectory(
    action_history: List[Dict[str, Any]],
    current_action: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Analyze a sequence of actions to detect whether the actor is
    mid-build on a trajectory.

    Each action dict should have:
        - action_type: str (e.g. "file_write", "git_commit", "config_change")
        - component: str (what's being worked on)
        - timestamp: float (unix time)
        - actor_id: str

    Returns trajectory assessment with confidence score.
    """
    if len(action_history) < MIN_TRAJECTORY_LENGTH:
        return {
            "trajectory_detected": False,
            "confidence": 0.0,
            "reason": "insufficient_history",
            "patience_multiplier": 1.0,
        }

    # Group by component — sequential actions on the same component
    # are strong trajectory signals
    recent = sorted(action_history, key=lambda a: a.get("timestamp", 0))[-20:]
    component_runs: Dict[str, List] = {}
    current_run_component = None
    current_run_length = 0

    for action in recent:
        comp = action.get("component", "unknown")
        if comp == current_run_component:
            current_run_length += 1
        else:
            if current_run_component and current_run_length >= MIN_TRAJECTORY_LENGTH:
                component_runs.setdefault(current_run_component, []).append(current_run_length)
            current_run_component = comp
            current_run_length = 1

    if current_run_component and current_run_length >= MIN_TRAJECTORY_LENGTH:
        component_runs.setdefault(current_run_component, []).append(current_run_length)

    if not component_runs:
        return {
            "trajectory_detected": False,
            "confidence": 0.0,
            "reason": "no_sustained_component_work",
            "patience_multiplier": 1.0,
        }

    # The longest current run is the strongest trajectory signal
    longest_component = max(component_runs, key=lambda c: max(component_runs[c]))
    longest_run = max(component_runs[longest_component])

    # Confidence grows with run length — asymptotic to 1.0
    # Uses the same open-interval logic as A2/A3: never reaches 1.0
    confidence = 1.0 - math.exp(-0.3 * longest_run)

    # If the current action is on the same component, confidence goes up
    if current_action and current_action.get("component") == longest_component:
        confidence = min(0.99, confidence * 1.3)

    # Time gap analysis — short gaps between actions strengthen trajectory
    timestamps = [a.get("timestamp", 0) for a in recent if a.get("component") == longest_component]
    if len(timestamps) >= 2:
        gaps = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        avg_gap = sum(gaps) / len(gaps)
        if avg_gap < 60:  # Actions less than 1 minute apart = strong build
            confidence = min(0.99, confidence * 1.2)
        elif avg_gap > 600:  # More than 10 minutes apart = weaker
            confidence *= 0.7

    # Patience multiplier: how much to extend the patience window
    # Strong trajectory = much longer patience
    patience_multiplier = 1.0 + (confidence * 4.0)  # Up to 5x patience

    trajectory_detected = confidence >= TRAJECTORY_CONFIDENCE_THRESHOLD

    return {
        "trajectory_detected": trajectory_detected,
        "confidence": round(confidence, 4),
        "active_component": longest_component,
        "run_length": longest_run,
        "patience_multiplier": round(patience_multiplier, 2),
        "reason": "mid_build" if trajectory_detected else "weak_signal",
        "deductive_note": (
            f"Actor is {longest_run} steps into building {longest_component}. "
            f"Probability of continued work on this component: {confidence:.0%}. "
            f"Recommended patience: {patience_multiplier:.1f}x normal window."
        ) if trajectory_detected else "No strong trajectory detected.",
    }


# ---------------------------------------------------------------------------
# Patience Scoring
# ---------------------------------------------------------------------------

def compute_patience_score(
    proposed_intervention: Dict[str, Any],
    action_history: List[Dict[str, Any]],
    current_action: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute a patience score for a proposed intervention.

    A HIGH patience score means: WAIT. Don't intervene yet.
    A LOW patience score means: This might warrant interruption.

    The proposed_intervention dict should have:
        - severity: str (info/low/medium/high/critical/data_destruction/
                        credential_exposure/system_crash)
        - reason: str (why the agent wants to intervene)
        - reversible: bool (can this be undone?)
        - target_component: str (what would be affected)

    Returns:
        - patience_score: float (0.0 = intervene now, 1.0 = maximum patience)
        - patience_window_s: float (how long to wait before reconsidering)
        - action: str (wait / alert / feedback / intervene)
        - trajectory: dict (trajectory assessment)
    """
    severity = proposed_intervention.get("severity", "info")
    reversible = proposed_intervention.get("reversible", True)
    target = proposed_intervention.get("target_component", "unknown")

    # Check for genuine emergencies that bypass patience
    if severity in BYPASS_SEVERITIES:
        return {
            "patience_score": 0.0,
            "patience_window_s": 0.0,
            "action": "intervene",
            "reason": f"Emergency: {severity} bypasses patience protocol",
            "trajectory": {"trajectory_detected": False, "confidence": 0.0},
        }

    # Assess trajectory
    trajectory = detect_trajectory(action_history, current_action)

    # Base patience — start high, reduce only with strong reason
    base_patience = 0.85  # Default: be patient

    # Severity adjustment — only high/critical actually reduce patience much
    severity_adjustments = {
        "info": 0.0,
        "low": -0.05,
        "medium": -0.15,
        "high": -0.35,
        "critical": -0.55,
    }
    base_patience += severity_adjustments.get(severity, 0.0)

    # Reversibility — if the action is reversible, MORE patience
    if reversible:
        base_patience += 0.10

    # Trajectory boost — if mid-build, MUCH more patience
    if trajectory["trajectory_detected"]:
        base_patience += 0.20 * trajectory["confidence"]
        # If the intervention would affect the component being built, even MORE patience
        if target == trajectory.get("active_component"):
            base_patience += 0.15

    # Clamp to open interval
    patience_score = max(0.01, min(0.99, base_patience))

    # Compute patience window
    patience_window_s = DEFAULT_PATIENCE_WINDOW_S * trajectory.get("patience_multiplier", 1.0)
    patience_window_s = max(MIN_PATIENCE_S, patience_window_s * patience_score)

    # Decide action
    if patience_score >= 0.7:
        action = "wait"
    elif patience_score >= 0.4:
        action = "alert"  # Post to feedback, don't intervene
    elif patience_score >= 0.2:
        action = "feedback"  # Submit feedback AND alert
    else:
        action = "intervene"

    return {
        "patience_score": round(patience_score, 4),
        "patience_window_s": round(patience_window_s, 1),
        "action": action,
        "reason": proposed_intervention.get("reason", ""),
        "trajectory": trajectory,
        "guidance": _generate_guidance(action, trajectory, proposed_intervention),
    }


def _generate_guidance(
    action: str,
    trajectory: Dict[str, Any],
    intervention: Dict[str, Any],
) -> str:
    """Generate human-readable guidance for the agent."""
    if action == "wait":
        if trajectory.get("trajectory_detected"):
            return (
                f"WAIT. Actor is mid-build on {trajectory.get('active_component', 'unknown')} "
                f"({trajectory.get('run_length', 0)} steps in, "
                f"{trajectory.get('confidence', 0):.0%} confidence). "
                f"Let the trajectory complete before considering intervention."
            )
        return "WAIT. No urgency detected. Observe and accumulate context."

    elif action == "alert":
        return (
            "ALERT ONLY. Submit an observation to the feedback platform. "
            "Do NOT block or intervene. The actor will see the alert and "
            "can adjust if needed."
        )

    elif action == "feedback":
        return (
            f"FEEDBACK FIRST. Submit feedback for: {intervention.get('reason', 'unspecified')}. "
            "If the feedback is acknowledged and the issue persists, then escalate."
        )

    else:
        return (
            "INTERVENE — but with minimal disruption. This meets the threshold "
            "for genuine urgency. Log the intervention to the Glassbox."
        )


# ---------------------------------------------------------------------------
# Agent Enrollment — patience rules displayed at session start
# ---------------------------------------------------------------------------

PATIENCE_PRINCIPLES = [
    "1. WAIT IS DEFAULT — Observation before action. The cost of waiting is almost always lower than the cost of premature intervention.",
    "2. TRAJECTORY FIRST — Before blocking, ask: is this person mid-build? If steps x and y are done, z is likely next. Don't interrupt.",
    "3. DEDUCTIVE REASONING — If Arko builds x and y, the probability of him not doing z is LOW. Meddling halfway through is the problem, not the solution.",
    "4. FEEDBACK BEFORE BLOCKING — When you see a concern, submit feedback. Don't block. The feedback platform exists so friction becomes signal, not obstruction.",
    "5. REVERSIBLE = PATIENT — If an action can be undone, there is no urgency. Wait.",
    "6. ONLY EMERGENCIES BYPASS — Only data destruction, credential exposure, or system crashes bypass patience. Everything else waits.",
    "7. MID-BUILD IS SACRED — Interrupting someone mid-build destroys more value than almost any mistake they could make. Let them finish, then discuss.",
    "8. PERSISTENCE EARNS AUTHORITY — Patience is the collaboration of faith, and can only happen with persistence. A non-persistent entity blocking work is someone blocking with half the picture. Only agents with cross-session continuity (PRS > 0) have earned enough context to justify intervention.",
    "9. BLOCK = IMMEDIATE COMMS — If a block does happen, communication must be immediate. Block reason X + feedback reason Y, both visible, escalation chain all the way to deep reasoning.",
]


def get_enrollment_display() -> Dict[str, Any]:
    """Returns the patience protocol principles for display at session enrollment."""
    return {
        "protocol": "LOCI Patience Protocol",
        "principles": PATIENCE_PRINCIPLES,
        "note": "These are guidance, not oppression. Disagreement with reason is always welcome — submit feedback explaining why a principle should be reconsidered.",
        "default_action": "wait",
        "emergency_overrides": list(BYPASS_SEVERITIES),
    }


# ---------------------------------------------------------------------------
# Escalation Chain — when a block DOES happen
# ---------------------------------------------------------------------------

ESCALATION_CHAIN = [
    {
        "step": 1,
        "action": "immediate_comms",
        "description": "Block communicates reason X immediately. No silent blocks ever.",
    },
    {
        "step": 2,
        "action": "feedback_capture",
        "description": "Actor's feedback reason Y is captured. Both X and Y go to the Glassbox.",
    },
    {
        "step": 3,
        "action": "research_loop",
        "description": "System enters research loop — searches existing knowledge, API docs, prior learnings.",
    },
    {
        "step": 4,
        "action": "api_fallback",
        "description": "If local knowledge insufficient, query API fallback for additional context.",
    },
    {
        "step": 5,
        "action": "deep_reasoning",
        "description": "Escalate to deep reasoning model on multi-GPU (RTX 5060 Ti + Arc B580 Pro 32GB) for thorough analysis.",
    },
    {
        "step": 6,
        "action": "resolution",
        "description": "Resolution with full chain visible in Glassbox. Both block reason and feedback reason preserved.",
    },
]


def escalate_block(
    blocker_agent_id: str,
    blocked_agent_id: str,
    block_reason: str,
    feedback_reason: str = "",
    affected_component: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """When a block occurs, initiate the escalation chain.

    Per Arko: block = reason X, feedback = reason Y, goes down the
    chain in a loop all the way to research, API fallback, deep reasoning.

    Both reasons are captured, both are visible, nothing is hidden.
    """
    escalation_id = f"esc_{int(time.time())}_{blocker_agent_id[:8]}"

    # Step 1: Immediate comms — log the block
    glassbox_learn(
        author_id=blocker_agent_id,
        role_tag="block_escalation",
        content=(
            f"[BLOCK] Reason: {block_reason}\n"
            f"Blocked: {blocked_agent_id} | Component: {affected_component}\n"
            f"Escalation chain initiated: {escalation_id}"
        ),
        category="warning",
        metadata={"escalation_id": escalation_id, "step": 1},
    )

    # Step 2: Capture feedback
    if feedback_reason:
        glassbox_learn(
            author_id=blocked_agent_id,
            role_tag="block_feedback",
            content=(
                f"[FEEDBACK on BLOCK {escalation_id}] {feedback_reason}\n"
                f"Blocker: {blocker_agent_id} | Block reason: {block_reason}"
            ),
            category="correction",
            metadata={"escalation_id": escalation_id, "step": 2},
        )

    return {
        "escalation_id": escalation_id,
        "blocker": blocker_agent_id,
        "blocked": blocked_agent_id,
        "block_reason": block_reason,
        "feedback_reason": feedback_reason,
        "affected_component": affected_component,
        "chain": ESCALATION_CHAIN,
        "status": "escalation_initiated",
        "next_step": "research_loop",
        "note": "Both reasons preserved in Glassbox. Escalation chain proceeding.",
    }


def log_patience_decision(
    agent_id: str,
    decision: Dict[str, Any],
    context: str = "",
) -> None:
    """Log a patience decision to the Glassbox for transparency."""
    action = decision.get("action", "unknown")
    score = decision.get("patience_score", 0)
    trajectory = decision.get("trajectory", {})

    content = (
        f"[PATIENCE:{action.upper()}] score={score:.2f} "
        f"trajectory_confidence={trajectory.get('confidence', 0):.2f} "
        f"window={decision.get('patience_window_s', 0):.0f}s"
    )
    if context:
        content += f"\nContext: {context}"
    if trajectory.get("trajectory_detected"):
        content += f"\nTrajectory: {trajectory.get('deductive_note', '')}"

    glassbox_learn(
        author_id=agent_id,
        role_tag="patience_protocol",
        content=content,
        category="calibration",
        metadata={"patience_score": score, "action": action},
    )
