"""What an objection is about, and what follows from not knowing.

Every objection used to land on `targets[0]` — the first assembled section,
whatever it was actually about. The live five-analyst run showed the price: a
deterministic receipt established `final_verdict`, and an uncorroborated
objection filed by default against `core_answer` held the entire release at
unresolved. The objection had no established relationship to the thing it
suppressed.

A target now comes from provenance or it does not exist. UNMAPPED is a real
outcome, visible in the audit, attached to nothing and deciding nothing — which
is strictly better than a confident guess, because the guess is what lets an
objection destroy a conclusion it was never about.

All offline: scripted providers, no network, no key.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_epistemic import (
    ADMISSIBLE_EVIDENCE_SOURCES,
    UNMAPPED_TARGET,
    ClaimRecord,
    EvidenceRecord,
    EvidenceSourceType,
    EvidenceStance,
    HybridEpistemicState,
    ObjectionRecord,
    ObjectionScope,
    ObjectionState,
    ObjectionTargetProvenance,
    ReleaseDecision,
    SupportState,
    VerificationClass,
    freeze_release,
    verify_task_internal,
)
from backend.dialogues.models import (
    ObjectionSeverity, RatificationDecision, RatificationVote, SectionName,
    ShadowScoringMode, TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.task_checker import evaluate_candidate, receipt_support

TASK = ("Four people — Anna, Ben, Clara, and David — must present one at a time. "
        "Anna presents before Ben. Clara presents immediately before David. "
        "Ben is not last.")
ANSWER = "The unique order is Anna, Ben, Clara, David."


def _state():
    """final_verdict carries the answer; core_answer is an ancillary section."""
    state = HybridEpistemicState("target", TASK)
    state.add_claim(ClaimRecord(claim_id="final_verdict", text=ANSWER,
                                section="final_verdict",
                                verification_class=VerificationClass.TASK_INTERNAL))
    state.add_claim(ClaimRecord(claim_id="core_answer",
                                text="A discussion of how the constraints interact.",
                                section="core_answer",
                                verification_class=VerificationClass.TASK_INTERNAL))
    state.add_evidence(receipt_support(evaluate_candidate(TASK, ANSWER),
                                       "final_verdict"))
    return state


def _objection(objection_id, target, *, scope=ObjectionScope.JUSTIFICATION,
               state=ObjectionState.RAISED,
               provenance=ObjectionTargetProvenance.DECLARED_IDENTIFIER):
    return ObjectionRecord(objection_id=objection_id, target_claim_id=target,
                           text="a doubt", scope=scope, state=state,
                           target_provenance=provenance)


def _release(state):
    return freeze_release(state, assembled_claim_ids=["core_answer", "final_verdict"],
                          quality_mean=8.0, legacy_epistemic_status="well_supported")


# ══ 1. an unrelated objection does not erase established support ═════════════

def test_1_an_objection_on_another_section_leaves_the_verdict_supported():
    """The live run's failure, inverted.

    A doubt about core_answer is a doubt about core_answer. The deterministic
    receipt on final_verdict is untouched by it, and the release says so.
    """
    state = _state()
    state.add_objection(_objection("o", "core_answer"))

    assert state.assess_claim("final_verdict").support_state is SupportState.SUPPORTED
    assert state.assess_claim("core_answer").support_state is SupportState.UNRESOLVED

    release = _release(state)
    assert release.release_decision is ReleaseDecision.RELEASE_SUPPORTED
    assert release.basis_record_ids
    # Still visible: recorded, reported, and not decisive.
    assert release.unresolved_record_ids == ["o"]
    assert release.claim_states["core_answer"] == SupportState.UNRESOLVED.value


def test_1_an_unmapped_objection_leaves_the_verdict_supported():
    state = _state()
    state.add_objection(_objection(
        "o", UNMAPPED_TARGET, provenance=ObjectionTargetProvenance.UNMAPPED))
    release = _release(state)
    assert release.release_decision is ReleaseDecision.RELEASE_SUPPORTED
    assert state.objections["o"].is_mapped is False


# ══ 2. an objection on the conclusion still blocks ═══════════════════════════

def test_2_an_unresolved_objection_on_the_verdict_prevents_release_supported():
    state = _state()
    state.add_objection(_objection("o", "final_verdict"))
    assert state.assess_claim("final_verdict").support_state is SupportState.UNRESOLVED
    release = _release(state)
    assert release.release_decision is ReleaseDecision.RELEASE_UNRESOLVED
    # The basis is still reported; it simply did not carry the decision.
    assert release.basis_record_ids


def test_2_a_validated_conclusion_counterexample_still_falsifies():
    state = _state()
    state.add_objection(_objection(
        "o", "final_verdict", scope=ObjectionScope.CONCLUSION,
        state=ObjectionState.VALIDATED))
    assert state.assess_claim("final_verdict").support_state is SupportState.FALSIFIED
    assert _release(state).release_decision is ReleaseDecision.BLOCKED


# ══ 3. ratification target_section maps to exactly that section ══════════════

class _Blocking(ScriptedMockProvider):
    async def _produce_raw_text(self, task, agent_state) -> str:
        if task.task_kind is TaskKind.ELENCHUS_OBJECTION:
            return json.dumps({"content": {"critique": "unshown assumption",
                                           "target_section": "nuance"},
                               "confidence": 0.8})
        return await super()._produce_raw_text(task, agent_state)


def _session(session_id, seats=3):
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for i in range(seats):
        registry.register(_Blocking(f"seat{i}"))
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                          provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(TASK, session_id=session_id))
    return ced, final


def _by_provenance(core, provenance):
    return [o for o in core.objections.values()
            if o.target_provenance is provenance]


def test_3_a_ratification_vote_maps_to_the_section_it_names():
    ced, final = _session("rat_map")
    final.ratification_votes = [
        RatificationVote(voter_agent_id="agent_1",
                         decision=RatificationDecision.BLOCKING_OBJECTION,
                         severity=ObjectionSeverity.CRITICAL,
                         target_section=SectionName.BLIND_SPOTS,
                         reason="the blind spots section overstates the risk"),
    ]
    core = ced.project_governing_state(ced.get_session("rat_map"), final)
    mapped = _by_provenance(
        core, ObjectionTargetProvenance.RATIFICATION_TARGET_SECTION)
    assert len(mapped) == 1
    assert core.claims[mapped[0].target_claim_id].section == "blind_spots"


def test_3_a_ratification_vote_naming_no_section_is_unmapped():
    ced, final = _session("rat_none")
    final.ratification_votes = [
        RatificationVote(voter_agent_id="agent_1",
                         decision=RatificationDecision.BLOCKING_OBJECTION,
                         severity=ObjectionSeverity.CRITICAL,
                         reason="something is wrong somewhere"),
    ]
    core = ced.project_governing_state(ced.get_session("rat_none"), final)
    unmapped = [o for o in core.objections.values()
                if o.text == "something is wrong somewhere"]
    assert len(unmapped) == 1
    assert unmapped[0].target_claim_id == UNMAPPED_TARGET
    assert unmapped[0].target_provenance is ObjectionTargetProvenance.UNMAPPED


def test_3_a_declared_elenchus_target_maps_to_that_section():
    ced, final = _session("elen_map")
    core = ced.project_governing_state(ced.get_session("elen_map"), final)
    declared = _by_provenance(core, ObjectionTargetProvenance.DECLARED_IDENTIFIER)
    assert declared, "the mock declares nuance"
    for objection in declared:
        assert core.claims[objection.target_claim_id].section == "nuance"


# ══ 4. no target means UNMAPPED, never targets[0] ════════════════════════════

def test_4_an_undeclared_objection_is_unmapped_and_never_the_first_claim():
    """The locked rule. Absence of a target is not a reason to invent one."""
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for i in range(3):
        registry.register(ScriptedMockProvider(f"seat{i}"))   # declares nothing
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                          provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(TASK, session_id="unmapped"))
    core = ced.project_governing_state(ced.get_session("unmapped"), final)

    assert core.objections, "objections must still be recorded"
    first_claim = next(iter(core.claims))
    for objection in core.objections.values():
        assert objection.target_claim_id == UNMAPPED_TARGET
        assert objection.target_claim_id != first_claim
        assert objection.target_provenance is ObjectionTargetProvenance.UNMAPPED
    # And they weigh nothing on any claim.
    for claim_id in core.claims:
        assert core.assess_claim(claim_id).unresolved_record_ids == []


def test_4_an_unmapped_objection_is_never_put_to_a_vote():
    """It could move no claim whatever the verdict, so it buys nothing."""
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for i in range(3):
        registry.register(ScriptedMockProvider(f"seat{i}"))
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                          provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(TASK, session_id="novote"))
    session = ced.get_session("novote")
    core = ced.project_governing_state(session, final)
    verdicts = asyncio.run(ced.run_objection_verification(session, core))
    assert verdicts == {}
    assert all(o.state is ObjectionState.RAISED for o in core.objections.values())


# ══ 5-6. scope survives targeting ════════════════════════════════════════════

def test_5_a_justification_objection_cannot_falsify_a_conclusion():
    state = _state()
    state.add_objection(_objection("o", "final_verdict",
                                   scope=ObjectionScope.JUSTIFICATION,
                                   state=ObjectionState.VALIDATED))
    assessment = state.assess_claim("final_verdict")
    assert assessment.support_state is SupportState.UNRESOLVED
    assert assessment.support_state is not SupportState.FALSIFIED
    assert state.objections["o"].is_destructive is False
    assert _release(state).release_decision is not ReleaseDecision.BLOCKED


def test_6_a_conclusion_objection_is_not_downgraded_by_the_projection():
    """Targeting decides *what* an objection is about, never *how hard* it hits."""
    conclusion = _objection("o", "final_verdict", scope=ObjectionScope.CONCLUSION,
                            state=ObjectionState.VALIDATED)
    assert conclusion.scope is ObjectionScope.CONCLUSION
    assert conclusion.is_destructive is True
    state = _state()
    state.add_objection(conclusion)
    assert state.objections["o"].scope is ObjectionScope.CONCLUSION
    assert state.assess_claim("final_verdict").support_state is SupportState.FALSIFIED


def test_6_the_default_scope_is_still_the_non_destructive_one():
    assert _objection("o", "final_verdict").scope is ObjectionScope.JUSTIFICATION


# ══ 7. replay ════════════════════════════════════════════════════════════════

def test_7_replay_preserves_target_scope_and_provenance():
    a_ced, a_final = _session("replay_t")
    b_ced, b_final = _session("replay_t")
    a = a_ced.project_governing_state(a_ced.get_session("replay_t"), a_final)
    b = b_ced.project_governing_state(b_ced.get_session("replay_t"), b_final)

    def shape(core):
        return sorted((o.objection_id, o.target_claim_id, o.scope.value,
                       o.target_provenance.value) for o in core.objections.values())

    assert shape(a) == shape(b)
    assert shape(a), "there must be objections to compare"


def test_7_a_round_tripped_objection_keeps_its_target_and_scope():
    original = _objection("o", "final_verdict", scope=ObjectionScope.CONCLUSION)
    wire = json.loads(original.model_dump_json())
    rebuilt = ObjectionRecord(**wire)
    assert rebuilt.target_claim_id == "final_verdict"
    assert rebuilt.scope is ObjectionScope.CONCLUSION
    assert rebuilt.target_provenance is original.target_provenance


# ══ 8-9. the firewall is unchanged, and cannot decide a target ═══════════════

def test_8_the_admissible_basis_classes_are_untouched():
    assert set(ADMISSIBLE_EVIDENCE_SOURCES) == {
        EvidenceSourceType.SUPPLIED_TASK_MATERIAL,
        EvidenceSourceType.DETERMINISTIC_COMPUTATION,
        EvidenceSourceType.TOOL_RECEIPT,
        EvidenceSourceType.EXTERNAL_SOURCE,
        EvidenceSourceType.HUMAN_PROVIDED,
    }


def test_8_model_evidence_still_creates_no_basis_under_the_new_release_rule():
    state = _state()
    for i in range(4):
        state.add_evidence(EvidenceRecord(
            evidence_id=f"m{i}", claim_id="core_answer",
            stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.CORROBORATED_MODEL_INTERPRETATION,
            source_identity=f"seat{i}", content="we agree"))
    assert state.assess_claim("core_answer").basis_record_ids == []


def test_9_agreement_confidence_and_scores_cannot_decide_a_target():
    """Nothing countable maps an objection. Only a declared identifier does.

    Four seats agreeing at high confidence that a section is wrong, with no
    section named, maps to nothing at all.
    """
    ced, final = _session("no_vote_target")
    final.ratification_votes = [
        RatificationVote(voter_agent_id=f"agent_{i}",
                         decision=RatificationDecision.BLOCKING_OBJECTION,
                         severity=ObjectionSeverity.CRITICAL,
                         reason=f"seat {i} is certain the answer is wrong")
        for i in range(4)
    ]
    core = ced.project_governing_state(ced.get_session("no_vote_target"), final)
    from_votes = [o for o in core.objections.values() if "certain" in o.text]
    assert len(from_votes) == 4
    assert all(o.target_claim_id == UNMAPPED_TARGET for o in from_votes)
    assert all(o.target_provenance is ObjectionTargetProvenance.UNMAPPED
               for o in from_votes)


def test_9_a_verified_check_still_cannot_support_from_a_seat():
    state = _state()
    for seat in ("seat0", "seat1"):
        state.add_verification(verify_task_internal(
            claim_id="core_answer", objection_id=None, task_text=TASK,
            cited_spans=[("Ben is not last", TASK.index("Ben is not last"))],
            condition_tested="established?", holds=True, rationale="yes",
            verifier_provider_id=seat))
    assert state.assess_claim("core_answer").basis_record_ids == []
