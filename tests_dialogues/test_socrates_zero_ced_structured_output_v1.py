"""Offline parity locks for the reduced benchmark's CED provider schemas."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Mapping

import pytest
from pydantic import ValidationError

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_epistemic import (
    VerificationResult,
    parse_verification_response,
)
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    AgentTask,
    CouncilVerdict,
    DialogPhase,
    EpistemicMarker,
    ProviderResponse,
    ProviderStatus,
    SCORE_WEIGHTS,
    SECTION_ORDER,
    ScoreBreakdown,
    SectionDraft,
    SectionName,
    TaskKind,
)
from backend.dialogues.provider_registry import parse_and_validate_move
from backend.dialogues.providers import FakeProvider
from backend.dialogues.reasoning_prompts import (
    BAYESIAN_UPDATE_DIRECTIVE,
    COMMITMENT_EMISSION_DIRECTIVE,
    ELENCHUS_TARGET_DIRECTIVE,
    OBJECTION_VERIFICATION_DIRECTIVE,
    OPENING_CONTENT_DIRECTIVE,
    RATIFICATION_CONTENT_DIRECTIVE,
    REFLECTION_COMMITMENT_DIRECTIVE,
    SCORE_CONTENT_DIRECTIVE,
    SOCRATIC_FOLLOWUP_MANDATE,
    SOCRATIC_OPERATORS,
    SYNTHESIS_CONTENT_DIRECTIVE,
    marker_is_contracted,
)
from backend.dialogues.socratic import (
    GroundingRefType,
    InquiryState,
    MaieuticOperator,
    commitment_events_from_reflection,
    commitments_from_move,
    validate_socratic_content,
)
from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
    SUPPORTED_CED_TASK_KINDS_V1,
    assert_ced_structured_schema_parity_v1,
    ced_structured_response_format_v1,
    ced_structured_schema_name_v1,
    ced_structured_schema_sha256_v1,
    validate_ced_structured_output_v1,
)
from backend.dialogues.socrates_zero.contracts import ContractValidationError


def _task(
    kind: TaskKind,
    phase: DialogPhase,
    role: AgentRole,
    *,
    task_id: str | None = None,
) -> AgentTask:
    return AgentTask(
        task_id=task_id or f"offline_{kind.value}_{role.value}",
        session_id="offline_schema_test",
        agent_id=f"agent_{role.value}",
        role=role,
        phase=phase,
        question="What follows from the available evidence?",
        task_kind=kind,
    )


def _tasks() -> Dict[str, AgentTask]:
    return {
        "opening": _task(
            TaskKind.SOCRATIC_QUESTION,
            DialogPhase.OPENING,
            AgentRole.SOCRATES,
        ),
        "followup": _task(
            TaskKind.SOCRATIC_QUESTION,
            DialogPhase.ELENCHUS,
            AgentRole.SOCRATES,
        ),
        "initial_critic": _task(
            TaskKind.INITIAL_RESPONSE,
            DialogPhase.INITIAL_RESPONSE,
            AgentRole.ELENCHUS_CRITIC,
        ),
        "initial_empiricist": _task(
            TaskKind.INITIAL_RESPONSE,
            DialogPhase.INITIAL_RESPONSE,
            AgentRole.EMPIRICIST,
        ),
        "initial_synthesizer": _task(
            TaskKind.INITIAL_RESPONSE,
            DialogPhase.INITIAL_RESPONSE,
            AgentRole.SYNTHESIZER,
        ),
        "elenchus_critic": _task(
            TaskKind.ELENCHUS_OBJECTION,
            DialogPhase.ELENCHUS,
            AgentRole.ELENCHUS_CRITIC,
        ),
        "elenchus_empiricist": _task(
            TaskKind.ELENCHUS_OBJECTION,
            DialogPhase.ELENCHUS,
            AgentRole.EMPIRICIST,
        ),
        "reflection": _task(
            TaskKind.REFLECTION_REVISION,
            DialogPhase.REFLECTION,
            AgentRole.REFLECTOR,
        ),
        "reconstruction": _task(
            TaskKind.RECONSTRUCTION_PROPOSAL,
            DialogPhase.RECONSTRUCTION,
            AgentRole.MAIEUTIC_RECONSTRUCTOR,
        ),
        "synthesis": _task(
            TaskKind.SYNTHESIS_DRAFT,
            DialogPhase.SYNTHESIS,
            AgentRole.SYNTHESIZER,
        ),
        "move_score": _task(
            TaskKind.MOVE_SCORE,
            DialogPhase.OPENING,
            AgentRole.FINAL_EVALUATOR,
        ),
        "section_score": _task(
            TaskKind.SECTION_SCORE,
            DialogPhase.SYNTHESIS,
            AgentRole.FINAL_EVALUATOR,
        ),
        "ratification": _task(
            TaskKind.COUNCIL_RATIFICATION,
            DialogPhase.RATIFICATION,
            AgentRole.FINAL_EVALUATOR,
        ),
        "verification": _task(
            TaskKind.OBJECTION_VERIFICATION,
            DialogPhase.ELENCHUS,
            AgentRole.FINAL_EVALUATOR,
        ),
    }


def _sample_contents() -> Dict[str, Dict[str, Any]]:
    score = {name: 7.0 for name in ScoreBreakdown.model_fields}
    synthesis = {
        # A three-word stub no longer passes: the acceptance contract now
        # requires a synthesis section to carry a proposition, not a label.
        section.value: (
            f"This {section.value.replace('_', ' ')} states what the council "
            "actually concluded and why that conclusion follows."
        )
        for section in SECTION_ORDER
    }
    synthesis["epistemic_marker"] = "reasonable_hypothesis"
    return {
        "opening": {
            "question": "Which distinction would change what follows?",
            "operator": "distinguish",
            "epistemic_marker": "open_uncertainty",
        },
        "followup": {
            "question": "What supports the causal step in commitment c1?",
            "operator": "request_grounds",
            "grounded_in": [{"ref_type": "commitment", "ref_id": "c1"}],
            "introduces_new_proposition": False,
            "inquiry_state": "ready_for_reconstruction",
            "aporia": None,
            "epistemic_marker": "open_uncertainty",
        },
        "initial_critic": {
            "contradictions": ["The asserted causal attribution exceeds the comparison."],
            "weak_assumptions": ["Voluntary adoption is treated as random."],
            "logic_gaps": ["Training is not separated from tool access."],
            "critique_summary": "The observed difference does not identify the tool effect.",
            "commitments": ["The full causal attribution is not yet justified."],
            "epistemic_marker": "logical_inference",
        },
        "initial_empiricist": {
            "factual_claims": [{
                "claim": "Output was 18 percent higher after three months.",
                "status": "reported_observation",
                "notes": "The comparison is not randomized.",
            }],
            "evidence_quality": 0.45,
            "documentation_gaps": ["Pre-treatment trends are not supplied."],
            "commitments": ["Selection and training are competing explanations."],
            "epistemic_marker": "reasonable_hypothesis",
        },
        "initial_synthesizer": {
            "synthesis_draft": "The result is associational, not a clean tool effect.",
            "key_insights": ["Selection and training are both confounded."],
            "unresolved_tensions": ["The relative size of each effect is unknown."],
            "commitments": ["Randomization or a credible quasi-experiment is needed."],
            "epistemic_marker": "reasonable_hypothesis",
        },
        "elenchus_critic": {
            "contradictions": ["The conclusion isolates a treatment never isolated in design."],
            "weak_assumptions": ["Applicant teams are assumed comparable."],
            "logic_gaps": ["The training effect is attributed to the tool."],
            "critique_summary": "Neither selection nor training is ruled out.",
            "target_section": "core_answer",
            "epistemic_marker": "logical_inference",
        },
        "elenchus_empiricist": {
            "factual_claims": [{
                "claim": "Managers volunteered for treatment.",
                "status": "stated_in_task",
                "notes": "This permits selection bias.",
            }],
            "evidence_quality": 0.35,
            "documentation_gaps": ["A tool-by-training factorial comparison is absent."],
            "target_section": "crucial_stress_test",
            "epistemic_marker": "logical_inference",
        },
        "reflection": {
            "answer_to_socratic_question": "The comparison does not support that step.",
            "commitments_retained": ["c1"],
            "commitments_revised": [],
            "commitments_withdrawn": [],
            "commitments_suspended": [],
            "new_commitments": ["A factorial design can separate tool and training effects."],
            "remaining_uncertainty": "The size of either causal effect remains unknown.",
            "revised_position": "The 18 percent difference cannot be assigned to the tool.",
            "prior_confidence": 0.75,
            "evidence_force": "strong",
            "posterior_confidence": 0.55,
            "what_changed": "The claim was narrowed from causal to associational.",
            "epistemic_marker": "open_uncertainty",
        },
        "reconstruction": {
            "stronger_position": (
                "The observation motivates a causal study but does not estimate "
                "the tool effect."
            ),
            "integrated_critiques": ["Account for selection and hold training constant."],
            "remaining_weaknesses": ["No pre-treatment outcome history is available."],
            "epistemic_marker": "reasonable_hypothesis",
        },
        "synthesis": synthesis,
        "move_score": score,
        "section_score": score,
    }


def _wire(content: Mapping[str, Any], confidence: float = 0.5) -> str:
    return json.dumps({"content": dict(content), "confidence": confidence})


def _resolve(schema: Mapping[str, Any], node: Mapping[str, Any]) -> Mapping[str, Any]:
    current = node
    while "$ref" in current:
        ref = current["$ref"]
        assert isinstance(ref, str) and ref.startswith("#/")
        resolved: Any = schema
        for part in ref[2:].split("/"):
            resolved = resolved[part]
        assert isinstance(resolved, Mapping)
        current = resolved
    return current


def _content_variants(schema: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    content = _resolve(schema, schema["properties"]["content"])
    any_of = content.get("anyOf")
    if isinstance(any_of, list):
        return tuple(_resolve(schema, item) for item in any_of)
    return (content,)


def test_full_offline_parity_gate_and_task_coverage() -> None:
    assert_ced_structured_schema_parity_v1()
    assert SUPPORTED_CED_TASK_KINDS_V1 == {
        TaskKind.SOCRATIC_QUESTION,
        TaskKind.INITIAL_RESPONSE,
        TaskKind.ELENCHUS_OBJECTION,
        TaskKind.REFLECTION_REVISION,
        TaskKind.RECONSTRUCTION_PROPOSAL,
        TaskKind.SYNTHESIS_DRAFT,
        TaskKind.MOVE_SCORE,
        TaskKind.SECTION_SCORE,
        TaskKind.COUNCIL_RATIFICATION,
        TaskKind.OBJECTION_VERIFICATION,
    }
    assert {task.task_kind for task in _tasks().values()} == set(
        SUPPORTED_CED_TASK_KINDS_V1
    )


def test_every_schema_has_a_closed_exact_envelope_and_nested_marker_policy() -> None:
    for task in _tasks().values():
        wrapper = ced_structured_response_format_v1(task)
        assert wrapper["type"] == "json_schema"
        assert wrapper["json_schema"]["strict"] is True
        schema = wrapper["json_schema"]["schema"]
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == {"content", "confidence"}
        assert set(schema["required"]) == set(schema["properties"])
        assert "epistemic_marker" not in schema["properties"]

        for content in _content_variants(schema):
            assert content["additionalProperties"] is False
            assert set(content["required"]) == set(content["properties"])
            assert (
                "epistemic_marker" in content["properties"]
            ) is marker_is_contracted(task.task_kind)


def test_schema_names_and_digests_are_stable_and_role_specific() -> None:
    tasks = _tasks()
    expected = {
        "opening": "ced_socratic_opening_move_v1",
        "followup": "ced_socratic_followup_move_v1",
        "initial_critic": "ced_initial_critic_move_v1",
        "initial_empiricist": "ced_initial_empiricist_move_v1",
        "initial_synthesizer": "ced_initial_synthesizer_move_v1",
        "elenchus_critic": "ced_elenchus_critic_move_v1",
        "elenchus_empiricist": "ced_elenchus_empiricist_move_v1",
        "reflection": "ced_reflection_move_v1",
        "reconstruction": "ced_reconstruction_move_v1",
        "synthesis": "ced_synthesis_move_v1",
        "move_score": "ced_move_score_v1",
        "section_score": "ced_section_score_v1",
        "ratification": "ced_council_ratification_v1",
        "verification": "ced_objection_verification_v1",
    }
    assert {name: ced_structured_schema_name_v1(task)
            for name, task in tasks.items()} == expected
    digests = {
        name: ced_structured_schema_sha256_v1(task)
        for name, task in tasks.items()
    }
    assert all(len(digest) == 64 for digest in digests.values())
    assert len(set(digests.values())) == len(digests)


def test_socratic_schema_enums_are_existing_ced_enums() -> None:
    tasks = _tasks()
    opening_schema = ced_structured_response_format_v1(
        tasks["opening"]
    )["json_schema"]["schema"]
    opening = next(iter(_content_variants(opening_schema)))
    operator = _resolve(opening_schema, opening["properties"]["operator"])
    marker = _resolve(opening_schema, opening["properties"]["epistemic_marker"])
    assert set(operator["enum"]) == {item.value for item in MaieuticOperator}
    assert set(marker["enum"]) == {item.value for item in EpistemicMarker}

    followup_schema = ced_structured_response_format_v1(
        tasks["followup"]
    )["json_schema"]["schema"]
    followup = next(iter(_content_variants(followup_schema)))
    inquiry = _resolve(followup_schema, followup["properties"]["inquiry_state"])
    grounding_array = followup["properties"]["grounded_in"]
    grounding = _resolve(followup_schema, grounding_array["items"])
    ref_type = _resolve(followup_schema, grounding["properties"]["ref_type"])
    assert set(inquiry["enum"]) == {item.value for item in InquiryState}
    assert set(ref_type["enum"]) == {item.value for item in GroundingRefType}
    assert followup["properties"]["introduces_new_proposition"]["enum"] == [False]


def test_role_payload_fields_match_repository_native_templates_and_directives() -> None:
    tasks = _tasks()
    template_fields = {
        role: set(FakeProvider._TEMPLATES[role.value]) - {"confidence"}
        for role in (
            AgentRole.ELENCHUS_CRITIC,
            AgentRole.EMPIRICIST,
            AgentRole.SYNTHESIZER,
            AgentRole.MAIEUTIC_RECONSTRUCTOR,
        )
    }

    for name, role in (
        ("initial_critic", AgentRole.ELENCHUS_CRITIC),
        ("initial_empiricist", AgentRole.EMPIRICIST),
        ("initial_synthesizer", AgentRole.SYNTHESIZER),
    ):
        schema = ced_structured_response_format_v1(tasks[name])["json_schema"]["schema"]
        content = next(iter(_content_variants(schema)))
        assert set(content["properties"]) == template_fields[role] | {
            "commitments",
            "epistemic_marker",
        }
    assert '"commitments"' in COMMITMENT_EMISSION_DIRECTIVE

    for name, role in (
        ("elenchus_critic", AgentRole.ELENCHUS_CRITIC),
        ("elenchus_empiricist", AgentRole.EMPIRICIST),
    ):
        schema = ced_structured_response_format_v1(tasks[name])["json_schema"]["schema"]
        content = next(iter(_content_variants(schema)))
        assert set(content["properties"]) == template_fields[role] | {
            "target_section",
            "epistemic_marker",
        }
    assert '"target_section"' in ELENCHUS_TARGET_DIRECTIVE

    schema = ced_structured_response_format_v1(
        tasks["reconstruction"]
    )["json_schema"]["schema"]
    content = next(iter(_content_variants(schema)))
    assert set(content["properties"]) == template_fields[
        AgentRole.MAIEUTIC_RECONSTRUCTOR
    ] | {"epistemic_marker"}


def test_exact_prompt_named_field_parity_for_remaining_contracts() -> None:
    tasks = _tasks()
    prompt_sources = {
        "opening": OPENING_CONTENT_DIRECTIVE + SOCRATIC_OPERATORS,
        "followup": SOCRATIC_FOLLOWUP_MANDATE,
        "reflection": REFLECTION_COMMITMENT_DIRECTIVE + BAYESIAN_UPDATE_DIRECTIVE,
        "synthesis": SYNTHESIS_CONTENT_DIRECTIVE,
        "move_score": SCORE_CONTENT_DIRECTIVE,
        "section_score": SCORE_CONTENT_DIRECTIVE,
    }
    for name, source in prompt_sources.items():
        schema = ced_structured_response_format_v1(tasks[name])["json_schema"]["schema"]
        content = next(iter(_content_variants(schema)))
        for field in content["properties"]:
            if field == "epistemic_marker":
                continue
            assert field in source, f"{name}.{field} is not prompt-named"

    synthesis_schema = ced_structured_response_format_v1(
        tasks["synthesis"]
    )["json_schema"]["schema"]
    synthesis = next(iter(_content_variants(synthesis_schema)))
    assert set(synthesis["properties"]) == {
        item.value for item in SECTION_ORDER
    } | {"epistemic_marker"}

    for name in ("move_score", "section_score"):
        score_schema = ced_structured_response_format_v1(
            tasks[name]
        )["json_schema"]["schema"]
        score = next(iter(_content_variants(score_schema)))
        assert set(score["properties"]) == set(ScoreBreakdown.model_fields)
        assert set(score["properties"]) == set(SCORE_WEIGHTS)


def test_ratification_and_verification_are_exact_closed_prompt_variants() -> None:
    tasks = _tasks()
    rat_schema = ced_structured_response_format_v1(
        tasks["ratification"]
    )["json_schema"]["schema"]
    rat_fields = {frozenset(item["properties"])
                  for item in _content_variants(rat_schema)}
    assert rat_fields == {
        frozenset({"verdict", "rationale"}),
        frozenset({"verdict", "rationale", "caveat"}),
        frozenset({
            "verdict",
            "rationale",
            "severity",
            "target_section",
            "required_fix",
        }),
    }
    for fields in rat_fields:
        for field in fields:
            assert field in RATIFICATION_CONTENT_DIRECTIVE

    verify_schema = ced_structured_response_format_v1(
        tasks["verification"]
    )["json_schema"]["schema"]
    verify_fields = {frozenset(item["properties"])
                     for item in _content_variants(verify_schema)}
    assert verify_fields == {
        frozenset({
            "objection_concerns_the_task",
            "cited_spans",
            "condition_tested",
            "objection_holds",
            "objection_targets",
            "rationale",
        }),
        frozenset({
            "objection_concerns_the_task",
            "cited_spans",
            "condition_tested",
            "objection_holds",
            "rationale",
        }),
    }
    for fields in verify_fields:
        for field in fields:
            assert field in OBJECTION_VERIFICATION_DIRECTIVE


def test_all_deliberative_samples_pass_provider_schema_and_unchanged_ced_parser() -> None:
    tasks = _tasks()
    for name, content in _sample_contents().items():
        task = tasks[name]
        raw = _wire(content)
        validate_ced_structured_output_v1(task, raw)
        move, status, error = parse_and_validate_move(
            raw,
            task,
            repair_attempts=0,
        )
        assert status is ProviderStatus.OK, (name, error)
        assert error is None
        assert move is not None
        assert (len(move.epistemic_markers) == 1) is marker_is_contracted(
            task.task_kind
        )


def test_socratic_outputs_reach_but_do_not_replace_ced_content_authority() -> None:
    tasks = _tasks()
    samples = _sample_contents()
    opening_raw = _wire(samples["opening"])
    opening_move, status, _ = parse_and_validate_move(opening_raw, tasks["opening"])
    assert status is ProviderStatus.OK and opening_move is not None
    opening = validate_socratic_content(opening_move.content, followup=False)
    assert opening.accepted is True
    assert opening.operator is MaieuticOperator.DISTINGUISH

    followup_raw = _wire(samples["followup"])
    followup_move, status, _ = parse_and_validate_move(followup_raw, tasks["followup"])
    assert status is ProviderStatus.OK and followup_move is not None
    followup = validate_socratic_content(
        followup_move.content,
        followup=True,
        public_ids={"commitment": {"c1"}},
    )
    assert followup.accepted is True
    assert followup.grounded_in == (("commitment", "c1"),)

    unresolved = validate_socratic_content(
        followup_move.content,
        followup=True,
        public_ids={"commitment": set()},
    )
    assert unresolved.accepted is False
    assert "unresolved reference" in unresolved.reason


def test_commitment_and_reflection_payloads_feed_existing_append_only_readers() -> None:
    samples = _sample_contents()
    initial = commitments_from_move(
        "move_initial",
        0,
        samples["initial_synthesizer"],
    )
    assert [item.claim for item in initial] == [
        "Randomization or a credible quasi-experiment is needed."
    ]
    known = {"c1"}
    events = commitment_events_from_reflection(
        "move_reflection",
        1,
        samples["reflection"],
        known,
    )
    assert any(
        item.claim == "A factorial design can separate tool and training effects."
        for item in events
    )
    assert any(item.target_commitment_id == "c1" for item in events)


def test_synthesis_and_score_payloads_feed_frozen_ced_types() -> None:
    samples = _sample_contents()
    synthesis = samples["synthesis"]
    draft = SectionDraft(
        draft_id="draft_offline",
        session_id="offline",
        author_agent_id="agent_a",
        move_id="move_synthesis",
        **{section.value: synthesis[section.value] for section in SECTION_ORDER},
    )
    assert all(draft.section_text(section).strip() for section in SECTION_ORDER)
    for name in ("move_score", "section_score"):
        breakdown = ScoreBreakdown(**samples[name])
        assert breakdown.weighted_overall() == pytest.approx(7.0)


def _orchestrator() -> CEDOrchestrator:
    provider = FakeProvider()
    agents = [
        SocraticAgent("agent_a", provider),
        SocraticAgent("agent_b", provider),
    ]
    return CEDOrchestrator(agents, provider)


@pytest.mark.parametrize(
    ("content", "expected", "is_block"),
    [
        ({"verdict": "accept", "rationale": "The answer meets the bar."},
         CouncilVerdict.ACCEPT, False),
        ({
            "verdict": "accept_with_caveat",
            "rationale": "The scope is narrower than the wording.",
            "caveat": "Do not generalize beyond applicant teams.",
        }, CouncilVerdict.ACCEPT_WITH_CAVEAT, False),
        ({
            "verdict": "blocking_objection",
            "rationale": "The core answer assigns the whole effect to the tool.",
            "severity": "critical",
            "target_section": "core_answer",
            "required_fix": "Separate selection and training explanations.",
        }, CouncilVerdict.BLOCKING_OBJECTION, True),
    ],
)
def test_ratification_variants_pass_provider_schema_then_ced_verdict_parser(
    content: Dict[str, Any], expected: CouncilVerdict, is_block: bool,
) -> None:
    task = _tasks()["ratification"]
    raw = _wire(content, 0.8)
    validate_ced_structured_output_v1(task, raw)
    move, status, error = parse_and_validate_move(raw, task, repair_attempts=0)
    assert status is ProviderStatus.OK and error is None and move is not None
    response = ProviderResponse(
        provider_id="offline_voter",
        agent_id=task.agent_id,
        status=ProviderStatus.OK,
        parsed_move=move,
    )
    verdict = _orchestrator()._parse_verdict(response, task)
    assert verdict is not None
    assert verdict.verdict is expected
    assert verdict.is_schema_valid_critical_block() is is_block


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ({
            "objection_concerns_the_task": True,
            "cited_spans": ["Managers voluntarily apply"],
            "condition_tested": "whether tool receipt was randomly assigned",
            "objection_holds": True,
            "objection_targets": "justification",
            "rationale": "Voluntary application permits selection bias.",
        }, VerificationResult.VERIFIED),
        ({
            "objection_concerns_the_task": False,
            "cited_spans": [],
            "condition_tested": "whether the objection concerns the task",
            "objection_holds": None,
            "rationale": "It criticizes an earlier derivation, not the task text.",
        }, VerificationResult.NOT_APPLICABLE),
    ],
)
def test_verification_variants_pass_provider_schema_then_existing_parser(
    content: Dict[str, Any], expected: VerificationResult,
) -> None:
    task = _tasks()["verification"]
    raw = _wire(content, 0.8)
    validate_ced_structured_output_v1(task, raw)
    move, status, error = parse_and_validate_move(raw, task, repair_attempts=0)
    assert status is ProviderStatus.OK and error is None and move is not None
    record = parse_verification_response(
        move.content,
        task_text="Managers voluntarily apply for the tool.",
        claim_id="claim_core",
        objection_id="obj_1",
        verifier_provider_id="offline_verifier",
        verifier_model_id="mock/offline",
    )
    assert record is not None
    assert record.result is expected


def test_provider_schema_and_ced_acceptance_remain_separate_measurements() -> None:
    task = _tasks()["opening"]
    extra = json.dumps({
        "content": _sample_contents()["opening"],
        "confidence": 0.5,
        "provider_extra": "not part of the contract",
    })
    with pytest.raises(ValidationError):
        validate_ced_structured_output_v1(task, extra)
    move, status, error = parse_and_validate_move(extra, task, repair_attempts=0)
    assert status is ProviderStatus.OK and error is None and move is not None

    whitespace = _sample_contents()["opening"] | {"question": "   "}
    with pytest.raises(ValidationError):
        validate_ced_structured_output_v1(task, _wire(whitespace))
    move, status, error = parse_and_validate_move(
        _wire(whitespace), task, repair_attempts=0
    )
    assert status is ProviderStatus.OK and error is None and move is not None
    assert validate_socratic_content(move.content, followup=False).accepted is False


def test_wrong_marker_nesting_and_evaluative_markers_fail_closed() -> None:
    opening = _tasks()["opening"]
    misplaced = {
        "content": {
            "question": "Which distinction matters?",
            "operator": "distinguish",
        },
        "confidence": 0.5,
        "epistemic_marker": "open_uncertainty",
    }
    raw = json.dumps(misplaced)
    with pytest.raises(ValidationError):
        validate_ced_structured_output_v1(opening, raw)
    move, status, error = parse_and_validate_move(raw, opening, repair_attempts=0)
    assert move is None
    assert status is ProviderStatus.SCHEMA_ERROR
    assert error == "schema validation failed: epistemic_marker is required"

    score = _tasks()["move_score"]
    score_content = _sample_contents()["move_score"] | {
        "epistemic_marker": "reasonable_hypothesis"
    }
    raw = _wire(score_content)
    with pytest.raises(ValidationError):
        validate_ced_structured_output_v1(score, raw)
    move, status, error = parse_and_validate_move(raw, score, repair_attempts=0)
    assert move is None
    assert status is ProviderStatus.SCHEMA_ERROR
    assert "not permitted" in str(error)


def test_factory_rejects_non_native_phase_role_and_task_combinations() -> None:
    bad_tasks = (
        _task(TaskKind.SOCRATIC_QUESTION, DialogPhase.OPENING, AgentRole.EMPIRICIST),
        _task(TaskKind.INITIAL_RESPONSE, DialogPhase.INITIAL_RESPONSE,
              AgentRole.MAIEUTIC_RECONSTRUCTOR),
        _task(TaskKind.ELENCHUS_OBJECTION, DialogPhase.REFLECTION,
              AgentRole.ELENCHUS_CRITIC),
        _task(TaskKind.MOVE_SCORE, DialogPhase.RATIFICATION,
              AgentRole.FINAL_EVALUATOR),
        _task(TaskKind.TREE_REVISION, DialogPhase.SYNTHESIS,
              AgentRole.SYNTHESIZER),
    )
    for task in bad_tasks:
        with pytest.raises(ContractValidationError):
            ced_structured_response_format_v1(task)

    no_kind = _task(
        TaskKind.SYNTHESIS_DRAFT,
        DialogPhase.SYNTHESIS,
        AgentRole.SYNTHESIZER,
    ).model_copy(update={"task_kind": None})
    with pytest.raises(ContractValidationError, match="task_kind is required"):
        ced_structured_response_format_v1(no_kind)


def test_schema_validation_is_strict_and_never_repairs_or_coerces() -> None:
    task = _tasks()["opening"]
    content = _sample_contents()["opening"]
    with pytest.raises(ValidationError):
        validate_ced_structured_output_v1(
            task,
            json.dumps({"content": content, "confidence": "0.5"}),
        )

    followup = _tasks()["followup"]
    invalid = _sample_contents()["followup"] | {
        "introduces_new_proposition": True
    }
    with pytest.raises(ValidationError):
        validate_ced_structured_output_v1(followup, _wire(invalid))
