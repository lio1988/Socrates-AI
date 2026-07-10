# Governed Attestation Bridges

This phase connects existing strict evidence builders to explicit operator
commands. It does not add automatic inference, approval, application, or CED
authority.

## Identity failure bridge

Default mode converts repeated marker-verified shadow section losses into
immutable `identity:add_known_failure` evidence.

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_evidence.py local_apprentice_001 --verified-by "Your Name"
```

Requirements:

- same apprentice seat;
- valid shadow runs only;
- at least two distinct session IDs;
- same section pattern;
- named non-self attester;
- exact reruns are idempotent;
- expanded windows append a new immutable record.

## Identity resolution bridge

Resolution is explicit and never inferred merely because scores improved.

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_evidence.py local_apprentice_001 --mode resolution --section blind_spots --window 2 --verified-by "Your Name"
```

Requirements:

- an existing pure `identity:add_known_failure` evidence record for the exact
  same weakness value;
- an adjacent before-window and after-window of equal size;
- every before session is a marker-verified loss;
- every after session is a marker-verified win;
- no replayed session IDs;
- named non-self attestation.

The output supports both the original weakness and its canonical
`resolve_known_failure` inverse. The evidence itself does not mutate Identity.

## Soul constitutional attestation bridge

Soul principles are normative commitments. They are not mined automatically
from traces.

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_evidence.py local_apprentice_001 `
  --mode soul `
  --action add_principle `
  --principle "State uncertainty before asserting a final verdict." `
  --evidence-ref "shadow/..." `
  --rationale "Repeated verified evidence warrants this commitment." `
  --review-reference "review/soul-001" `
  --constitutional-review --risk-reviewed `
  --verified-by "Your Name"
```

Requirements:

- explicit `add_principle` or `retire_principle` action;
- at least one existing evidence reference owned by the same agent;
- explicit constitutional review flag;
- explicit risk review flag;
- written rationale;
- named review artifact;
- named non-self reviewer;
- secret-shaped content refusal.

## Curator review surface

`scripts/openclaw_review.py` now reads dialogue history, immutable revision
evidence, and lifecycle records. When revision artifacts exist it writes:

```text
runs/openclaw_proposals/SELF_REVISION_PIPELINE.md
```

The report contains evidence references, supported actions, verifier names,
proposal states, and the next governed operator action. It is read-only and
never changes Identity, Memory, Soul, or proposal lifecycle state.

## Closed authority boundary

```text
instrument or constitutional review
→ named attestation
→ immutable evidence
→ bounded self-review
→ agent proposal
→ independent evaluation
→ named non-self approval
→ recoverable application
→ probation
→ confirmation or governed rollback
```

Attestation creates raw material only. Every later gate remains mandatory.
