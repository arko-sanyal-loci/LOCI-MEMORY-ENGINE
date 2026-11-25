# RAG Appendix Journal

Status: local implementation, consent-gated; not wired to a background recorder.

The RAG appendix is a separate SQLite database and a separate API from
`LociEngine`'s facts and vector store. It is an append-only, SHA-256 hash-chained
journal for compact profile evidence and profile versions. Use
`rag.journal.RagAppendixJournal` and give it its own database path.

## Consent and profile boundaries

- Both `environment` and `user` scopes start with consent off. Writes and profile
  reads fail closed until the caller explicitly records `grant_consent(scope)`.
- Revocation blocks new writes and profile reads. A later grant starts a new
  consent version; observations from an earlier version are not reused.
- Consent grants, revocations, observations, and generated profiles are journal
  events. SQLite triggers reject update and delete operations. Revocation keeps
  the audit history, so this is not a data-erasure feature.
- Entries accept short categorical tokens only. Do not pass prompts, transcript
  text, face or voice identifiers, precise locations, images, PCM, or other raw
  personal content.
- The audio/video adapter accepts only `audio` and `video` timeline events,
  reduces them to coarse environment features (noise level, timbre band, visual
  motion, change, and sampler fidelity), and ignores captions, transcripts,
  scores, object IDs, frame pixels, raw audio samples, and the `voice_spectrum`
  payload. It requires active
  `environment` consent.
- A user profile must be populated through an explicit, consented feature source
  such as an interaction setting the user directly supplied. Passive audio/video
  events never write to the `user` scope.

## Heatmap and versioning

Each observed `(feature, category)` cell contributes a heat value that decays
with a 30-day half-life by default. A profile contains only cells with at least
three observations and heat confidence of at least 0.60. Each generated profile
is a new journal version that points to the preceding profile event. Profile
output includes support counts and heat-derived confidence so downstream code
can display evidence rather than turning a pattern into a certainty.

This is a categorical recurrence heatmap, not a validated predictive model. It
does not infer emotion, identity, health, intent, or a person's preferences from
media. Those remain out of scope.

## Audio/video timeline relationship

`mr-calendar/media_timeline.py` produces ordered audio, video, authored score,
and caption events for the offline fixture. `RagAppendixJournal.append_stream_event`
can consume audio/video events from that JSONL format. Relative `pts_us` values
are anchored to `session_started_at` when supplied; otherwise journal time uses
the current wall clock. The existing media fixture verifies timing and feature
track separation, but it is not live capture and does not verify microphone or
camera consent dialogs, jitter, drift correction, or model interpretation.

## API sketch

```python
from rag.journal import RagAppendixJournal

journal = RagAppendixJournal("./rag_appendix.sqlite3")
journal.grant_consent("environment")  # call only from a direct user choice
journal.append_stream_event({"track": "audio", "pts_us": 0,
                             "data": {"rms": 0.04, "spectral_centroid_hz": 900}})
profile_event = journal.build_profile("environment")
profile = journal.get_profile("environment")
assert journal.verify_chain()["valid"]
journal.close()
```

The grant call is not a substitute for a user interface that explains purpose,
scope, retention, and revocation. This package exposes the gate; the embedding
application must collect the user's affirmative choice before calling it.

## Glassbox prototype review

`~/Downloads/loci_glassbox_teel_compendium.py` remains an unverified prototype,
not a production integration. Its audio/video path accepts `transcript_hint`
and embeds it in ledger content; its ledger also uses `INSERT OR REPLACE` and
updates prior rows while describing itself as append-only. It has no consent
gate on media ingestion. Do not connect it to live streams or personal profiles
until those behaviors are corrected and independently tested. The new journal
is a separate safe path and does not claim that the downloaded prototype's CARD,
forecasting, or media pipeline is validated.
