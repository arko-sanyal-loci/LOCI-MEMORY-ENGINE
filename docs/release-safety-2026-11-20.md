# Local replication and release safety · 2026-11-20

Run window 02:52–02:58 Asia/Dhaka (UTC+06:00). Ubuntu workstation, Python 3.14, and canonical baseline `044cc7db33b9d02d5b27cfbe22d26fff949dcbd7`. PR heads reviewed were [#7](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/pull/7) at `d8efe065e7b2ec59cddaf5b4d1ca34743b72bda2` and [#8](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/pull/8) at `bbd50360a868ea4e97e8888d4cf46786b6652620`.

## Observed results

| Local test | Result |
| --- | --- |
| Canonical test suite, including nine new release-safety regressions | 180 passed, 17 dependency deprecation warnings. |
| Disposable Git source and node clones | Check mode left the checkout unchanged. Apply fast-forwarded validated clean work. Staged, unstaged, untracked and ignored colliding work survived. A bad manifest and the legacy overlay were rejected. |
| Disposable qSympRev transcript and signer/writer fixtures | Provider-like test values became fingerprints before signing. Ordinary facts survived. A credential-like session name blocked signing and state writes. |
| Independent measurement implementation for the existing synthetic MusicSympRev audio files | Standard-library WAV decoding reproduced final pre-line RMS values of 0.01854 (minor early), 0.15451 (minor late), and 0.01860 (major early). The metric uses the last 150 ms before the 4.8 s line. It confirms the engineered signal-level contrast only. |
| Pattern scan of fetched reachable Git refs, including the two PR heads | 475 distinct text blobs scanned. Two matched the URL user-info pattern and require triage. No values were emitted. Regex coverage is limited, and no deployed logs, memory streams, backups or external stores were scanned. |

To reproduce the canonical checks, run `python -m pytest -q tests/test_release_safety.py` or `python -m pytest -q` from the repository root with its test dependencies. The audio recomputation reused the same generated waveforms and workstation. A second operator, independently acquired workloads, and held-out examples are still needed to validate any general performance or mood finding. The reviewed HOT threshold and speculative inference gains were outside this run.

## Deployment and credential boundaries

PR #7 improves manifest generation but its proposed node script retains `git reset --hard` and `git clean -fd`. The replacement here checks by default, validates the fetched commit's tracked-engine manifest, and permits only an explicit fast-forward of clean local main. The tar-over-SSH script previously overlaid a live checkout and restarted a service. It now refuses the operation. No deployment ran during the audit.

The static audit also identified propagation and onboarding wrappers that push to remote nodes, including invocations with `--no-verify`, and a separate memory sync systemd unit. Audit deployed receive hooks, actual unit overrides, schedules, and node copies of those wrappers before authorizing deployment. Those live paths were outside the verified scope.

PR #8 provides the fingerprint and guard approach. The qSympRev change applies that approach at extraction and checks the serialized patch and state before writing. Historic streams and backup replicas still need a separately scoped incident review. Revoke or rotate affected credentials with their issuer, then verify downstream consumers and assess Git refs, PRs, logs, Glassbox, backups, and external replicas. No credentials were rotated and no Git history was rewritten in this run. [GitHub guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)

## Contributions and provenance

- **Arko Sanyal** directed the work and defined the LOCI, CARD, and multimodal evidence questions. **Roza Sanyal** is credited in [AUTHORS.md](../AUTHORS.md) for persistent-memory design. Their shared listening session informed the example selection. No independent listener rating was recorded here.
- **Arc** is credited in AUTHORS.md for formalizing heat and the open-interval invariant. **Gemini Spark** is credited there for the earlier threshold sweep. This run did not repeat that sweep.
- **Claude** authored the reviewed PR commits, including the manifest approach and secret-fingerprint guard. **ChatGPT** supplied the independent-reproduction, deployment-audit and credential-rotation concerns that Arko brought to this review.
- **Codex** implemented and ran the local regression fixtures, remeasured the audio signal, and recorded the evidence and remaining scope. **Mr Calendar** generated earlier local interpretations from synthetic music feature records. Those outputs are hypotheses and were not counted as listener evidence.
