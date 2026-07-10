# Governed Agent Self-Revision

## Purpose

This layer lets an agent inspect a bounded, evidence-backed view of its own
performance and propose changes to its descriptive **Memory**, **Identity**, and
**Soul Card**.

It does **not** let an agent:

- approve or verify itself;
- edit its identity file directly;
- manufacture evidence;
- alter prompts automatically;
- acquire tools, council weight, permissions, or runtime authority;
- erase old history.

```text
agent observes bounded evidence
        ↓
agent proposes one strict JSON revision
        ↓
trusted non-self instruments verify evidence
        ↓
independent evaluator recomputes the result
        ↓
separate named non-self approver decides
        ↓
recoverable append-only application transaction
        ↓
probationary post-change evidence
        ↓
confirmed OR governed inverse proposal
```

“​​Soul” remains non-mystical: it is a versioned record of approved descriptive
principles, known failures, stable lessons, earned versions, and public evidence.
It never grants authority.

## Runtime modules

| Responsibility | Module |
|---|---|
| Strict proposal and evidence evaluation | `openclaw_identity/self_revision.py` |
| Bounded self-review snapshot | `openclaw_identity/self_review.py` |
| Strict identity profile | `openclaw_identity/identity_profile.py` |
| Full-history identity persistence | `openclaw_identity/identity_registry.py` |
| Immutable verified evidence | `openclaw_identity/revision_evidence.py` |
| Instrument-specific evidence builders | `openclaw_identity/revision_evidence_builders.py` |
| Proposal lifecycle | `openclaw_identity/revision_registry.py` |
| Canonical inverse proposal | `openclaw_identity/revision_reversal.py` |
| Recoverable application journal | `openclaw_identity/revision_transaction.py` |
| Terminal-aware journal verification | `openclaw_identity/revision_transaction_recovery.py` |
| Self-review artifact command | `scripts/openclaw_self_review.py` |
| Interrupted transaction recovery | `scripts/openclaw_recover_revision.py` |
| Joined operator view | `scripts/openclaw_status.py` |

## Allowed descriptive changes

| Target | Action | Meaning |
|---|---|---|
| `identity` | `add_known_failure` | Record an attributed repeated weakness |
| `identity` | `resolve_known_failure` | Resolve it after matched recovery evidence |
| `memory` | `link_stable_lesson` | Link an already stable verified lesson |
| `memory` | `unlink_stable_lesson` | Remove a lesson shown harmful for this agent |
| `soul` | `add_principle` | Add a constitutionally reviewed commitment |
| `soul` | `retire_principle` | Retire it after explicit review |

These actions change descriptive profile fields only.

## Proposal contract

```json
{
  "proposal_id": "REV-2026-0001",
  "agent_id": "local_apprentice_001",
  "proposed_by": "local_apprentice_001",
  "target": "identity",
  "action": "add_known_failure",
  "value": "rushes exact-output tasks",
  "reason": "The cited attributed evidence repeats across sessions.",
  "evidence_references": ["attribution/exact-output-1"],
  "risk": "The attribution window may be narrow.",
  "status": "proposed"
}
```

Rules:

- exact field set; hidden or missing fields fail;
- `proposed_by == agent_id`;
- safe agent/proposal IDs;
- maximum 64 evidence references;
- Memory values must use `LESSON-*`;
- empty, oversized, control-character, and secret-shaped text fails;
- proposals enter only as `proposed`.

## Trusted evidence provenance

Every evidence item used for self-revision requires:

```json
{
  "verified": true,
  "agent_id": "local_apprentice_001",
  "source": "TraceAttribution/window-1",
  "supports": ["identity:add_known_failure"],
  "value": "rushes exact-output tasks",
  "verified_by": "evidence-harness",
  "verification_reference": "report/attribution-1",
  "observed_on": "2026-07-10",
  "outcomes": []
}
```

The verifier must be named and different from the agent. Anonymous
`verified: true` is insufficient, including through the legacy JSON path.

Approved identity history stores:

- exact evidence references;
- verifier identities;
- verification references;
- a deterministic digest of the cited evidence manifest;
- approver identity and approval reference.

## Immutable evidence registry

`RevisionEvidenceRegistry` stores one atomic immutable envelope per evidence
reference.

- schema: `openclaw_self_revision_evidence_v2`;
- exact envelope and record fields;
- record SHA-256 digest;
- filename/reference binding;
- named non-self verifier;
- canonical action supports;
- optional probation outcomes: `confirmed`, `reverted`;
- idempotent exact re-registration;
- conflicting duplicate reference refusal;
- per-record exclusive lock;
- secret-shaped data refusal.

A legacy evidence JSON can temporarily coexist, but duplicate references must
match the registry in **all** relevant semantics, including verifier,
verification reference, observed date, supports, and outcomes.

## Causal instrument builders

Generic session failures and whole-council A/B results cannot automatically
become personal Identity or Memory evidence.

### Identity weakness attribution

`build_identity_failure_evidence` requires:

- at least two distinct sessions and source traces;
- the same failure pattern;
- explicit attribution to the same agent;
- `attribution_verified=true` per observation;
- named non-self verification.

### Identity resolution

`build_identity_resolution_evidence` requires:

- equal matched before/after windows;
- non-overlapping sessions;
- repeated failures before;
- zero failures after;
- explicit agent and pattern identity.

Resolution evidence supports both the original `add_known_failure` action and
its inverse `resolve_known_failure`, and may prove the original probation change
should be `reverted`.

### Agent-specific Lesson A/B

The normal council-wide `lesson_ab_v2` report is deliberately insufficient.
`build_agent_lesson_ab_evidence` requires
`openclaw_agent_lesson_ab_v1` with `treatment_scope="single_agent"`.

