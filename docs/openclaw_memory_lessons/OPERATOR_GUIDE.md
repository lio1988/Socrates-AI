# Operator Guide — one page, every button

**Canonical name:** `OPENCLAW_MEMORY_LESSONS_OPERATOR_GUIDE`

What to run, what it means, and which decisions need a human hand.
Everything below is offline and free unless a mode says otherwise.
All commands from the repo root, PowerShell:

```powershell
# use the venv python everywhere:
.\.venv\Scripts\python.exe <script>
```

---

## Mode 0 — Where am I? (always safe, start here)

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_status.py
```

Shows: lessons found, traces/shadow records accumulated, identity registry
state, pending proposals, governed self-revision lifecycle/transaction state,
env gates, and the **next recommended command**. Add `--json` for a
machine-readable report.

## Mode A — Demo shadow run (free, deterministic, zero setup)

```powershell
.\.venv\Scripts\python.exe scripts\shadow_dialogue.py
```

A mock apprentice shadows a mock council: per-section comparison, Soul Card,
gate progress. Records accumulate in `runs/openclaw_shadow/`.

## Mode B — Real local apprentice (needs Ollama, no cloud credits)

```powershell
$env:CED_ENABLE_LOCAL_APPRENTICE = "1"
$env:CED_LOCAL_LLM_MODEL = "llama3.1:8b"     # any model you have pulled
# optional: $env:CED_LOCAL_LLM_URL = "http://localhost:11434/v1"
.\.venv\Scripts\python.exe scripts\shadow_dialogue.py
```

If the server is down the script stops with a hint — it never silently
falls back to a mock. Evidence accumulates across runs; the identity
registry (`runs/openclaw_identity/`) keeps earned versions/promotions.

## Mode C — Council dialogue (mock free; live costs credits)

```powershell
.\.venv\Scripts\python.exe scripts\live_dialogue.py "your question"
# live: set CED_ENABLE_LIVE_PROVIDERS=1 + ANTHROPIC_API_KEY (see its header)
```

Writes a trace per session to `runs/openclaw_traces/`.

## Mode D — Review accumulated evidence (the curator step)

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_review.py
```

Reads all traces, shadow records, immutable self-revision evidence, and proposal
lifecycles. It may write these read-only curator surfaces under
`runs/openclaw_proposals/`:

```text
PROPOSED_LESSONS.md
PROPOSED_PROMPT_PATCHES.md
SELF_REVISION_PIPELINE.md
```

The pipeline report shows each agent’s verified evidence, proposal status, and
next governed action. Nothing becomes active merely because it appears there.

## Mode E — Whole-council Lesson A/B test

```powershell
.\.venv\Scripts\python.exe -c "
import asyncio
from backend.dialogues.openclaw_memory import run_lesson_ab, load_memory_lessons
pool = [l for l in load_memory_lessons() if l.lesson_id == 'LESSON-XXXX']
report = asyncio.run(run_lesson_ab(['deliberation scoring assembly'], pool))
print(report['verdict'], report['mean_score_delta'])
"
```

Matched-pair: same question, councils with vs without the lesson. Verdicts:
`helped` / `harmed` / `no_effect` / `untested`. This `lesson_ab_v2` report may
support global curation, but it is deliberately insufficient for personal agent
Memory because the treatment covers a whole council.

## Mode F — Human promotion checklist (the only step that changes status)

1. Run Mode 0 + Mode D; read the evidence (gate lines, proposal files).
2. **Lessons/patches**: edit the status field by hand in the curated file
   (`MEMORY_LESSONS.md`) or in the registry spec — after Mode E says
   `helped`. Never promote an untested proposal.
3. **Agent identity** (gate says PASSED):

```powershell
.\.venv\Scripts\python.exe -c "
from backend.dialogues.openclaw_identity import *
reg = IdentityRegistry('runs/openclaw_identity')
p = reg.load_profile('local_apprentice_001')
gate = next_gate_for(p.identity_version)
evidence = evidence_from_shadow_traces('local_apprentice_001',
    __import__('backend.dialogues.openclaw_memory', fromlist=['load_jsonl'])
    .load_jsonl('runs/openclaw_shadow/shadow_records.jsonl'))
result = evaluate_gate(gate, evidence)
reg.save_profile(record_promotion(p, result, approved_by='YOUR NAME'))
print('promoted to', reg.load_profile('local_apprentice_001').identity_version)
"
```

`record_promotion` refuses a failing gate, an unnamed approver, and
self-approval — the checks run even when you drive it by hand.

## Mode G1 — Attest a repeated Identity weakness

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_evidence.py local_apprentice_001 --verified-by "Your Name"
```

Converts repeated marker-verified shadow section losses into immutable
`identity:add_known_failure` evidence. At least two distinct sessions are
required; replayed session IDs never double-count.

## Mode G2 — Attest an Identity resolution

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_evidence.py local_apprentice_001 --mode resolution --section blind_spots --window 2 --verified-by "Your Name"
```

