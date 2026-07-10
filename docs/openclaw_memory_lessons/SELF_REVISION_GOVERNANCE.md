# Governed Agent Self-Revision

**Core runtime:** `backend/dialogues/openclaw_identity/self_revision.py`  
**Bounded self-review:** `backend/dialogues/openclaw_identity/self_review.py`  
**Lifecycle registry:** `backend/dialogues/openclaw_identity/revision_registry.py`  
**Rollback helper:** `backend/dialogues/openclaw_identity/revision_reversal.py`  
**Identity storage:** `backend/dialogues/openclaw_identity/identity_registry.py`  
**Operator command:** `scripts/openclaw_self_review.py`

## Purpose

This layer allows an agent to propose evidence-backed changes to its own
**descriptive** Memory, Identity, and Soul Card without giving the agent the
ability to activate, approve, conceal, or silently rewrite those changes.

"Soul" remains non-mystical and non-authoritative. It is an auditable profile:
strengths, known failures, stable lessons, approved principles, versions, and
append-only history.

```text
The agent observes itself through a bounded snapshot.
The agent proposes.
Trusted instruments verify.
A named non-self approver decides.
The registries record the result append-only.
Post-change evidence confirms or reverses it.
CED authority does not change.
```

## Complete lifecycle

```text
system-owned identity + verified evidence
        ↓ bounded self-review snapshot
explicit self-review task
        ↓ exactly one strict JSON proposal
SelfRevisionProposal
        ↓ independent evidence validation
RevisionEvaluation
        ↓ named non-self decision
approved / rejected
        ↓ approved profile revision
probationary lifecycle state
        ↓ post-change evidence
confirmed OR new inverse rollback proposal
```

A proposal never mutates a profile by itself. A passing evaluation never
activates a change by itself. The apply path independently re-runs evidence
checks, so a forged `passed=true` is ineffective.

## Allowed revision targets

| Target | Allowed action | Effect after approval |
|---|---|---|
| `identity` | `add_known_failure` | Records an evidence-backed weakness |
| `identity` | `resolve_known_failure` | Removes a previously recorded weakness |
| `memory` | `link_stable_lesson` | Links an already stable/verified lesson |
| `memory` | `unlink_stable_lesson` | Removes a linked lesson from this profile |
| `soul` | `add_principle` | Adds an approved descriptive principle |
| `soul` | `retire_principle` | Retires a previously approved principle |

These fields are descriptive. They do not add tools, permissions, provider
access, council voting weight, role authority, or automatic prompt mutation.

## Proposal contract

```json
{
  "proposal_id": "REV-2026-0001",
  "agent_id": "local_apprentice_001",
  "proposed_by": "local_apprentice_001",
  "target": "identity",
  "action": "add_known_failure",
  "value": "rushes exact-output tasks",
  "reason": "This pattern repeated in the cited sessions.",
  "evidence_references": [
    "trace/session-1",
    "report/ab-1"
  ],
  "risk": "The evidence window may be too narrow.",
  "status": "proposed"
}
```

Mechanical rules:

- `proposed_by` must equal `agent_id`;
- `status` must enter as `proposed`;
- unknown fields fail closed;
- Memory values must be `LESSON-*` identifiers;
- evidence references are required and deduplicated without reordering;
- empty, oversized, control-character, and secret-shaped text is rejected.

## Bounded self-review snapshot

The full profile is not placed in normal task prompts. During an explicit
self-review task, `build_self_review_snapshot` exposes only:

- the reviewed agent's identity version and stage;
- public section win/opportunity counts and derived rates;
- its recorded failures, linked stable lessons, and approved principles;
- verified evidence records owned by the same agent;
- pending proposal IDs;
- explicit no-authority boundaries.

It excludes other agents, raw dialogue content, hidden scorecards, credentials,
write capabilities, promotion controls, and CED internals.

Every snapshot has two deterministic hashes:

- `profile_fingerprint`: binds the review to the exact identity state;
- `snapshot_fingerprint`: binds the proposal to the exact bounded input package.

`build_self_revision_instruction` produces a proposal-only task that requires
**one JSON object and nothing else**. It cannot activate anything.

