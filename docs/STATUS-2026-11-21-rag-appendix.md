# LOCI RAG Appendix Journal — Status Update
**Date:** 2026-11-21
**Status:** Implemented and locally verified

## Work completed

- Added `rag.journal.RagAppendixJournal` as a separate SQLite store for
  append-only, SHA-256 hash-chained observations and profile versions.
- Added separate, default-off `environment` and `user` consent scopes. Revoking
  consent blocks future writes and profile reads; renewed consent starts a new
  evidence version.
- Added a decaying categorical heatmap with support and confidence thresholds.
- Added an audio/video timeline adapter that persists coarse environment
  categories only. It ignores captions, score tracks, object IDs, and raw media.
- Added an offline voice-spectrum analyzer to Mr Calendar: periodic pitch,
  periodicity, spectral centroid/rolloff, and coarse bands. It does not identify
  speakers or infer gender, and the journal excludes these measurements.
- Documented the connection to the offline media timeline and reviewed the
  downloaded Glassbox prototype's current consent and mutability gaps.

## Verification

- `./.venv/bin/pytest -q tests/test_journal.py`: 6 passed.
- `./.venv/bin/pytest -q`: 103 passed, 8 skipped.
- Synthetic 180-frame video + authored audio integration: 339 ordered timeline
  events (240 audio, 96 video, 2 score, 1 caption); 338 journal events; profile
  generation succeeded; hash chain verified.
- The existing `langsmith` dependency emitted 17 `asyncio.iscoroutinefunction`
  deprecation warnings.
- Voice-spectrum tests: 4 passed. Repeated the synthetic timeline integration
  after adding spectrum fields; 339 ordered events flowed through, the profile
  built, and the journal hash chain remained valid.

## Limits

- No background scheduler or live microphone/camera capture was added. The
  embedding application must gather affirmative consent and call profile
  generation at an appropriate cadence.
- The current check is synthetic; hardware stream capture, timing drift, live
  permission prompts, and predictive quality remain unverified.
- The downloaded `loci_glassbox_teel_compendium.py` remains a prototype. Its
  audio/video bridge stores transcript hints, and its ledger updates/replaces
  rows; it has not been connected to the new journal.
