# Reflection on omissions without judging people

This principle governs how LOCI learns from an omitted fact, an action, or a harmful outcome. The system examines the evidence path and its own response so it can correct its process. It does not infer a person's character or private motive from an action.

## Record the event; do not invent intent

Keep these as distinct, source-linked records:

1. **Observation:** what was directly seen or recorded, by whom, and when.
2. **Available context:** what evidence was available to the actor and to the system at that time. Mark unknown or missing context explicitly.
3. **Outcome:** what followed, including observed damage or recovery.
4. **Omission:** which relevant source-backed item was absent from the system's response or decision, and the retrieval/compression path that omitted it.
5. **Correction:** the evidence later recovered, the system change proposed, and its verification result.

Do not add a motive, diagnosis, character score, or relationship interpretation to this record. A person's stated reason may be recorded as their statement, attributed to them; it is not silently promoted to an independently verified cause. When the reason is unknown, preserve it as unknown. A confidence value does not make an unsupported motive claim safe to store.

## Learn forward; preserve history

An omission is a recoverable system event. Preserve the original source and prior output, link the correction to them, and add a new version of the system's retrieval or presentation rule. Do not rewrite the past event as though the corrected output had been present all along. Distinguish recovery (the source still exists) from reconstruction (the source is missing); never present reconstruction as recovered evidence.

The system may learn that a retrieval path repeatedly fails to surface a source under a particular query or budget. Frequency can tune retrieval priority, but it does not increase factual truth. Relevance, heat, and profile fit are routing signals, not evidence that a claim is true.

## Multiple perspectives and relationship material

Record each account with its speaker/source and time. Do not average conflicting accounts, decide by majority, or treat an absent account as evidence against the absent person. Flag missing perspectives and unresolved contradictions for review. Only use an explicitly recorded statement as an account of that person's stated reason; do not infer a motive from tone, outcome, mood, or a profile.

Mood and relationship hypotheses remain isolated research data until separately validated and explicitly enabled by the user. They must not change a person's standing, access, or treatment. The system can analyze observable communication conditions and offer process improvements without deciding who is at fault.

## Required review questions after an omission

- Which exact source-backed item was missing, and can the original source still be retrieved?
- At what stage did it disappear: ingestion, indexing, retrieval, ranking, compression, budget enforcement, or answer generation?
- What context was available to the system and to the person at that moment? What is unknown?
- What smallest process change would prevent this omission, and what held-out case will check that it did?
- Did the change preserve source attribution, prior versions, dissent, and the option for a person to correct the record?

## Current implementation boundary

`loci_engine.ethics` already provides append-only source/conclusion records, a source-completeness check, missing-party and dissent flags, and a transparency check. Those mechanisms do not automatically capture an answer omission or trace it through retrieval and compression. Root-cause identification is supplied by a caller rather than inferred and verified by the system. This document states the invariant for a future omission-reflection path; it does not claim that path is implemented.

## Acceptance criteria for an implementation

- Build and change the omission-reflection mechanism in the isolated playground first. Do not wire experimental learning into the live engine while its behavior is still being established.
- Each playground experiment has a dated fixture, source/version identifier, exact command, expected behavior, measured result, and limitations. Keep adversarial cases and control cases together so a fix cannot pass only by overfitting to the attack.
- Test recovery across the full path: ingestion, indexing, retrieval, ranking, compression, answer assembly, correction, and history preservation. Include paraphrase, indirect reference, exact values, conflicting versions, long histories, missing source/voice, and deliberately misleading links.
- Promote a change only after repeated, independently reproducible runs meet predeclared criteria, preserve provenance and prior records, improve the targeted failure without degrading controls, and introduce no person-directed motive or character inference. If a check fails or evidence is ambiguous, keep the change in the playground and record the failure.
- An omission record links to the original source, answer/run, retrieval candidates, and later correction.
- Evidence fields are distinct from speaker-attributed statements and from unknowns.
- No inferred motive, character judgment, or relationship score is written by the omission path.
- A correction appends a new record and leaves prior source, output, and history unchanged.
- Tests show that one high-relevance omitted item is recoverable under constrained budgets and that a repeated omission improves the retrieval path without changing source truth weights.
- Relationship and mood material cannot affect a live decision path while the feature is in the research-only state.
