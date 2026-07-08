# Prompt Patch Policy v0.1

This document defines how OpenClaw should improve prompts over time.

## Core rule

Prompt evolution must be small, measured, and reversible.

```text
Do not rewrite the whole prompt after one failure.
Patch the smallest instruction that explains the failure.
Test the patch against the old prompt.
Promote only if it improves performance without obvious regressions.
```

## Allowed prompt change types

- Clarify exact-output behavior.
- Clarify unsupported-claim handling.
- Clarify uncertainty handling.
- Clarify role-specific behavior.
- Clarify synthesis section expectations.
- Clarify memory lesson usage.
- Reduce ambiguity in output schema.

## Disallowed automatic changes

- Full prompt rewrite.
- Removing core CED principles.
- Making a provider a permanent authority.
- Making a provider a permanent role.
- Exposing hidden scores to runtime agents.
- Adding private secrets or environment details.
- Changing CED protocol logic from inside a prompt.

## Patch record format

```yaml
patch_id: PATCH-0001
prompt_id: agent_master_prompt
base_version: v0.1
candidate_version: v0.1.1
change_type: small_patch
problem_observed: Agent explained when exact token was requested.
patch_text: When an exact token is requested, return only that token.
expected_effect: Reduce exact-output format violations.
risk: May make open-ended answers too terse if applied too broadly.
test_required: Proof Sprint exact-output subset.
status: proposed
```

## Approval lifecycle

```text
proposed → tested → approved → stable → deprecated
```

## A/B testing rule

Every prompt patch should be tested as:

```text
base prompt vs candidate prompt
same tasks
same provider when possible
same output schema
Evidence Harness comparison
```

## Human approval

Prompt Generator may propose patches, but it should not silently promote them to production.

Human approval or explicit test-gate approval is required before a prompt becomes stable.

## Principle

```text
The system should not reinvent its agents.
The system should sharpen them.
```
