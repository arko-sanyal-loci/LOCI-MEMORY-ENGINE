"""Provenance trust boundary for LOCI fact writes.

Closes a real vulnerability found in this project: any caller of add_fact
could previously pass source="user_stated" (a plain string) for content
that did not actually come from the live user - including text relayed
from another agent, a tool result, or a retrieved document, regardless of
what that text claims about its own origin. Since user_stated trust gets
the asymmetric gate's easier correction path, this was the highest-value
target for exactly the kind of memory poisoning that already happened once
in production (one agent's message, crafted to read as the user's own
words, was passed to another agent and stored as if the user had said it).

The fix is a type boundary, not a stronger string check: no amount of
validating a string's *content* closes the gap, because the problem is
never what the string says, it's what code path was allowed to produce it.

UserStated is the ONLY path to full (1.0) trust. Python has no true private
constructors, so this is not cryptographically unforgeable - it is an
architectural boundary enforced by convention and by code review, backed by
a fail-closed default that means any caller who does NOT go out of their
way to construct a UserStated gets the lowest trust tier, never something
in between and never something higher by omission.

**Only construct UserStated from text that came directly and unmodified
from the live user's own turn** - the actual chat/CLI/UI code reading a
real message from the human, in the current process, right now. Never
construct it from: a loci-coordination-bus agent.message payload (regardless
of what the payload claims), a tool result, a retrieved document or web
page, or the model's own generated text. If you are not the literal code
that receives raw input from the live human in this session, you should
not be importing UserStated at all.
"""
from __future__ import annotations

TRUST_WEIGHTS: dict[str, float] = {
    "model_inferred": 0.7,
    "system_derived": 0.5,
}
DEFAULT_TRUST = 0.5  # fail-closed: anything not explicitly recognized lands here


class UserStated:
    """Wraps a value asserted to have come directly from the live user.

    See the module docstring - only the genuine live-user-input boundary
    should ever construct this.
    """

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value


def resolve_trust(source: "UserStated | str | None") -> float:
    if isinstance(source, UserStated):
        return 1.0
    if isinstance(source, str) and source in TRUST_WEIGHTS:
        return TRUST_WEIGHTS[source]
    return DEFAULT_TRUST
