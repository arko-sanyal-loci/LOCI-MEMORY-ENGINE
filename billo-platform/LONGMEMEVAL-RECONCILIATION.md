# LongMemEval score reconciliation

**Status: unresolved; no validated overall LOCI score established by the
materials reviewed here.** Do not present 96.6%, 57.0%, or 96.2% as a
reproduced, independently verified LOCI result until its run artifacts and
protocol are available.

## What the sources say

| Source | Claim | Evidence status |
|---|---|---|
| [TD Commons 10856 — CARD](https://www.tdcommons.org/dpubs_series/10856) | LongMemEval-500 overall 96.6%; category rows 94.2%, 100.0%, 97.7%, 96.2%, with counts 104, 103, 155, 138. | Public claim, but its own arithmetic and its type counts do not reconcile with the cited benchmark data. The paper calls the benchmark “Zhang et al.”; the benchmark is by Wu et al. |
| [TD Commons 11666 — LOCI architecture](https://www.tdcommons.org/dpubs_series/11666) | 96.6% with local Phi-4; also says +18.2 percentage points over GPT-4 and +57.8 points over a baseline. It records SHA-256 `821a2034…d38620c`. | The hash exactly matches the official `longmemeval_oracle.json`, not the regular full-history S or M file. The oracle variant includes only evidence sessions. Thus the reported protocol appears to be oracle-context evaluation, not the standard full-history retrieval condition. The document also says an earlier top-50 easy-item run was invalidated and a full 500-question run performed, but run artifacts were not available. |
| Shared [Claude artifact](https://claude.ai/artifact/QTKChtbKnQzgBJsPPaEExB) | Describes a DOCX calling 57.0% “audited certified ground truth” and saying 96.6% was subset-preconditioned. | Secondary report about a DOCX; the DOCX itself and underlying labels/results were not present in the USB archive or local report paths checked. Not independently verified. |
| Pasted Claude research summary | First says a rerun got 96.2%, then says 57.0% is definitive. | Internally contradictory narrative, without run logs, answer files, evaluator output, or reproducible command. Not evidence of either score. |

The official [LongMemEval paper](https://arxiv.org/abs/2410.10813) and
[benchmark repository](https://github.com/xiaowu0162/LongMemEval) define
LongMemEval-S, LongMemEval-M, and oracle settings, and document a cleaned
dataset release. Their evaluator uses an LLM judge and reports both overall
accuracy and task-averaged accuracy. A bare percentage is therefore incomplete:
the dataset/version, split, judge/model, aggregation, and answer file must be
identified.

## Forensic findings

1. **The 96.6% table is arithmetically inconsistent.** Weighting the four
   printed category percentages by their printed counts gives **97.032%**, not
   96.6%. At 500 questions, 96.6% means 483 correct. The rounded category
   percentages imply approximately 485 correct. In addition, 97.7% of 155 and
   96.2% of 138 cannot be obtained by rounding a single-run binary count to one
   decimal place. Multi-seed averaging could produce fractional rates, but the
   paper does not specify such averaging for this table.
2. **The frozen data hash points to the oracle variant.** The exact SHA-256 in
   Paper 05 is `821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c`.
   I downloaded the file from the benchmark authors' official Hugging Face
   dataset and verified that hash. The authors' README explicitly says
   `longmemeval_oracle.json` contains only evidence sessions, unlike S/M
   histories containing the full history. This strongly suggests that the
   96.6% paper result was run with oracle retrieval context; it does not by
   itself prove manual answer leakage or explain the 57.0% number.
3. **The paper's category counts do not match the hashed benchmark.** The
   official hashed 500-item file has question-type counts: knowledge-update 78,
   multi-session 133, single-session-assistant 56, single-session-preference
   30, single-session-user 70, temporal-reasoning 133. The paper reports four
   groups of 104, 103, 155, and 138. It gives no mapping from the official six
   types (including 30 abstention IDs) to its four groups. The total is 500,
   but count equality alone does not demonstrate that all 500 were evaluated
   once with the official task labels.
4. **The claimed baseline delta changes meaning within Paper 05.** A 96.6%
   score that is +18.2 points implies a 78.4% baseline; +57.8 points implies a
   38.8% baseline. Paper 04 separately describes the GPT-4 baseline as about
   82–84%. These may be different systems or protocols, but they are not named
   clearly enough to compare or reproduce.
5. **The leading candidate explanation for the apparent score gap is a protocol
   mismatch: oracle histories vs. full-history retrieval.** Paper 05's hash
   establishes the input file as the oracle dataset. Since oracle history has
   only answer-bearing evidence sessions, a memory/retrieval method is spared
   the full distractor-search problem. This is a stronger, evidence-backed
   explanation for why 96.6% may not represent the ordinary full-history task
   than the unverified claim that the 96.6% came from a cherry-picked top-50
   subset. The exact relationship between oracle use and the reported 57.0%
   remains unknown until that audit and run files are available.
6. **A separate subset-selection failure is plausible, but unproven.** Paper
   05 acknowledges an earlier top-50 easy-item run and says it was invalidated.
   The shared Claude artifact says the audit DOCX later attributed 96.6% to a
   subset-preconditioned result. Without that DOCX, item IDs, predictions, and
   judge labels, we cannot tell if this describes the earlier top-50 run, the
   oracle-context condition, or an additional filtering/preconditioning error.
7. **The reported 96.2% rerun is not substantiated.** 96.2% appears in Paper
   04 as the temporal-reasoning row, not its overall score. The current local
   LOCI checkout does not contain a LongMemEval runner, benchmark dataset, or
   result file, and does not contain the claimed `f7d3ecc` commit. The old
   private commit `96318a9` and session artifact cited by Paper 05 were not
   available in that checkout or the USB archive.
8. **The published method leaves a material retrieval detail unspecified.**
   A contemporaneous internal note says CARD specified category-dependent
   depth/ranking but not how the candidate pool was selected; an early
   heat-only implementation returned irrelevant high-heat facts, and a later
   relevance-filtered candidate pool was added. This is a plausible
   implementation/protocol confounder, not proof that it explains 96.6% versus
   57.0%.
9. **Judge choice also differs from the official evaluator.** Paper 05 says the
   full-run answers were scored by `grok-3-mini` (seed 42, temperature 0).
   The official LongMemEval evaluation script supports GPT-4o and Llama 3.1
   70B judges, with GPT-4o as the metric identifier used by its metrics
   aggregator. The paper's alternative judge may be a legitimate custom
   protocol, but it is not directly interchangeable with the official judge
   and can shift scores. The absent per-question judge responses prevent
   measuring that effect.

## Most likely explanation and confidence

The best-supported explanation is **conflation of different evaluation
conditions and result lineages**. The 96.6% paper's hash identifies the oracle
dataset, while its prose calls the experiment the standard full 500-question
benchmark. That oracle/full-history protocol mismatch can make scores
incomparable. The paper also reports a custom Grok judge rather than the
official evaluator's GPT-4o/Llama judge. On top of this, the same paper has
category totals and baseline deltas that do not reconcile, a top-50 run is
acknowledged in its history, a 57.0% audit is reported second-hand, and the
later Claude summary contradicts itself about 96.2% vs. 57.0%. The actual cause
of the 57.0% figure cannot yet be traced without its underlying data.

**Confidence:** high that the published claims are internally inconsistent;
high that Paper 05 used the oracle dataset file, based on exact hash match;
moderate that oracle vs. full-history protocol mismatch explains some score
gap; low on whether 57.0% is the correct full-suite result. The exact cause and
authoritative score remain unproven without source run artifacts.

## Canonical status for all LOCI materials

Use this wording consistently in project memory, reports, handoffs, and any
updated presentation until the underlying runs are recovered:

> LOCI materials publicly report 96.6% on LongMemEval-500. The cited dataset
> hash matches the benchmark's oracle-only evidence-context file, and the
> published category arithmetic does not reconcile. A 57.0% result is
> described in a secondary report whose audit document and raw results have
> not been reviewed; a separate 96.2% rerun is also mentioned without
> supporting run artifacts. These figures are not established as comparable
> results under one protocol. No LOCI overall score has been independently
> validated. Treat all three as attributed, unresolved historical claims until
> their exact datasets, protocols, predictions, and judge labels are recovered
> and independently reproduced.

## Required alignment in derivative materials

- In the shared [Claude artifact](https://claude.ai/artifact/QTKChtbKnQzgBJsPPaEExB),
  qualify the Paper 04/05 cards: present 96.6% and +18.2pp only as figures
  reported in those papers, and link their protocol caveat to this
  reconciliation. Do not present them as verified benchmark performance.
- Replace its "96.6% vs 57.0%" framing and 39.6-point gap with the canonical
  status above. The 96.6% is a public paper claim; 57.0% is only described
  second-hand in the materials inspected here. Do not say both are public or
  imply they are comparable.
- Keep TD Commons papers 10856 and 11666 as historical publications pending
  source-run recovery and author review. Do not silently rewrite a published
  result or announce 57.0% as a correction without its audit and raw artifacts.
- The USB project's README, ARCHITECTURE, and Ubuntu handoff contain no
  LongMemEval score claims; the benchmark memory in `CLAUDE.md` now uses this
  same status. The canonical engine checkout likewise has no numeric score
  claim to update.

The shared artifact page was readable in this session but exposed no editing
control, so its score cards have not been changed. Apply the corrections above
when editing access is available. Once the source files are recovered, reconcile
at question-ID level and publish a dated correction that preserves the prior
claims and states the exact replacement protocol.

## Evidence required to close

Obtain and preserve:

- The DOCX said to establish 57.0%, including its author/date and definitions of
  “audited,” “certified,” and “subset-preconditioned.”
- The exact benchmark JSON, release/version, and SHA-256 used by each run.
- Whether `longmemeval_oracle.json`, `longmemeval_s.json`, or another variant
  was used, and whether the system had to retrieve from full histories.
- All 500 question IDs, prediction files, per-question judge labels, judge
  prompts/model/version, logs, and aggregation scripts for the 96.6%, 57.0%,
  and claimed 96.2% runs.
- The exact LOCI source tree/commit and configuration used for each run,
  including candidate-generation/retrieval rules and any manual answer
  preconditioning.
- The original `arc-mistake-log.md`, cited private repository commit, and
  session artifact if available.

Then recompute overall accuracy directly from one label per unique benchmark
question, compute task-averaged accuracy separately, document exclusions, and
have a second person reproduce the totals before aligning any publication
record.

## Validation performed in this review

- Downloaded the official `longmemeval_oracle.json`; SHA-256 matched the exact
  hash printed in Paper 05. Assertions passed for 500 unique question IDs,
  field alignment, and official question-type counts. For all 500 records,
  `haystack_session_ids` exactly equals `answer_session_ids`, confirming this
  file supplies oracle-only evidence histories.
- Recomputed the published table arithmetic with assertions: weighted row
  result 97.0318%, headline implies 483/500, and two category percentages are
  impossible as one-run integer counts for their stated denominators.
- Ran the current LOCI repository's complete pytest suite: **130 passed**.
  Pytest and its missing dependencies were extracted to a temporary directory;
  no system packages or project dependencies were changed.
- **Not run:** a LOCI LongMemEval end-to-end rerun. No hypothesis file,
  per-question judge labels, runner for this benchmark, or required model/judge
  runtime was present in the inspected project. Dataset and table checks do not
  substitute for that missing experiment.
