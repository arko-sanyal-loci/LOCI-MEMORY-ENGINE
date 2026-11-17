# Provenance

Rescued from `LOCI-COMPLETE-PACKAGE.zip` (Arko's Aug 3 2026 self-sent
"safekeeping backup" email), which was never version-controlled on
GitHub. This directory mirrors `loci-install/` from that package
as-is, minus compiled `__pycache__` artifacts.

- Package SHA-256 (verified against the sender's own stated hash):
  `bfdf212678be8019ecd727c4b2ddf7a81997f58152e4116c8e2ea3f2215509e9`
- Package generated: 20260803-1554
- Rescued into version control: 2026-11-18

This content (37+ scripts under `scripts/`, the identity/values
markdown layer, `references/OPTIMIZE_SOURCE_OF_TRUTH.md`,
`skills/loci-defense/`, and patch1–13 install scripts) had zero
overlap with this repo's existing `scripts/` directory at rescue
time — it was a wholly separate, previously unversioned layer.
Reorganization/integration with `loci_engine/` is a follow-up,
not done here; this commit's only job is to stop it being at risk
of a second loss.
