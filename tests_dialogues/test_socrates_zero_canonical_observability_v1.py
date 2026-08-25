"""Phase 6 science gates for opt-in canonical SearchState observability v1.

All fixtures use the real CED SessionState and governing Hybrid record models.
No provider, model, network, benchmark outcome, or future reward is consulted.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from backend.dialogues import ced_search_projection
from backend.dialogues.ced_search_observability_v1 import (
    SEARCH_STATE_V1_PROJECTION_VERSION,
    SEARCH_STATE_V1_SCHEMA_VERSION,
    CanonicalClaimAssessmentView,
    CanonicalContradictionView,
    CanonicalEvidenceView,
    CanonicalObjectionView,
    CanonicalVerificationView,
    SearchStateV1,
)
from backend.dialogues.ced_search_projection_v1 import project_search_state_v1
from backend.dialogues.hybrid_epistemic import (
    ClaimRecord,
    ContradictionRecord,
    ContradictionState,
    EvidenceRecord,
    EvidenceSourceType,
    EvidenceStance,
    HybridEpistemicState,
    MalformedVerification,
    ObjectionRecord,
    ObjectionScope,
    ObjectionState,
    SupportState,
    VerificationClass,
    VerificationMethod,
    VerificationResult,
    external_evidence_required,
    verify_task_internal,
)
from backend.dialogues.models import (
    EpistemicMarker,
    MicroScore,
    ScoreBreakdown,
)
from backend.dialogues.socrates_zero import BudgetUsage, ContractValidationError
from tests_dialogues.test_socrates_zero_projection import (
    QUESTION,
    _budget,
    _project as _project_v0,
    _source_fixture,
)


_ARTIFACT_SHA256 = (
    "21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c"
)


def _project_v1(source=None) -> SearchStateV1:
    state, task, commitments, aporia, hybrid = source or _source_fixture()
    return project_search_state_v1(
        state,
        task,
        budget=_budget(),
        budget_usage=BudgetUsage(nodes=1, max_depth_observed=0),
        commitments=commitments,
        aporia_records=aporia,
        hybrid_state=hybrid,
    )


def _typed_payload(projected: SearchStateV1):
    return {
        name: [item.model_dump(mode="json") for item in getattr(projected, name)]
        for name in (
            "evidence",
            "verifications",
            "claim_assessments",
            "objections",
            "contradictions",
        )
    }


def _replace_hybrid(source, hybrid):
    changed = list(source)
    changed[4] = hybrid
    return tuple(changed)


def _check(*, claim_id="claim_a", objection_id=None, holds=True,
           provider_id=None, model_id=None):
    return verify_task_internal(
        claim_id=claim_id,
        objection_id=objection_id,
        task_text=QUESTION,
        cited_spans=(("Evidence A is supplied.", 0),),
        condition_tested="does the supplied evidence satisfy the tested condition?",
        holds=holds,
        rationale="bounded task-internal fixture check",
        verifier_provider_id=provider_id,
        verifier_model_id=model_id,
    )


def test_v1_has_explicit_separate_ids_and_keeps_v0_as_unchanged_base():
    projected = _project_v1()

    assert SEARCH_STATE_V1_SCHEMA_VERSION == "socrates.zero.search-state/v1"
    assert SEARCH_STATE_V1_PROJECTION_VERSION == "ced-search-state-projection/v1"
    assert ced_search_projection.SEARCH_STATE_PROJECTION_VERSION \
        == "ced-search-state-projection/v0"
    assert projected.schema_version == SEARCH_STATE_V1_SCHEMA_VERSION
    assert projected.projection_version == SEARCH_STATE_V1_PROJECTION_VERSION
    assert projected.state_id.startswith("szstatev1_")
    assert projected.base_state == _project_v0()
    assert projected.base_state.schema_version == "socrates.zero.search-contracts/v0"
    assert "project_search_state_v1" not in ced_search_projection.__all__


def test_v1_projects_only_typed_canonical_fields_and_governing_assessment():
    source = _source_fixture()
    projected = _project_v1(source)
    assessment = source[4].assess_claim("claim_a")

    assert [(item.source_record_id, item.stance, item.source_type)
            for item in projected.evidence] == [(
                "evidence_a",
                EvidenceStance.SUPPORTING,
                EvidenceSourceType.SUPPLIED_TASK_MATERIAL,
            )]
    assert [(item.source_record_id, item.state) for item in projected.objections] \
        == [("objection_a", ObjectionState.RAISED)]
    observed = projected.claim_assessments[0]
    assert observed.claim_id == assessment.claim_id
    assert observed.support_state is assessment.support_state
    assert observed.basis_record_ids == tuple(assessment.basis_record_ids)
    assert observed.unresolved_record_ids == tuple(assessment.unresolved_record_ids)
    assert observed.eligible_for_assembly is assessment.eligible_for_assembly

    forbidden = {
        "text", "content", "rationale", "confidence", "score", "consensus",
        "epistemic_marker", "provider_id", "model_id", "quality",
    }
    for model in (
        CanonicalEvidenceView,
        CanonicalVerificationView,
        CanonicalClaimAssessmentView,
        CanonicalObjectionView,
        CanonicalContradictionView,
    ):
        assert forbidden.isdisjoint(model.model_fields)


def test_real_v0_alias_is_separated_by_canonical_dismissed_contradiction():
    without_record = _source_fixture()
    without_record[4].add_claim(ClaimRecord(claim_id="claim_b", text="Claim B"))
    with_dismissed = deepcopy(without_record)
    with_dismissed[4].add_contradiction(ContradictionRecord(
        contradiction_id="contradiction_ab",
        claim_id_a="claim_a",
        claim_id_b="claim_b",
    ))
    with_dismissed[4].dismiss_contradiction(
        "contradiction_ab", "canonical checker found no contradiction"
    )

    v0_without = _project_v0(without_record)
    v0_dismissed = _project_v0(with_dismissed)
    v1_without = _project_v1(without_record)
    v1_dismissed = _project_v1(with_dismissed)

    assert v0_without == v0_dismissed
    assert v0_without.state_id == v0_dismissed.state_id
    assert v1_without.base_state == v1_dismissed.base_state
    assert v1_without.contradictions == ()
    assert [(item.source_record_id, item.state)
            for item in v1_dismissed.contradictions] == [
                ("contradiction_ab", ContradictionState.DISMISSED)
            ]
    assert v1_without.state_id != v1_dismissed.state_id


def test_verification_success_and_failure_are_structured_not_opaque_in_v1():
    successful = _source_fixture()
    failed = deepcopy(successful)
    successful[4].add_verification(_check(holds=True))
    failed[4].add_verification(_check(holds=False))

    v0_success = _project_v0(successful)
    v0_failure = _project_v0(failed)
    assert not hasattr(v0_success.verification_results[0], "result")
    assert not hasattr(v0_failure.verification_results[0], "result")
    assert v0_success.state_id != v0_failure.state_id  # opaque digest only

    v1_success = _project_v1(successful)
    v1_failure = _project_v1(failed)
    assert v1_success.verifications[0].result is VerificationResult.VERIFIED
    assert v1_failure.verifications[0].result is VerificationResult.FALSIFIED
    assert v1_success.verifications[0].semantic_digest \
        != v1_failure.verifications[0].semantic_digest


def test_v0_semantic_alias_hides_governing_supported_vs_unsupported_assessment():
    template = _source_fixture()
    deterministic = HybridEpistemicState(template[0].session_id, QUESTION)
    deterministic.add_claim(ClaimRecord(
        claim_id="claim_a",
        text="Claim A",
        verification_class=VerificationClass.TASK_INTERNAL,
    ))
    deterministic.add_verification(_check(holds=True))
    model_produced = HybridEpistemicState(template[0].session_id, QUESTION)
    model_produced.add_claim(ClaimRecord(
        claim_id="claim_a",
        text="Claim A",
        verification_class=VerificationClass.TASK_INTERNAL,
    ))
    model_produced.add_verification(_check(
        holds=True, provider_id="model-route", model_id=None
    ))
    deterministic_source = _replace_hybrid(template, deterministic)
    model_source = _replace_hybrid(template, model_produced)

    deterministic_v0 = _project_v0(deterministic_source)
    model_v0 = _project_v0(model_source)
    assert deterministic_v0.state_id == model_v0.state_id
    assert deterministic_v0.identity_payload() == model_v0.identity_payload()
    assert not hasattr(deterministic_v0, "claim_assessments")
    assert deterministic_v0.verification_results[0].semantic_digest \
        == model_v0.verification_results[0].semantic_digest

    deterministic_v1 = _project_v1(deterministic_source)
    model_v1 = _project_v1(model_source)
    assert deterministic_v1.verifications == model_v1.verifications
    assert deterministic_v1.claim_assessments[0].support_state \
        is SupportState.SUPPORTED
    assert model_v1.claim_assessments[0].support_state \
        is SupportState.UNSUPPORTED
    assert deterministic_v1.state_id != model_v1.state_id


def test_supported_and_required_unverified_are_governing_typed_states_in_v1():
    template = _source_fixture()
    supported = HybridEpistemicState(template[0].session_id, QUESTION)
    supported.add_claim(ClaimRecord(
        claim_id="claim_a",
        text="Claim A",
        verification_class=VerificationClass.TASK_INTERNAL,
    ))
    supported.add_evidence(EvidenceRecord(
        evidence_id="evidence_a",
        claim_id="claim_a",
        stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.DETERMINISTIC_COMPUTATION,
        source_identity="canonical-checker",
    ))
    required = HybridEpistemicState(template[0].session_id, QUESTION)
    required.add_claim(ClaimRecord(
        claim_id="claim_a",
        text="Claim A",
        verification_class=VerificationClass.EXTERNAL_EVIDENCE,
    ))
    required.add_verification(external_evidence_required(
        "claim_a", "the supplied task contains no governing external source"
    ))

    supported_v1 = _project_v1(_replace_hybrid(template, supported))
    required_v1 = _project_v1(_replace_hybrid(template, required))

    assert not hasattr(supported_v1.base_state, "claim_assessments")
    assert supported_v1.claim_assessments[0].support_state \
        is SupportState.SUPPORTED
    assert required_v1.claim_assessments[0].support_state \
        is SupportState.EXTERNAL_EVIDENCE_REQUIRED
    assert required_v1.verifications[0].result \
        is VerificationResult.EXTERNAL_EVIDENCE_REQUIRED


@pytest.mark.parametrize(
    "holds,terminal_state,expected_result",
    [
        (True, ObjectionState.VALIDATED, VerificationResult.VERIFIED),
        (False, ObjectionState.REJECTED, VerificationResult.FALSIFIED),
    ],
)
def test_resolved_objection_lifecycle_is_preserved_with_its_verification(
    holds, terminal_state, expected_result
):
    source = _source_fixture()
    hybrid = source[4]
    hybrid.transition_objection(
        "objection_a", ObjectionState.PENDING_VERIFICATION
    )
    check = hybrid.add_verification(_check(
        objection_id="objection_a", holds=holds
    ))
    hybrid.transition_objection(
        "objection_a", terminal_state, verification_id=check.verification_id
    )

    v0 = _project_v0(source)
    v1 = _project_v1(source)
    assert "objection_a" not in {
        item.artifact_id for item in v0.unresolved_questions
    }
    assert v1.objections[0].state is terminal_state
    assert v1.objections[0].verification_id == check.verification_id
    assert v1.verifications[0].result is expected_result


def test_no_invented_verification_resolution_question_or_abstention_state():
    source = _source_fixture()
    hybrid = HybridEpistemicState(source[0].session_id, QUESTION)
    hybrid.add_claim(ClaimRecord(claim_id="claim_a", text="A bare claim"))
    projected = _project_v1(_replace_hybrid(source, hybrid))

    assert projected.evidence == ()
    assert projected.verifications == ()
    assert projected.objections == ()
    assert projected.contradictions == ()
    assert projected.claim_assessments[0].support_state is SupportState.UNSUPPORTED
    assert projected.claim_assessments[0].basis_record_ids == ()
    assert projected.claim_assessments[0].falsifying_record_ids == ()
    assert projected.claim_assessments[0].unresolved_record_ids == ()
    assert "question_resolutions" not in SearchStateV1.model_fields
    assert "abstention_state" not in SearchStateV1.model_fields


def test_forbidden_scores_markers_provider_identity_and_prose_do_not_change_typed_views():
    original = _source_fixture()
    original[4].add_verification(_check(
        holds=True, provider_id="route-a", model_id="vendor/model-a"
    ))
    changed = deepcopy(original)
    state = changed[0]
    state.moves[0].content["question"] = "Stylistically different wording?"
    state.moves[0].confidence = 0.01
    state.moves[0].epistemic_markers = [EpistemicMarker.ESTABLISHED_FACT]
    score = ScoreBreakdown(
        epistemic_value=10,
        logical_rigor=10,
        factual_grounding=10,
        constructive_impact=10,
        intellectual_honesty=10,
        clarity_precision=10,
        grounded_creativity=10,
    )
    author = state.moves[0].agent_id
    voters = [item for item in state.agent_states if item != author]
    state.micro_scores.extend(MicroScore(
        session_id=state.session_id,
        output_id=state.moves[0].move_id,
        phase=state.moves[0].phase,
        author_agent_id=author,
        voter_agent_id=voter,
        score_breakdown=score,
        confidence=0.99,
        justification="unanimous stylistic approval",
    ) for voter in voters)

    hybrid = changed[4]
    claim = hybrid.claims["claim_a"]
    hybrid.claims["claim_a"] = claim.model_copy(update={
        "text": "Stylistically different claim prose.",
        "author_agent_id": "different-author",
        "provider_id": "different-claim-route",
    })
    evidence = hybrid.evidence["evidence_a"]
    hybrid.evidence["evidence_a"] = evidence.model_copy(update={
        "source_identity": "different-canonical-label",
        "content": "Different evidence prose with the same typed record status.",
        "citation": "different display citation",
        "provenance": "different audit prose",
    })
    objection = hybrid.objections["objection_a"]
    hybrid.objections["objection_a"] = objection.model_copy(update={
        "text": "Different objection prose.",
        "raised_by": "different-seat",
        "raised_by_model_id": "vendor/different-objector",
    })
    verification_id = next(iter(hybrid.verifications))
    verification = hybrid.verifications[verification_id]
    hybrid.verifications[verification_id] = verification.model_copy(update={
        "rationale": "Different verifier prose.",
        "scope": "different display scope",
        "limitations": "different limitations prose",
        "provenance": "different verification audit prose",
        "verifier_provider_id": "route-b",
        "verifier_model_id": "vendor/model-b",
    })

    first = _project_v1(original)
    second = _project_v1(changed)
    assert _typed_payload(first) == _typed_payload(second)
    assert first.base_state.state_id != second.base_state.state_id


def test_projection_has_no_temporal_leakage_from_later_verifier_outcomes():
    future_success = _source_fixture()
    future_failure = deepcopy(future_success)
    prefix_success = _project_v1(future_success)
    prefix_failure = _project_v1(future_failure)

    assert prefix_success == prefix_failure
    frozen_prefix = prefix_success.model_dump(mode="json")

    future_success[4].add_verification(_check(holds=True))
    future_failure[4].add_verification(_check(holds=False))
    after_success = _project_v1(future_success)
    after_failure = _project_v1(future_failure)

    assert after_success.verifications[0].result is VerificationResult.VERIFIED
    assert after_failure.verifications[0].result is VerificationResult.FALSIFIED
    assert after_success.state_id != after_failure.state_id
    assert prefix_success.model_dump(mode="json") == frozen_prefix
    assert prefix_success.verifications == prefix_failure.verifications == ()


def test_v1_projection_is_pure_over_ced_hybrid_and_socratic_sources():
    source = _source_fixture()
    state, _task, commitments, aporia, hybrid = source
    before_state = state.model_dump(mode="json")
    before_commitments = [item.to_dict() for item in commitments]
    before_aporia = [item.to_dict() for item in aporia]
    before_hybrid = deepcopy(hybrid.__dict__)

    _project_v1(source)

    assert state.model_dump(mode="json") == before_state
    assert [item.to_dict() for item in commitments] == before_commitments
    assert [item.to_dict() for item in aporia] == before_aporia
    assert hybrid.__dict__ == before_hybrid


def test_v1_identity_and_collection_order_ignore_mapping_insertion_order():
    source = _source_fixture()
    hybrid = source[4]
    hybrid.add_claim(ClaimRecord(claim_id="claim_b", text="Claim B"))
    hybrid.add_evidence(EvidenceRecord(
        evidence_id="evidence_b",
        claim_id="claim_b",
        stance=EvidenceStance.WEAK,
        source_type=EvidenceSourceType.HUMAN_PROVIDED,
        source_identity="operator",
    ))
    hybrid.add_objection(ObjectionRecord(
        objection_id="objection_b",
        target_claim_id="claim_b",
        text="A second canonical objection",
    ))
    hybrid.add_verification(_check(holds=True))
    hybrid.add_contradiction(ContradictionRecord(
        contradiction_id="contradiction_ab",
        claim_id_a="claim_a",
        claim_id_b="claim_b",
    ))
    first = _project_v1(source)
    reordered = deepcopy(source)
    for name in (
        "claims", "evidence", "objections", "verifications", "contradictions"
    ):
        current = getattr(reordered[4], name)
        setattr(reordered[4], name, dict(reversed(tuple(current.items()))))
    second = _project_v1(reordered)

    assert first == second
    assert first.state_id == second.state_id
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_every_v1_observation_and_assessment_reference_has_canonical_provenance():
    source = _source_fixture()
    hybrid = source[4]
    hybrid.add_verification(_check(holds=True))
    hybrid.add_claim(ClaimRecord(claim_id="claim_b", text="Claim B"))
    hybrid.add_contradiction(ContradictionRecord(
        contradiction_id="contradiction_ab",
        claim_id_a="claim_a",
        claim_id_b="claim_b",
    ))
    projected = _project_v1(source)

    assert {item.source_record_id for item in projected.evidence} \
        == set(hybrid.evidence)
    assert {item.source_record_id for item in projected.verifications} \
        == set(hybrid.verifications)
    assert {item.source_record_id for item in projected.objections} \
        == set(hybrid.objections)
    assert {item.source_record_id for item in projected.contradictions} \
        == set(hybrid.contradictions)
    assert {item.claim_id for item in projected.claim_assessments} \
        == set(hybrid.claims)
    canonical_assessments = hybrid.assess_all()
    for item in projected.claim_assessments:
        canonical = canonical_assessments[item.claim_id]
        assert item.support_state is canonical.support_state
        assert item.basis_record_ids == tuple(canonical.basis_record_ids)
        assert item.falsifying_record_ids == tuple(canonical.falsifying_record_ids)
        assert item.unresolved_record_ids == tuple(canonical.unresolved_record_ids)
    for collection in _typed_payload(projected).values():
        assert all(len(item["semantic_digest"]) == 64 for item in collection)


def test_v1_fails_closed_on_duplicate_dangling_and_misindexed_sources():
    projected = _project_v1()
    with pytest.raises(ValueError, match="duplicate"):
        SearchStateV1(
            base_state=projected.base_state,
            evidence=(projected.evidence[0], projected.evidence[0]),
            claim_assessments=projected.claim_assessments,
            objections=projected.objections,
        )

    dangling = CanonicalObjectionView(
        source_record_id="orphan_objection",
        target_claim_id="claim_a",
        state=ObjectionState.REJECTED,
        scope=ObjectionScope.JUSTIFICATION,
        target_provenance=projected.objections[0].target_provenance,
        verification_id="missing_verification",
    )
    with pytest.raises(ValueError, match="dangling verification"):
        SearchStateV1(
            base_state=projected.base_state,
            evidence=projected.evidence,
            claim_assessments=projected.claim_assessments,
            objections=(dangling,),
        )

    source = _source_fixture()
    record = source[4].evidence.pop("evidence_a")
    source[4].evidence["wrong-index-key"] = record
    with pytest.raises(ContractValidationError, match="index key"):
        _project_v1(source)


def test_v1_revalidates_mutated_verification_records_instead_of_omitting_them():
    source = _source_fixture()
    record = source[4].add_verification(_check(holds=True))
    source[4].verifications[record.verification_id] = record.model_copy(update={
        "method": VerificationMethod.EXTERNAL_SOURCE,
    })

    with pytest.raises(MalformedVerification, match="not legal"):
        _project_v1(source)


def test_phase5_artifact_sha256_remains_frozen():
    path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "branches"
        / "feature-socrates-zero-search-v0"
        / "artifacts"
        / "socrateszero_search_kernel_benchmark_v0.json"
    )
    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(normalized).hexdigest() == _ARTIFACT_SHA256
