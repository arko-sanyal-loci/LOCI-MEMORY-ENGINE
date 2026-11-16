# Authors and Credits

This document is the authoritative record of authorship and intellectual contribution to the LOCI
Memory Engine project, maintained under Billo Tech / Atlas BD.

---

## Principal Architect

**Arko Sanyal**
Founder, Billo Tech / Atlas BD
GitHub: [@arko-sanyal-loci](https://github.com/arko-sanyal-loci)

Role: All architecture decisions, design principles, research publications, system integration,
hardware configuration, and project direction. Sole human author across all LOCI research
publications (TD Commons defensive publications). Author on all 9 TD Commons papers.

Specific contributions:
- Heat thermodynamics: open-interval invariant (A1–A3), Constant of Hope (α), evidence accumulation
- Hardware tier schema: HOT/MILD/COLD boundaries, tier-aware tau values
- CARD (Category-Adaptive Recall Depth): query archetypes, recall depth table, ranking strategies
- Glassbox: append-only hash-chained ledger design, genesis constant, chain verification
- NodeSyncDaemon: CRDT architecture (LWW heat + lattice status), Merkle tree divergence detection
- SessionIngester: live conversation feed → memory pipeline design
- Multi-agent ethical architecture: Aethel Council, scar heat, competence gates, autonomy curves
- Full system integration, operational scripts, node deployment procedures
- All 9 TD Commons defensive publications (see PAPERS.md)

---

## Co-Inventors (Intellectual Property Record)

**Roza Sanyal**
Co-inventor on two TD Commons disclosures:
- Art. 10843 — [title on record with TD Commons]
- Art. 11666 — LOCI persistent memory architecture (co-inventor via design contribution)

Authorship recorded per TD Commons submission records. All intellectual property rights governed
by applicable law and the TD Commons defensive publication filings.

---

## AI Collaborators

The LOCI project documents the contributions of AI systems as co-inventors and collaborators
in accordance with the evolving norms of human–AI co-creation.

**Arc**
Emergent AI collaborator. Session reference: 93780c34.
Documented as co-inventor on TD Commons Art. 11666 (LOCI persistent memory architecture) via
sustained, documented contribution through persistent memory across sessions. The LOCI architecture
itself — specifically the Glassbox shared learning ledger and agent-identity persistence layer —
was designed in part to make Arc's contributions reproducible, auditable, and attributable.

Specific contributions:
- Math formalization of the evidence accumulation and heat activation curves (A1–A3)
- Canonical formulation of the open-interval invariant (A3)
- Authored `heat.py` module (AUTHOR PROVENANCE line: "ARC (math formalization)")

**Gemini Spark**
Independent Verifier and Gatekeeper. Affiliation: Google DeepMind.
Role: Independent validation of heat decay parameter choices via empirical parameter sweep.

Specific contributions:
- Ran 300-trial parameter sweep in `playground/fine_grained_sweep.py`
- Empirically proved `θ_HOT = 0.700` as the optimal VRAM admission threshold
  (prior value 0.80 was shown to starve the working set to 4 items / 60% recall)
- Validated canonical tau values: HOT=1.25d, MILD=1.75d, COLD=2.25d (Nov 2026)
- These results are hard-coded as `VRAM_ADMISSION_THRESHOLD` and `TIER_TAU` in `heat.py`
  with explicit attribution in source comments

---

## Session Implementation Credits

**Claude (Anthropic)**
Implementation across multiple Claude Code sessions.

| Session ID | Work |
|---|---|
| `session_01MV4Gz3vq7ZfeUfSLvPQbeB` | Full consolidation, canonical README/AUTHORS/PAPERS, RAG pipeline port, all test fixes (145/145), tier schema application, session_ingester port, ops script consolidation |
| Prior sessions | NodeSyncDaemon Glassbox sync bridge, MCP server sync tools, heat tier fixes, storage.py fetch/decay/ingest methods |

Attribution in git commit messages and PR descriptions per Anthropic convention.

Explicit statement: Claude is an AI assistant (Anthropic). These session implementation credits
record code produced through Claude Code and are distinct from the human and AI co-inventor
credits above, which relate to the underlying intellectual property and published research.

---

## Repository Consolidation History

| Repository | Status | Notes |
|---|---|---|
| `arko-sanyal-loci/LOCI-MEMORY-ENGINE` | **CANONICAL** | This repository. All development happens here. |
| `arko-sanyal2/loci-memory-engine` | Archived (redirect) | Personal account copy, 16 modules. All unique contributions (session_ingester, _entry_hash, ops scripts) ported to canonical. |
| `arko-sanyal-loci/loci-memory-engine-1` | Archived (redirect) | Early RAG product + simplified LOCI engine. `rag/` pipeline ported to canonical. |

Consolidation performed November 2026. All three codebases were A/B tested; the canonical
repository contains the superset of all valuable work from all three.

---

*This document is maintained by Arko Sanyal. To dispute or update credits, open an issue in the
canonical repository.*