Resolution is deliberately explicit. It requires:

- an existing attested weakness with the exact same value;
- two equal adjacent windows for that section;
- every session in the before-window is a verified loss;
- every session in the after-window is a verified win;
- distinct, non-replayed sessions.

The resulting evidence supports the original weakness and its canonical
`resolve_known_failure` inverse. It does not change Identity by itself.

## Mode G3 — Attest a Soul constitutional review

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

Soul principles are normative commitments and are never inferred automatically.
The command refuses unless the reviewer explicitly confirms constitutional and
risk review, cites existing evidence owned by the same agent, writes a rationale,
and names a review artifact. Use `--action retire_principle` for a reviewed
retirement. Evidence still requires a separate agent proposal, evaluation,
non-self approval, and recoverable application.

## Mode G4 — Attest single-agent Lesson A/B Memory evidence

The ordinary Mode E report is whole-council evidence and cannot enter one
agent's Memory. Mode G4 accepts only an explicit
`openclaw_agent_lesson_ab_v1` report where the treatment scope is
`single_agent`.

Helped result → link evidence:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_lesson_ab.py `
  local_apprentice_001 `
  --report runs\agent_lesson_ab\lesson-0007-helped.json `
  --action link `
  --verified-by "Your Name"
```

Harmful post-link result → unlink/revert evidence:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_lesson_ab.py `
  local_apprentice_001 `
  --report runs\agent_lesson_ab\lesson-0007-harmed.json `
  --action unlink `
  --verified-by "Your Name"
```

The verifier named on the command must match the verifier inside the report.
Link evidence requires a curated `stable`/`verified` lesson and a clean helped
verdict with no regressions. Unlink evidence requires a concrete harmed verdict
and a lesson currently linked to that agent. The command writes only immutable
evidence; it never edits `MEMORY_LESSONS.md` or the agent profile. See
[AGENT_LESSON_AB_ATTESTATION.md](AGENT_LESSON_AB_ATTESTATION.md) for the exact
report schema.

## Mode H — Bounded self-review package (agent proposes, nothing activates)

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_self_review.py local_apprentice_001
```

Builds the snapshot/summary/instruction artifacts an agent may use to author
one descriptive proposal. Evidence comes only from the trusted registry
(Mode G1/G2/G3/G4). Evaluation, named non-self approval, recoverable
application, probation, and confirmation/rollback all still follow — see
[SELF_REVISION_GOVERNANCE.md](SELF_REVISION_GOVERNANCE.md).

## Mode I — Recover an interrupted revision transaction

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_recover_revision.py local_apprentice_001 <proposal_id>
```

Completes or verifies a crash-interrupted identity application from its
journal. `openclaw_status.py` lists incomplete transactions and recommends
this exact command when one exists.

## Run manifest (concept — not yet built)

A future `runs/openclaw_runs/<run_id>/MANIFEST.json` will bundle per run:
trace file, shadow records, identity snapshot, lesson ids used, prompt
version/fingerprint, A/B results, review output path — so "why did this
gate pass?" is one file. Until then, `openclaw_status.py` is the joined-up
view and the audit files above are the ground truth.

## Troubleshooting

- **"no local server at http://localhost:11434/v1"** — start Ollama
  (`ollama serve`) and pull a model (`ollama pull llama3.1:8b`).
- **Greek text garbled in the console** — `$env:PYTHONIOENCODING = "utf-8"`.
- **New .md/.json files not committing** — `.gitignore` ignores them;
  use `git add -f` (and note `runs/` is deliberately not committed).
- **Live run refuses** — both gates needed: `CED_ENABLE_LIVE_PROVIDERS=1`
  AND a real `ANTHROPIC_API_KEY` in the environment (never in files).
- **Nothing to review** — traces, evidence, and lifecycle records accumulate
  only after their corresponding modes run; the review reads history.
- **Resolution refused** — first attest the weakness, then provide a clean
  adjacent loss→win window of the requested size.
- **Soul refused** — confirm both review flags and cite existing evidence for
  the same agent.
- **Lesson A/B Memory attestation refused** — confirm the report uses
  `openclaw_agent_lesson_ab_v1`, targets the same agent, names the same verifier,
  and references a curated lesson with a compatible helped/harmed verdict.

## The constitution (what no mode can do)

The system proposes; a human promotes. Judging stays anonymous; agents never
see hidden scores. Failures stay missing, never fabricated. The apprentice
cannot touch final answers before the Promotion Arena. Memory, Identity, and
Soul remain descriptive and never grant CED authority. Every artifact above is
a plain auditable file.
