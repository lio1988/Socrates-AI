# Single-Agent Lesson A/B Attestation

**Attestation envelope:** `openclaw_agent_lesson_ab_attestation_v1`  
**Nested instrument report:** `openclaw_agent_lesson_ab_v1`  
**Operator command:** `scripts/openclaw_attest_lesson_ab.py`

## Purpose

The ordinary `run_lesson_ab` harness produces `lesson_ab_v2`, which measures a
lesson applied to a whole council. That result may support global lesson
curation, but it cannot prove that the lesson helped or harmed one particular
agent.

Personal Memory evidence therefore requires a separate matched experiment where
the treatment applies the lesson only to one named `target_agent_id`. The
attestation file must also bind the result to:

1. the exact curated lesson record tested;
2. the exact governed Identity state tested;
3. the exact matched experiment configuration.

A lesson edited under the same `LESSON-*` ID, a later Identity state, or a
changed compute/configuration setup cannot inherit the old result.

The command does not run the experiment. It validates and registers an
already-produced, human-reviewed attestation envelope.

## Command

Helped result:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_lesson_ab.py `
  local_apprentice_001 `
  --report runs\agent_lesson_ab\lesson-0007-helped-attestation.json `
  --action link `
  --verified-by "Your Name"
```

Harmful post-link result:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_lesson_ab.py `
  local_apprentice_001 `
  --report runs\agent_lesson_ab\lesson-0007-harmed-attestation.json `
  --action unlink `
  --verified-by "Your Name"
```

`--verified-by` must match the verifier stored inside the nested instrument
report. The agent cannot verify itself, including through capitalization changes.

## Exact envelope

```json
{
  "schema_version": "openclaw_agent_lesson_ab_attestation_v1",
  "lesson_fingerprint": "64 lowercase SHA-256 hex characters",
  "target_identity_fingerprint": "64 lowercase SHA-256 hex characters",
  "experiment_fingerprint": "64 lowercase SHA-256 hex characters",
  "instrument_report": {
    "schema_version": "openclaw_agent_lesson_ab_v1",
    "reference": "agent-ab/local_apprentice_001/lesson-0007/helped-1",
    "target_agent_id": "local_apprentice_001",
    "lesson_id": "LESSON-0007",
    "treatment_scope": "single_agent",
    "tested": 4,
    "min_tested": 3,
    "verdict": "helped",
    "helped": true,
    "mean_score_delta": 0.25,
    "harm_rate": 0.0,
    "max_harm_rate": 0.0,
    "ratification_regressions": 0,
    "unresolved_regressions": 0,
    "catastrophic_regressions": 0,
    "configuration_mismatches": 0,
    "source": "AgentLessonAB/run-2026-07-10-001",
    "verified_by": "Your Name",
    "verification_reference": "review/agent-ab-001",
    "observed_on": "2026-07-10"
  }
}
```

The envelope field set is exact. A bare `openclaw_agent_lesson_ab_v1` report is
refused because it is not bound to lesson, Identity, and experiment state.

## Lesson fingerprint

`memory_lesson_fingerprint()` computes SHA-256 over the canonical complete
`MemoryLesson.to_record()` value. It includes:

- lesson ID and name;
- lifecycle status;
- lesson type and source;
- `use_when` conditions;
- problem, bad, and good patterns;
- exact lesson text;
- risk text.

Example:

```powershell
.\.venv\Scripts\python.exe -c "
from backend.dialogues.openclaw_memory import load_memory_lessons, memory_lesson_fingerprint
lesson = next(x for x in load_memory_lessons(include_deprecated=True)
              if x.lesson_id == 'LESSON-0007')
print(memory_lesson_fingerprint(lesson))
"
```

The operator bridge recomputes this fingerprint from the current curated
catalogue before registering a new evidence reference.

## Target Identity fingerprint

The report must carry `governed_profile_fingerprint(profile)`. This binds the
experiment to version/stage, known failures, linked lessons, Soul principles,
gates, and append-only governed histories while excluding refreshable
observational counters.

