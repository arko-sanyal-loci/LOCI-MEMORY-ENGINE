# LOCI project memory

## Evidence and attribution

- Treat founder/creator attribution as a claim that needs provenance, not as an
  automatic fact. The user identifies Arko Sanyal as LOCI's founder and creator.
- Verified here: the workstation's public
  [LOCI-MEMORY-ENGINE repository](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE)
  is under the `arko-sanyal-loci` account, and its local Git history contains
  commits authored by Arko Sanyal. This supports repository ownership and
  contribution, but does not independently prove who first conceived or
  founded LOCI.
- [`../docs/organization.md`](../docs/organization.md) records the current
  project attribution and evidence boundary; it is not independent
  corroboration.
- For consequential claims, record the source, date, hash or URL, confidence,
  and what evidence could disprove the claim. Label user reports, inferences,
  and independently verified facts distinctly. Ask for evidence rather than
  filling gaps with confident guesses.

## Safety and ethics

- Do not attack, exploit, intrude into, evade controls on, or disrupt systems.
  Keep work defensive and within an explicitly authorized scope. If scope or
  authorization is unclear, stop and ask.
- Do not expose credentials, private memory, calendar data, or personal
  information in logs, examples, commits, or deployment artifacts.
- Do not flash firmware or run a production installer unless explicitly
  requested and the target, authorization, backup, and recovery path are clear.

## Benchmark evidence

- See [`LONGMEMEVAL-RECONCILIATION.md`](./LONGMEMEVAL-RECONCILIATION.md) for
  the evidence, arithmetic checks, and unresolved score lineage. Canonical
  status: public LOCI materials report 96.6%, while 57.0% and 96.2% appear in
  secondary or ambiguous reports; none is an independently validated overall
  result. The 96.6% paper's dataset hash matches LongMemEval's oracle-only
  evidence-context file, and its category arithmetic does not reconcile. Keep
  these as attributed historical claims, not ground truth, until the run data,
  exact protocol, and per-question labels are available and independently
  reproduced.

## Workspace and deployment

- This folder is the Billo source snapshot extracted from `backup.zip` and
  consolidated under `billo-platform/` in the canonical LOCI-MEMORY-ENGINE Git
  checkout. Its original hashes are recorded in
  `SOURCE-ORIGINAL-MANIFEST.sha256`; the current copy is checked by
  `SOURCE-MANIFEST.sha256`.
- Do not expose this snapshot as a public SaaS yet. The API currently has no
  authentication on its context and scratch endpoints, and CORS permits all
  origins with credentials. The VPS installer also creates `/opt/billo` but
  does not copy the application source there. Resolve these blockers and test
  a staging deployment before any production exposure.
