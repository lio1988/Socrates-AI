# Single-Agent Lesson A/B Attestation

**Canonical report schema:** `openclaw_agent_lesson_ab_v1`  
**Operator command:** `scripts/openclaw_attest_lesson_ab.py`

## Purpose

The ordinary `run_lesson_ab` harness produces `lesson_ab_v2`, which measures a
lesson applied to a whole council. That result may help a human decide whether a
lesson belongs in the global curated catalogue, but it cannot prove that the
lesson helped or harmed one particular agent.

Personal Memory evidence therefore requires a separate, explicit report whose
treatment scope is exactly:

```text
treatment_scope = single_agent
```

The report must compare matched control/treatment executions where the tested
lesson is injected only into the named `target_agent_id`. The report producer is
responsible for preserving the same question set, execution mode, configured
provider set, role assignment, judge eligibility, and compute budget across
arms.

The attestation command does not run the experiment. It validates and registers
an already-produced report as a named human act.

## Command

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_lesson_ab.py `
  local_apprentice_001 `
  --report runs\agent_lesson_ab\lesson-0007-helped.json `
  --action link `
  --verified-by "Your Name"
```

For a harmful post-link result:

```powershell
.\.venv\Scripts\python.exe scripts\openclaw_attest_lesson_ab.py `
  local_apprentice_001 `
  --report runs\agent_lesson_ab\lesson-0007-harmed.json `
  --action unlink `
  --verified-by "Your Name"
```

`--verified-by` must match the named verifier stored inside the report. The
agent cannot verify itself, even with different capitalization.

## Helped report: Memory link evidence

```json
{
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
```

A link record is accepted only when:

- the exact schema and field set match;
- the target agent matches the command;
- the treatment scope is `single_agent`;
- `tested >= min_tested`;
- the verdict is `helped` and `helped=true`;
- mean score delta is positive and finite;
- harm rate is within its configured bound;
- there are no ratification, unresolved, catastrophic, or configuration
  regressions;
- `LESSON-*` exists exactly once in the curated catalogue;
- the lesson status is `stable` or `verified`;
- a governed identity profile exists for the target agent.

The resulting evidence supports:

```text
memory:link_stable_lesson
outcome: confirmed
```

It does not link the lesson by itself.

## Harmed report: Memory unlink evidence

```json
{
  "schema_version": "openclaw_agent_lesson_ab_v1",
  "reference": "agent-ab/local_apprentice_001/lesson-0007/harmed-1",
  "target_agent_id": "local_apprentice_001",
  "lesson_id": "LESSON-0007",
  "treatment_scope": "single_agent",
  "tested": 4,
  "min_tested": 3,
  "verdict": "harmed",
  "helped": false,
  "mean_score_delta": -0.2,
  "harm_rate": 0.5,
  "max_harm_rate": 0.0,
  "ratification_regressions": 1,
  "unresolved_regressions": 0,
  "catastrophic_regressions": 0,
  "configuration_mismatches": 0,
  "source": "AgentLessonAB/run-2026-07-10-002",
  "verified_by": "Your Name",
  "verification_reference": "review/agent-ab-002",
  "observed_on": "2026-07-10"
}
```

An unlink record requires a concrete harmed result: negative effect, explicit
regression, or harm beyond the configured bound. The lesson must currently be
linked in the target agent's governed profile when a new evidence reference is
registered.

The resulting evidence supports both:

```text
memory:link_stable_lesson
memory:unlink_stable_lesson
outcome: reverted
```

This allows the same immutable harmful report to justify the original
probationary link outcome and a separate canonical unlink proposal.

## Idempotency and immutability

- Exact reruns of the same report are idempotent.
- Reusing an evidence reference with changed content is refused.
- Existing exact evidence remains replayable even if current profile state later
  changes after governed application.
- Report files must be local UTF-8 JSON objects and are bounded to 1 MB.
- URLs, malformed JSON, non-finite metrics, unknown fields, unsafe lesson IDs,
  anonymous verification, and secret-shaped values fail closed.

## Authority boundary

This bridge only creates immutable evidence. It does not:

- edit `MEMORY_LESSONS.md`;
- link or unlink a lesson;
- create a self-revision proposal;
- approve or apply a proposal;
- confirm or revert a lifecycle;
- change prompts, tools, roles, permissions, or CED authority;
- call any model or provider.

The governed path remains:

```text
single-agent matched A/B report
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
