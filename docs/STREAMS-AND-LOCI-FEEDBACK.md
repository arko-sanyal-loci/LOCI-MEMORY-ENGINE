# LOCI live streams: a guide for learning and giving feedback

**Status:** design guide for an existing set of partial components. This is not a claim that every chat product currently streams into every LOCI node.

## The original idea

The stream extractor reads a conversation incrementally while it is happening. It can prepare a tentative forecast before a speaker finishes, then revise or discard that forecast when the next delta arrives. A forecast is not a final answer, a saved memory, or permission to act. Only a completed, attributable turn can be committed to the session journal.

This matches the original `stream_extractor.py` idea Arko described. The closest implementation currently in this repository is [`loci_engine/session_ingester.py`](../loci_engine/session_ingester.py): it stores complete turns with session and agent identity, then routes recall through CARD. Search the history for the original filename did not find a tracked `stream_extractor.py` or `streams.py`; the incremental extractor and multi-node fan-out remain design work.

## A useful mental model

```text
source adapter
  → ordered deltas (source, session, sequence, timestamp)
  → consent + redaction gate
  → per-agent private context and tentative forecast
  → completed turn / cancellation boundary
  → ContrastiveDeltaPacket (what changed, evidence, confidence, provenance)
  → human-readable review
       ├─ private, versioned LOCI memory (only with the relevant consent)
       └─ Glassbox provenance entry (approved, attributable learning only)
```

Each inference node should have its own identity and private reflection record. A coordinator may compare their sourced deltas and identify agreement or disagreement; it should not blend their private scratchpads or present a speculative forecast as verified fact. Feedback on one agent's answer should route to that agent's reflection record and remain reviewable before it changes durable memory.

## Terms to learn first

| Term | Plain-language meaning | Where to start |
|---|---|---|
| Stream / delta | One ordered piece of a message or observation | This guide's source-adapter sketch |
| SessionIngester | Saves complete turns and recalls them for a query | [`session_ingester.py`](../loci_engine/session_ingester.py) |
| CARD | Chooses how much and what kind of memory to retrieve | [`card_router.py`](../loci_engine/card_router.py) |
| Heat | A relevance/recency weight that decays over time | [`heat.py`](../loci_engine/heat.py) |
| Provenance | Who or what supports a claim, and where it came from | [`provenance.py`](../loci_engine/provenance.py) |
| Glassbox | Append-only, hash-chained record of approved shared learnings | [`glassbox.py`](../loci_engine/glassbox.py) |
| Coordination bus | Authenticated messages exchanged between agent identities | [`coordination_bus/`](../coordination_bus/) |
| Reflection | An agent's review of its own response against later evidence or feedback | [`feedback_platform.py`](../loci_engine/feedback_platform.py) |

## A practical learning path

1. Read the `SessionIngester` module docstring and follow one `ingest_turn()` call into `StorageEngine.ingest_session_turn()`.
2. Follow `recall_for_query()` into `CardRouter.execute_card_retrieval()`; note which fields affect selection and which fields only describe provenance.
3. Read [`glassbox.py`](../loci_engine/glassbox.py) and [`provenance.py`](../loci_engine/provenance.py) before proposing shared writes. These define the audit trail and source labels.
4. Write feedback as a small, concrete packet: *what I expected; what I observed; the exact message or event; what should change; whether this may be remembered*. Mark inference separately from direct observation.
5. Keep new stream parsing behind a feature flag and test with a short, synthetic transcript first. Do not collect another app's chat, microphone, camera, or keystrokes without that app's explicit integration and the participants' consent.

## Feedback packet template

```yaml
source: user-feedback
session_id: <session>
agent_id: <agent>
sequence: <monotonic integer>
observation: <specific output or behavior>
expected: <what would have helped>
evidence_refs: [<message ids or hashes>]
confidence: <low|medium|high>
scope: <this reply|this session|propose private memory|propose shared Glassbox>
consent: <explicit choice for the requested scope>
```

“More compassionate” can guide the current reply without automatically becoming a durable profile. A proposed durable change should retain its source, version, review status, and the ability to supersede it with a later correction. Do not infer a diagnosis or a person's emotional state from timing, voice, or camera features alone.

## Current boundaries

- `session_ingester.py` works on complete turns; a transcript adapter must call it only after the source has defined a completed-turn boundary.
- No universal, verified stream adapter currently connects ChatGPT, Gemini, Claude, Copilot, Arc, and Mr Calendar into one synchronized feed.
- Per-agent identities, access scopes, sequence numbers, and replay protection are prerequisites for a shared live bus. A shared key for all agents would erase accountability.
- Forecasts can be streamed to the UI as provisional and revised in place. They should never be silently appended to memory or the Glassbox.
- Use LOCI as a proposed name for the architecture's concepts, not as a requirement to learn a proprietary language. Start with the table above and ask for explanations using the concrete code paths.
