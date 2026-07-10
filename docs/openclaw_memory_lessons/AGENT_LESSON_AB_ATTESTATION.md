# Single-Agent Lesson A/B Attestation

**Attestation envelope:** `openclaw_agent_lesson_ab_attestation_v1`  
**Experiment manifest:** `openclaw_agent_lesson_ab_experiment_v1`  
**Nested instrument report:** `openclaw_agent_lesson_ab_v1`  
**Operator command:** `scripts/openclaw_attest_lesson_ab.py`

## Purpose

The ordinary `run_lesson_ab` harness produces `lesson_ab_v2`, which measures a
lesson applied to a whole council. That result may support global lesson
curation, but it cannot prove that the lesson helped or harmed one particular
agent.

Personal Memory evidence therefore requires a separate matched experiment where
the treatment applies the lesson only to one named `target_agent_id`. The
attestation file binds the result to:

1. the exact curated lesson record tested;
2. the exact governed Identity state tested;
3. a retained, self-verifying matched experiment manifest.

A lesson edited under the same `LESSON-*` ID, a later Identity state, a changed
question set, contaminated control arm, changed provider/judge set, or changed
compute budget cannot inherit the old result.

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
  "experiment_fingerprint": "SHA-256 of the exact experiment_manifest below",
  "experiment_manifest": {
    "schema_version": "openclaw_agent_lesson_ab_experiment_v1",
    "target_agent_id": "local_apprentice_001",
    "lesson_id": "LESSON-0007",
    "treatment_scope": "single_agent",
    "question_hashes": [
      "64-char SHA-256 of question 1",
      "64-char SHA-256 of question 2",
      "64-char SHA-256 of question 3",
      "64-char SHA-256 of question 4"
    ],
    "control_configuration": {
      "base_configuration_fingerprint": "64-char SHA-256",
      "injected_lesson_fingerprints": [],
      "injection_target_agent_id": ""
    },
    "treatment_configuration": {
      "base_configuration_fingerprint": "same SHA-256 as control",
      "injected_lesson_fingerprints": [
        "exact lesson_fingerprint from the envelope"
      ],
      "injection_target_agent_id": "local_apprentice_001"
    },
    "execution_mode": "deterministic-local-or-mock-mode",
    "provider_ids": ["provider-a", "provider-b"],
    "judge_configuration": {
      "judge_set_fingerprint": "64-char SHA-256",
      "self_judging_allowed": false
    },
    "random_seeds": [101, 102, 103, 104],
    "arm_orders": [
      ["control", "treatment"],
      ["treatment", "control"],
      ["control", "treatment"],
      ["treatment", "control"]
    ],
    "counterbalanced": true,
    "compute_budget": {
      "token_limit": 1000,
      "timeout_seconds": 30.0,
      "retry_limit": 0
    },
    "producer_version": "agent-lesson-ab-runner-v1"
  },
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

The envelope, manifest, arm configurations, judge configuration, compute budget,
and nested report all use exact field sets. A bare
`openclaw_agent_lesson_ab_v1` report is refused.

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

```powershell
.\.venv\Scripts\python.exe -c "
from backend.dialogues.openclaw_memory import load_memory_lessons, memory_lesson_fingerprint
lesson = next(x for x in load_memory_lessons(include_deprecated=True)
              if x.lesson_id == 'LESSON-0007')
print(memory_lesson_fingerprint(lesson))
"
```

The bridge recomputes this fingerprint from the current curated catalogue before
registering a new evidence reference.

## Target Identity fingerprint

The envelope carries `governed_profile_fingerprint(profile)`. This binds the
experiment to version/stage, known failures, linked lessons, Soul principles,
gates, and append-only governed histories while excluding refreshable
observational counters.

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

## Self-verifying experiment manifest

The script computes canonical JSON using sorted keys, compact separators,
UTF-8, and `allow_nan=false`, then SHA-256 hashes the complete retained manifest.
The result must exactly equal `experiment_fingerprint`.

The manifest is also checked semantically:

- manifest agent, lesson, and `single_agent` scope match the nested report;
- question hashes are unique lowercase SHA-256 values;
- seeds and arm orders align one-to-one with the question set;
- every arm order contains control and treatment exactly once;
- a counterbalanced multi-question run exercises both arm orders;
- control and treatment share one base configuration fingerprint;
- control contains no lesson injection and no injection target;
- treatment injects exactly the bound lesson into only the target agent;
- provider IDs are non-empty and distinct;
- the judge-set fingerprint is present and self-judging is false;
- token limit and timeout are positive, retry count is non-negative;
- instrument `tested` count cannot exceed the manifest question count;
- all fields are secret-scanned and non-finite JSON values are refused.

All three external fingerprints are committed into the immutable evidence
source digest. Changing the lesson, Identity, experiment manifest, or report
under the same evidence reference produces a conflict.

## Helped result: Memory link evidence

A link record is accepted only when:

- envelope, manifest, and nested report exact schemas match;
- target agent and named verifier match the command;
- the observation date is ISO `YYYY-MM-DD` and not in the future;
- the instrument source is non-empty;
- `tested >= min_tested`;
- verdict is `helped` and `helped=true`;
- mean score delta is positive and finite;
- harm rate is within its configured bound;
- there are no ratification, unresolved, catastrophic, or configuration
  regressions;
- exact lesson and Identity fingerprints match current governed state;
- lesson status is `stable` or `verified`.

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

For a new unlink evidence reference, the lesson must currently be linked in the
exact target profile bound by the envelope.

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
- Reusing an evidence reference with changed report, manifest, or fingerprint is
  refused.
- Existing exact evidence remains replayable after later governed application.
- Attestation files must be local UTF-8 JSON objects and are bounded to 1 MB.
- URLs, malformed JSON, non-finite metrics, unknown fields, future dates,
  invalid hashes, replayed question hashes, self-judging, unsafe lesson IDs,
  anonymous verification, and secret-shaped values fail closed.

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
single-agent matched A/B experiment
→ retained self-verifying manifest
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
