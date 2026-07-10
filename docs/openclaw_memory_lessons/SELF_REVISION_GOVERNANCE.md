# Governed Agent Self-Revision

**Runtime:** `backend/dialogues/openclaw_identity/self_revision.py`  
**Identity storage:** `backend/dialogues/openclaw_identity/identity_registry.py`

## Purpose

This layer allows an agent to propose evidence-backed changes to its own
**descriptive** Memory, Identity, and Soul Card without giving the agent the
ability to activate, approve, or hide those changes.

"Soul" remains non-mystical and non-authoritative. It is an auditable profile:
strengths, known failures, stable lessons, approved principles, versions, and
append-only history.

```text
The agent proposes.
Trusted instruments verify.
A named non-self approver decides.
The registry records the result append-only.
CED authority does not change.
```

## Lifecycle

```text
agent-authored proposal
        ↓ strict schema and secret guard
trusted evidence manifest
        ↓ ownership + provenance + action/value matching
RevisionEvaluation
        ↓ recommendation only
named non-self approval
        ↓ independent re-evaluation
append-only identity revision
        ↓
new descriptive Soul Card
```

A proposal never mutates a profile by itself. A passing evaluation never
activates a change by itself. The apply path independently re-runs the evidence
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

- `proposed_by` must equal `agent_id`; this is specifically a self-revision
  proposal, not a curator edit disguised as one.
- `status` must enter as `proposed`.
- Unknown fields fail closed.
- Memory values must be `LESSON-*` identifiers.
- Evidence references are required and deduplicated without reordering.
- Empty, oversized, control-character, and secret-shaped text is rejected.

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
  },
  "report/ab-1": {
    "verified": true,
    "agent_id": "local_apprentice_001",
    "source": "LessonAB/report-1",
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
- independent re-evaluation against the supplied trusted manifest;
- a named approver;
- an approver different from the agent;
- a non-empty approval reference;
- an operation that is valid against the current profile state.

Duplicate proposal IDs, duplicate additions, and removal of absent values are
rejected.

## Append-only persistence

`AgentIdentityProfile` now includes:

```text
soul_principles
revision_history
```

The registry protects these alongside version history:

- existing revision history must remain an exact prefix;
- proposal IDs cannot be replayed;
- every appended entry is structurally revalidated;
- every entry must have a non-self approver;
- stored actions are replayed from the previous profile state;
- the replay result must exactly equal `known_failures`, `stable_lessons`, and
  `soul_principles` on the new profile;
- direct mutation without matching history is refused;
- writes remain atomic (`temp → fsync → os.replace`).

A baseline profile must be saved before self-revision history is appended. This
separates initial curated bootstrap data from later agent-authored evolution.

## Soul Card

The Soul Card now displays approved principles and the number of recorded
self-revisions. It remains an operator artifact and does not grant authority.

```text
Approved soul principles:
  - State uncertainty before asserting a final verdict.
Self-revisions recorded: 1
```

## Runtime boundaries

This phase deliberately does **not**:

- import identity into the CED core;
- let an agent write its profile directly;
- inject the full Soul Card into model context;
- auto-approve or auto-activate any proposal;
- turn a Soul principle into a prompt patch automatically;
- promote an agent, swap a council seat, or change role rotation;
- treat memory or identity as factual proof;
- call providers or consume API keys.

## Next integration phase

The next safe phase can add an out-of-band self-review task that asks an agent
to emit the strict proposal schema, plus instrument-specific manifest builders
for Trace Capture, Lesson A/B, Shadow Apprentice, Tree Search, and the Evidence
Harness.

Even then the same boundary remains:

```text
self-observation may generate a proposal;
only independently verified evidence plus external approval may revise identity;
identity revision alone never grants runtime power.
```