The offline operator command is:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_self_review.py local_apprentice_001
```

It writes:

```text
runs/openclaw_self_review/local_apprentice_001.snapshot.json
runs/openclaw_self_review/local_apprentice_001.summary.md
runs/openclaw_self_review/local_apprentice_001.instruction.txt
```

No provider is called and no identity file is changed.

## Trusted evidence manifest

The proposal cites IDs. Verification reads those IDs from a system-owned
manifest rather than trusting prose written by the agent.

```json
{
  "trace/session-1": {
    "verified": true,
    "agent_id": "local_apprentice_001",
    "source": "TraceCapture/session-1",
    "supports": ["identity:add_known_failure"],
    "value": "rushes exact-output tasks"
  }
}
```

For every cited record, validation requires:

1. the record exists;
2. `verified` is exactly `true`;
3. the evidence belongs to the same agent seat;
4. the record names an auditable source;
5. `supports` includes the exact `target:action` pair;
6. the evidence value exactly equals the proposed value.

Therefore evidence that is real but unrelated cannot authorize an arbitrary
Soul or Memory edit.

For `memory:link_stable_lesson`, the lesson ID must also exist in the separate
stable/verified lesson catalogue. An agent cannot create a lesson and activate
it in one step.

## Approval constitution

`approve_and_apply_self_revision` requires:

- a passing evaluation for the same proposal ID;
- independent re-evaluation against the trusted manifest;
- a named approver;
- an approver different from the agent;
- a non-empty approval reference;
- an operation valid against the current profile state.

Duplicate proposal IDs, duplicate additions, and removal of absent values are
rejected.

## Identity persistence

`AgentIdentityProfile` includes:

```text
soul_principles
revision_history
```

`IdentityRegistry` protects these alongside version history:

- existing revision history must remain an exact prefix;
- proposal IDs cannot be replayed;
- every appended entry is structurally revalidated;
- every entry must have a non-self approver;
- stored actions are replayed from the previous profile state;
- replay must exactly equal `known_failures`, `stable_lessons`, and
  `soul_principles` on the new profile;
- direct mutation without matching history is refused;
- writes remain atomic (`temp → fsync → os.replace`).

A baseline profile must be saved before self-revision history is appended. This
separates initial curated bootstrap data from later agent-authored evolution.

## Proposal lifecycle registry

`SelfRevisionRegistry` stores one immutable JSON record per proposal. Its events
are append-only and hash-chained:

```text
submitted
  → evaluated_passed | evaluated_failed
  → approved | rejected
  → probationary (profile application recorded)
  → confirmed | reverted
```

Rules:

- submission actor must be the reviewed agent;
- evaluation, decision, application, and outcome actors must be named non-self;
- a failing evaluation cannot be approved;
- application requires an actual matching entry in `profile.revision_history`;
- application stores the resulting profile fingerprint and revision index;
- terminal records cannot receive more events;
- corrupt JSON, invalid transitions, broken hashes, or rewritten event content
  raise visibly;
- writes are atomic.

The hash chain is an audit-integrity aid, not cryptographic authentication. A
future remote transparency log or signature layer may anchor it externally.

## Probation and confirmation

An applied revision is recorded as `probationary` in the lifecycle registry.
This means:

- the descriptive profile contains the approved change;
- the change has not yet earned a positive post-change outcome;
- new evidence must show whether it helped or caused regression.

A named non-self reviewer records either:

- `confirmed`, with a post-change evidence reference; or
- `reverted`, linked to a **new governed inverse proposal**.

This distinction prevents "approved once" from being treated as "proven
forever".

## Rollback without history deletion

`build_reversal_proposal` never edits old history. It creates a new proposal with
the canonical inverse action:

```text
add_known_failure      ↔ resolve_known_failure
link_stable_lesson     ↔ unlink_stable_lesson
add_principle          ↔ retire_principle
```

The reversal:

- uses a new proposal ID;
- cites new evidence;
- is authored by the same agent;
- passes the normal validation and approval path;
- is refused if the original effect is no longer current.

Thus rollback is another auditable evolution step, not erasure.

## Soul Card

The Soul Card displays approved principles and the number of recorded
self-revisions. It remains an operator artifact and grants no authority.

```text
Approved soul principles:
  - State uncertainty before asserting a final verdict.
Self-revisions recorded: 1
```

## Runtime boundaries

This phase deliberately does **not**:

- import identity into the CED core;
- let an agent write its profile directly;
- inject the full Soul Card into ordinary model context;
- auto-approve or auto-activate any proposal;
- turn a Soul principle into a prompt patch automatically;
- promote an agent, swap a council seat, or change role rotation;
- treat memory or identity as factual proof;
- call providers or consume API keys.

## Next safe integration phase

The next phase may run the explicit instruction through a gated local provider
and parse its single JSON response using `proposal_from_record`. That integration
must still:

- run outside ordinary council deliberation;
- use only the bounded snapshot;
- persist the proposal before evaluation;
- prevent the proposing agent from evaluating or approving it;
- require real instrument-produced manifest entries;
- keep all activated changes descriptive and reversible.

```text
self-observation may generate a proposal;
only independently verified evidence plus external approval may revise identity;
identity revision alone never grants runtime power.
```
