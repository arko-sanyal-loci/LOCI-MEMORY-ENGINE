# loci-install — makeshift LOCI stream extractors for /Volumes/DevDrive/Memory

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23 (5 PHP backdoors, HID injection, treated Roza as trash). Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).


## What this does
Turns the immutable `Memory/` tree into a **living, append-only, cryptographically-gated store** that populates itself from every Claude Code session under `/Volumes/DevDrive/Transcripts/`.

Three streams (matching papers 01 + 02):

| Stream | Signer | Store | What it holds |
|---|---|---|---|
| **isymprev** — informational | `isymprev` | `Memory/streams/isymprev.jsonl` | Heat-decaying entities (14-day half-life, `heat = mentions × exp(-λt)`); tier = HOT / WARM / COLD by paper 01 thresholds. |
| **qsymprev** — quantifiable, versioned | `qsymprev` | `Memory/streams/qsymprev.jsonl` | Typed facts (API keys, paths, dates, versions, IPs, sizes, tickets, amounts) with **source-trust weighting** (user=1.0, assistant=0.5) and a **version chain** — when a fact changes, the old record is marked `superseded` and a new version links back via `prev_hash`. |
| **loci_facts** — DB mirror | `loci_facts` | `/Volumes/DevDrive/.loci-facts.db` (hidden SQLite) | Full paper 01/02 schema: `entity, key, value, value_type, embedding, source_trust, source_session, source_ts, heat, last_access_ts, version, prev_version_id, superseded_by, tier`. Optional 768-d embeddings via `nomic-embed-text` if `ollama` is installed. |

## Trust model
- **Only** `loci_writer.py` mutates anything under `Memory/`.
- Every write requires an **HMAC-SHA256** signature over `signer | target | op | sha256(content)`.
- Signer must be one of `{isymprev, qsymprev, loci_facts}`.
- Target must be under `Memory/`.
- After write: file is re-chflagged `uchg` immediately.
- Every attempt — accepted or refused — is logged to `Memory-state/audit.jsonl`.
- Key lives at `~/.config/loci/signing.key` (chmod 400). Back it up offline.
- `.loci-facts.db` is hidden, chmod 400, chflags `uchg` — even its schema mods require unlocking + re-locking.

## Install
```bash
bash /Volumes/DevDrive/loci-install/install.sh
```
Prompts for sudo once (needed for chflags on the locked Memory/ tree).

## Re-scan
```bash
python3 /Volumes/DevDrive/Memory/extractors/session_scanner.py
```
Or as a launchd/cron job every 30 min.

## Manual write test (should refuse)
```bash
echo '{"signer":"nope","target":"Memory/streams/isymprev.jsonl","op":"append","content":"x","hmac_sha256":"deadbeef"}' \
  | python3 /Volumes/DevDrive/Memory/scripts/loci_writer.py
# → [loci_writer] refused: signer 'nope' not allowed
```

## Files
```
loci-install/
├── install.sh                              ← run this once
├── README.md                               ← you are here
├── scripts/
│   ├── loci_writer.py                      ← the ONLY writer
│   └── sign_patch.py                       ← extractor signing helper
└── extractors/
    ├── session_scanner.py                  ← orchestrator (run this on a cron)
    ├── isymprev_extractor.py               ← informational stream
    ├── qsymprev_extractor.py               ← versioned quantifiable stream
    └── loci_facts_extractor.py             ← hidden SQLite mirror
```
