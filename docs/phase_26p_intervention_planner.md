# Phase 26P — Intervention Planner

Phase 26P converts a triad feedback packet into a ranked plan of next review steps.

```text
CEDFeedbackPacket -> InterventionPlan
```

The plan is advisory only.

## Added

### `backend/dialogues/learning_intervention_planner.py`

Types:

- `InterventionKind`
- `InterventionPriority`
- `InterventionRisk`
- `InterventionProposal`
- `InterventionPlanPolicy`
- `InterventionPlan`

Helpers:

- `intervention_hash(...)`
- `interventions_from_feedback(...)`
- `build_intervention_plan(...)`
- `intervention_plan_summary(...)`

### `tests_dialogues/test_learning_intervention_planner.py`

Tests cover:

- deterministic ids
- ranked proposals
- compact policy
- review flags
- JSON output

## Proposal fields

Each proposal contains:

```text
kind
priority
risk
title
rationale
proposed_action
evidence
requires_human_review
executable = false
```

## Use

```python
triad = run_triad_learning_loop(state, registry=ced.registry, learner_state=learner_state)
plan = build_intervention_plan(triad)
print(plan.summary)
```

## Boundary

This module only ranks review proposals from existing feedback. It does not edit runtime behavior.
