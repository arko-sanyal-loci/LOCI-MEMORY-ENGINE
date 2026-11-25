# Agent operating model

## Purpose

Organize AI agents as accountable, task-scoped contributors within the Billo
Tech project. The business remains human-led: an agent can propose or perform
bounded technical work, but cannot independently make legal, financial,
personnel, customer, publication, or production-release decisions.

## Project lanes

| Lane | Responsibility | Required outcome |
|---|---|---|
| Product and governance | Clarify user need, scope, priorities, and acceptance criteria | Human-approved task and acceptance criteria |
| LOCI memory and research | Memory behavior, provenance, retrieval, and evidence analysis | Reproducible implementation or evidence-linked report |
| Billo orchestration | API, worker, task routing, and integration boundaries | Tested change with explicit service ownership |
| Platform operations | Workstation/VPS configuration, deployment, monitoring, and recovery | Reviewed, reversible operational procedure |
| Quality and assurance | Tests, security and privacy checks, benchmark validation, and release review | Independent verification; author does not self-certify |

These are functional work lanes, not staffed corporate departments.

## Known agent identities and provisional assignments

The model names below are taken from the repository's
[`agent_identities.py`](../loci_engine/agent_identities.py). Assignments are
coordination suggestions, not claims that the models are technically
specialized or hold company positions.

| Agent identity | Recorded model/runtime | Suggested work lane | Constraint |
|---|---|---|---|
| **Apex** | `loci-arc-35b`, Qwen 3.6 35B MoE on Intel Arc | Architecture synthesis and cross-component review | May recommend; a human approves architecture and release decisions |
| **Vesica** | `loci-rtx-14b`, Qwen 3 14B on RTX | Interactive implementation and workstation inference | The repository notes its role prompt is not yet functionally specialized |
| **Synapse** | `loci-agent-14b-qwen3`, Qwen 3 14B | Memory/context integration support | Not the interface's default model; role prompt is not specialized |
| **Billo** | Software platform, not an AI principal | Routes and executes explicitly assigned software tasks | The orchestrator is not a manager or an authority source |

Model availability, tag, role prompt, and hardware assignment can change. Check
the current configuration before routing work; do not treat this table as a
live inventory.

## Task protocol

Every agent task should state:

1. A human owner and a bounded objective.
2. The allowed repositories, files, tools, and environment.
3. Whether the task is read-only, implementation, or operational.
4. Acceptance criteria and how results will be verified.
5. Evidence and provenance requirements for factual or benchmark claims.
6. A review and approval point for changes with external, production, privacy,
   or irreversible effects.

Agents should report uncertainty, failed checks, and incomplete work directly.
They must not claim tests, deployments, benchmark runs, or external actions that
were not performed.

## Safety and authority boundaries

- No attacks, unauthorized access, evasion, disruption, or credential
  collection. Keep work defensive and within a clearly authorized scope.
- Never put credentials, private calendar/browser data, or sensitive personal
  data in source, logs, tests, or reports.
- Production deployment, destructive data changes, firmware changes, external
  publication, contracts, payments, and customer communications require
  explicit human authorization and a documented recovery or review path.
- The LOCI agent hub records ethics guidance with messages; its current code
  describes that guidance as metadata and does not make it an enforced
  authorization boundary. This operating policy must not be mistaken for
  technical enforcement.
- A model that authored a change cannot be its sole release approver.