Link evidence requires:

- enough tested matched comparisons;
- `verdict="helped"` and `helped=true`;
- positive mean delta;
- no ratification, unresolved, catastrophic, or configuration regression;
- harm rate within its bound.

Unlink evidence requires a concrete harmful result and supports both the
original link and inverse unlink actions.

### Soul constitutional attestation

Soul principles are normative commitments, not facts inferred automatically
from traces. `build_soul_attestation_evidence` requires:

- explicit constitutional review;
- explicit risk review;
- cited supporting evidence references;
- written rationale;
- named non-self reviewer and review artifact.

## Bounded self-review snapshot

Schema: `openclaw_self_review_v4`.

The snapshot contains only:

- this agent’s canonical version and stage;
- public section wins/opportunities and derived rates;
- known failures, linked stable lessons, and approved principles;
- verified evidence owned by this agent;
- named verifier provenance;
- pending proposal IDs;
- explicit no-authority boundaries.

It excludes other agents, raw dialogue content, hidden scorecards, secrets,
provider credentials, CED internals, and write capabilities.

Hard bounds:

```text
verified evidence      ≤ 64
pending proposals      ≤ 32
known failures         ≤ 32
stable lessons         ≤ 64
Soul principles        ≤ 32
rendered instruction   ≤ 65,536 UTF-8 bytes
```

## Two identity fingerprints

The architecture separates:

1. **Governed fingerprint** (`profile_fingerprint`) — Identity version/stage,
   known failures, stable lessons, Soul principles, gates, and append-only
   histories.
2. **Observational fingerprint** — all governed state plus refreshable role
   rates, win counts, opportunities, and session totals.

The snapshot hash commits to both. Therefore the original self-review package is
exactly auditable, while new session metrics can refresh during probation
without falsely appearing as an unauthorized governed identity change.

## Proposal lifecycle

Schema: `openclaw_self_revision_registry_v3`.

```text
submitted
  → evaluated_passed | evaluated_failed
  → approved | rejected
  → probationary
  → confirmed | reverted
```

The first hashed event commits to:

- proposal digest;
- full snapshot fingerprint;
- governed profile fingerprint;
- snapshot evidence-reference digest.

Further rules:

- evaluation is recomputed internally;
- evaluator and approver must be different named actors;
- current governed state and evidence digest must remain unchanged;
- application recomputes the exact expected updated profile;
- outcome evidence must support the exact action, value, and requested outcome;
- outcome verifier and final outcome reviewer must be different actors;
- `reverted` requires an existing canonical inverse proposal bound to the
  current governed state;
- events have exact schemas, bounded count, hash chain, and exclusive lock.

## Full-history identity validation

Every `IdentityRegistry` load proves the **entire** stored history, not only new
append operations.

### Version and stage history

- canonical version set and stage ladder only;
- canonical next gate;
- exact one-step stage movement;
- canonical promotion gate, description, evidence, and reasons;
- named non-self approver;
- reverse validation from current state to bootstrap state.

### Self-revision history

- exact entry fields;
- unique proposal IDs;
- complete verifier provenance and evidence digest;
- non-self verifier and approver;
- reverse reconstruction of the previous field state;
- forward replay must recreate the exact final governed state.

JSON that remains syntactically valid but has rewritten old evidence, hidden
fields, altered verifiers, missing effects, or non-canonical transitions is
reported as corrupt.

## Recoverable application transaction

Identity save and lifecycle application are separate atomic files. A crash
between them is handled by a write-ahead journal:

```text
prepared
  → identity_saved
  → lifecycle_recorded
  → committed
```

Schema: `openclaw_self_revision_transaction_v1`.

The journal commits to:

- exact proposal;
- exact cited evidence records;
- stable lesson catalogue used for evaluation;
- previous and updated profile records;
- previous and updated governed fingerprints;
- application actor/reference/date.

Recovery handles these deterministic cases:

- neither side applied yet;
- Identity saved, lifecycle still approved;
- lifecycle application recorded before journal advancement;
- observational metrics refreshed after Identity save.

Any governed state conflicting with both transaction endpoints fails closed.

A committed application journal remains valid after later probation outcomes by
checking the unique original `applied` event hash rather than assuming it is
still the final lifecycle event.

Operator recovery:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_recover_revision.py `
  local_apprentice_001 REV-2026-0001
```

This command completes an already prepared transaction. It creates no new
proposal, evidence, approval, or authority.

## Rollback without erasure

Rollback creates a **new** inverse proposal:

```text
add_known_failure  ↔ resolve_known_failure
link_stable_lesson ↔ unlink_stable_lesson
add_principle      ↔ retire_principle
```

The original history remains. Reversal requires new evidence, a new proposal ID,
normal evaluation, independent approval, and the same recoverable application
path.

## Operator commands

Create bounded review artifacts:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_self_review.py `
  local_apprentice_001
```

View all evidence, lifecycle, and transaction states:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_status.py
```

`openclaw_status.py` prioritizes incomplete transaction recovery before new
review, experiments, or evidence collection.

## Explicit boundaries

This phase still does not:

- import Identity into the CED core;
- inject full Soul Cards into ordinary dialogue prompts;
- call a provider from the artifact/recovery commands;
- auto-generate trusted personal evidence from generic traces;
- auto-approve or auto-activate changes;
- change council seats, runtime roles, permissions, tools, or voting weight;
- treat hash chains as actor authentication;
- replace future signed evidence or a remote transparency log.

```text
The agent may observe and propose.
Trusted instruments may verify.
Independent governance may approve.
Recoverable registries may apply.
None of these alone grants authority.
```