Example:

```powershell
.\.venv\Scripts\python.exe -c "
from backend.dialogues.openclaw_identity import IdentityRegistry, governed_profile_fingerprint
profile = IdentityRegistry('runs/openclaw_identity').load_profile('local_apprentice_001')
print(governed_profile_fingerprint(profile))
"
```

The bridge recomputes it before registering new evidence. Exact reruns of an
already-registered immutable reference remain idempotent after later governed
state changes.

## Experiment fingerprint

The experiment producer must compute a canonical SHA-256 digest over the matched
execution manifest. At minimum that manifest should bind:

- ordered question IDs or question-content hashes;
- target agent ID and role;
- control and treatment prompt fingerprints;
- the single changed treatment: exact lesson injection into only the target;
- model/provider identities and configured available-provider set;
- execution mode and scoring/judging configuration;
- judge eligibility and self-judging exclusions;
- random seeds or deterministic replay identifiers;
- arm execution order/counterbalancing;
- token, timeout, retry, and compute budgets;
- report producer/version.

The bridge validates that `experiment_fingerprint` is canonical lowercase
SHA-256 hex. The named verifier is responsible for confirming that the retained
experiment manifest actually hashes to that value.

All three fingerprints are committed into the immutable evidence source digest.
Changing any binding under the same evidence reference produces a conflict.

## Helped result: Memory link evidence

A link record is accepted only when:

- the envelope and nested report exact schemas match;
- the target agent and named verifier match the command;
- `treatment_scope="single_agent"`;
- the report observation date is valid ISO `YYYY-MM-DD` and not in the future;
- `tested >= min_tested`;
- verdict is `helped` and `helped=true`;
- mean score delta is positive and finite;
- harm rate is within its configured bound;
- there are no ratification, unresolved, catastrophic, or configuration
  regressions;
- the exact lesson fingerprint matches one curated lesson;
- lesson status is `stable` or `verified`;
- the exact governed target Identity fingerprint matches.

The resulting evidence supports:

```text
memory:link_stable_lesson
outcome: confirmed
```

It does not link the lesson by itself.

## Harmed result: Memory unlink evidence

A harmful nested report uses the same exact field set, with a concrete harmed
result such as:

```json
{
  "verdict": "harmed",
  "helped": false,
  "mean_score_delta": -0.2,
  "harm_rate": 0.5,
  "ratification_regressions": 1
}
```

The unchanged required fields remain present in the full nested report. For a
new unlink evidence reference, the lesson must currently be linked in the exact
target profile bound by the envelope.

The resulting evidence supports:

```text
memory:link_stable_lesson
memory:unlink_stable_lesson
outcome: reverted
```

The same immutable harmful evidence may justify the original probation outcome
and a separate canonical unlink proposal.

## Idempotency and immutability

- Exact reruns of the same envelope are idempotent.
- Reusing an evidence reference with changed report content or any changed
  fingerprint is refused.
- Existing exact evidence remains replayable after later governed application.
- Attestation files must be local UTF-8 JSON objects and are bounded to 1 MB.
- URLs, malformed JSON, non-finite metrics, unknown fields, future dates,
  invalid hashes, unsafe lesson IDs, anonymous verification, and secret-shaped
  values fail closed.

## Authority boundary

This bridge creates immutable evidence only. It does not:

- edit `MEMORY_LESSONS.md`;
- link or unlink a lesson;
- create a self-revision proposal;
- approve or apply a proposal;
- confirm or revert a lifecycle;
- change prompts, tools, roles, permissions, or CED authority;
- call any model or provider.

The governed path remains:

```text
single-agent matched A/B experiment + retained manifest
→ bound attestation envelope
→ named non-self attestation
→ immutable Memory evidence
→ bounded self-review
→ agent proposal
→ independent evaluation
→ named non-self approval
→ recoverable application
→ probation
→ confirmation or governed unlink rollback
```
