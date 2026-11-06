# loci-memory-engine

Deterministic context orchestration and memory engine substrate.

The offline learning cycle is `python -m loci_engine.learning_cli demo --db <sqlite-path>`.
It plans, recalls, checks an application policy, and can persist task-scoped lessons
from an explicit external outcome. It does not call a web search or a model.
`--numeric-n` scores that many arithmetic points and is a numerical demo, not a
set of agent plans. `--trace` writes an append-only JSONL of step times and
digests. Those timestamps do not prove the wall clock. CARD recall depth and
the application-policy decision are separate: a valence score does not
authorize a consent-required action. SYMPREV review keeps exact facts intact
and does not call a shorter packet golden.
