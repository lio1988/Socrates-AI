"""H7 — the canonical session's release authority is the hybrid core.

Before H7 the final epistemic verdict was a mean-quality threshold. After it,
`run_registry_session` routes the release through `freeze_release`, and the
legacy value survives only as clearly-labelled compatibility metadata.

Everything upstream of the authority boundary must be untouched: roles, provider
routing, prompts, moves, scoring, assembly and ratification inputs.

All offline: mock providers, no network, no key.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_epistemic import (
    ClaimRecord, EvidenceRecord, EvidenceSourceType, EvidenceStance,
    HybridEpistemicState, ObjectionRecord, ObjectionState, ReleaseDecision,
    SupportState, VerificationClass, freeze_release, verify_task_internal,
)
from backend.dialogues.models import EpistemicStatus, ShadowScoringMode
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider

Q = "Is consensus among AI models a reliable signal of truth?"


def _run(session_id="h7", agents=4, seats=3):
    provider = FakeProvider()
    council = [SocraticAgent(f"agent_{i}", provider) for i in range(agents)]
    registry = CouncilProviderRegistry()
    for i in range(seats):
        registry.register(ScriptedMockProvider(f"mock_seat{i}"))
    ced = CEDOrchestrator(council, provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(Q, session_id=session_id))
    return ced, ced.get_session(session_id), final


# ── 1. the canonical session routes through freeze_release ───────────────────

def test_run_registry_session_produces_a_governing_release():
    _ced, _state, final = _run()
    governing = final.audit_summary["governing_release"]
    assert governing["available"] is True
    assert final.release_decision in {d.value for d in ReleaseDecision}
    assert final.governing_epistemic_status in {s.value for s in SupportState}
    assert governing["frozen_digest"]


def test_the_release_is_produced_by_freeze_release_and_not_reimplemented(monkeypatch):
    """The one release authority is called; CED does not compute its own."""
    calls = []
    import backend.dialogues.ced as ced_mod
    original = ced_mod.freeze_release

    def spy(*args, **kwargs):
        calls.append(kwargs.get("assembled_claim_ids"))
        return original(*args, **kwargs)

    monkeypatch.setattr(ced_mod, "freeze_release", spy)
    _run(session_id="h7_spy")
    assert len(calls) == 1


# ── 2-4. the legacy threshold cannot govern ──────────────────────────────────

def test_legacy_epistemic_hint_does_not_determine_the_governing_status():
    _ced, _state, final = _run(session_id="h7_legacy")
    governing = final.audit_summary["governing_release"]
    assert governing["legacy_epistemic_status_authority"] == "legacy_non_governing"
    # The legacy label is retained; it is not the governing value.
    assert governing["legacy_epistemic_status"] == final.epistemic_status.value
    assert final.governing_epistemic_status != "well_supported"


def test_high_quality_without_support_is_never_governing_supported():
    core = HybridEpistemicState("q", "task")
    core.add_claim(ClaimRecord(claim_id="c", text="fluent and unsupported"))
    release = freeze_release(core, assembled_claim_ids=["c"], quality_mean=9.9,
                             legacy_epistemic_status="well_supported")
    assert release.quality_mean == 9.9
    assert release.legacy_epistemic_status == "well_supported"
    assert release.release_decision is not ReleaseDecision.RELEASE_SUPPORTED
    assert release.basis_record_ids == []


def test_a_ratified_session_without_support_is_not_governing_supported():
    _ced, _state, final = _run(session_id="h7_ratified")
    assert final.ratified is True                      # ratification unchanged
    assert final.governing_epistemic_status != SupportState.SUPPORTED.value
    assert final.audit_summary["governing_release"]["basis_record_ids"] == []


# ── 5. the frozen H10 failure projects as unresolved ─────────────────────────

def test_the_h10_shaped_session_projects_as_unresolved_not_well_supported():
    """Sections assembled, objections raised and unverified: nothing supports it."""
    _ced, state, final = _run(session_id="h7_h10")
    core = _ced.project_governing_state(state, final)
    assert core.claims, "assembled sections should project as claims"
    release = freeze_release(core, assembled_claim_ids=list(core.claims))
    assert release.release_decision is not ReleaseDecision.RELEASE_SUPPORTED
    assert release.basis_record_ids == []


# ── 6-8. the core's verdicts reach the canonical boundary ────────────────────

def test_a_claim_with_an_admissible_basis_can_be_strongly_released():
    core = HybridEpistemicState("s", "task")
    core.add_claim(ClaimRecord(claim_id="c", text="supported"))
    core.add_evidence(EvidenceRecord(
        evidence_id="e", claim_id="c", stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.DETERMINISTIC_COMPUTATION,
        source_identity="checker"))
    release = freeze_release(core, assembled_claim_ids=["c"], quality_mean=1.0)
    assert release.release_decision is ReleaseDecision.RELEASE_SUPPORTED
    assert release.basis_record_ids == ["e"]


def test_a_validated_objection_blocks_the_release():
    task = "Ben does not present last."
    core = HybridEpistemicState("b", task)
    core.add_claim(ClaimRecord(claim_id="c", text="an order putting Ben last",
                               verification_class=VerificationClass.TASK_INTERNAL))
    core.add_objection(ObjectionRecord(objection_id="o", target_claim_id="c",
                                       text="Ben is last"))
    core.transition_objection("o", ObjectionState.PENDING_VERIFICATION)
    check = core.add_verification(verify_task_internal(
        claim_id="c", objection_id="o", task_text=task,
        cited_spans=[("Ben does not present last", 0)],
        condition_tested="is Ben last?", holds=True, rationale="position 4"))
    core.transition_objection("o", ObjectionState.VALIDATED,
                              verification_id=check.verification_id)
    release = freeze_release(core, assembled_claim_ids=["c"], quality_mean=10.0)
    assert release.release_decision is ReleaseDecision.BLOCKED
    assert "falsified" in release.blocked_reason


def test_an_unverified_objection_leaves_the_claim_unresolved_not_falsified():
    core = HybridEpistemicState("u", "task")
    core.add_claim(ClaimRecord(claim_id="c", text="a correct claim"))
    core.add_objection(ObjectionRecord(objection_id="o", target_claim_id="c",
                                       text="persuasive but unchecked"))
    assessment = core.assess_claim("c")
    assert assessment.support_state is SupportState.UNRESOLVED
    assert assessment.eligible_for_assembly is True
    release = freeze_release(core, assembled_claim_ids=["c"])
    assert release.release_decision is ReleaseDecision.RELEASE_UNRESOLVED


# ── 9-14. execution parity: everything upstream is unchanged ─────────────────

def test_scoring_behaviour_is_unchanged():
    _ced, state, final = _run(session_id="h7_scoring")
    coverage = final.audit_summary["score_coverage"]
    assert coverage["scores_collected"] > 0
    assert coverage["scores_collected"] == len(state.micro_scores)
    assert state.shadow_harvest is not None


def test_ratification_behaviour_is_unchanged():
    _ced, _state, final = _run(session_id="h7_rat")
    council = final.audit_summary["council_ratification"]
    assert council["valid_verdicts"] >= council["quorum"]
    assert final.ratification_status
    assert isinstance(final.ratified, bool)


def test_five_section_synthesis_is_unchanged():
    _ced, _state, final = _run(session_id="h7_sections")
    assert final.synthesis is not None
    names = [s.section_name.value for s in final.synthesis.sections]
    assert names == ["core_answer", "crucial_stress_test", "blind_spots",
                     "nuance", "final_verdict"]


def test_provider_routing_and_model_identity_are_unchanged():
    _ced, _state, final = _run(session_id="h7_providers")
    summary = final.audit_summary["provider_status_summary"]
    assert summary["available_providers"] == ["mock_seat0", "mock_seat1", "mock_seat2"]
    rounds = final.audit_summary["registry_phase_rounds"]
    assert all(r["proceed"] for r in rounds)


def test_role_rotation_is_unchanged():
    _ced, state, _final = _run(session_id="h7_roles")
    assert state.role_history, "roles must still rotate per phase"
    phases = {entry["phase"] for entry in state.role_history}
    assert len(phases) > 1


def test_observer_failure_isolation_is_unchanged():
    """A projection failure must never destroy the canonical response."""
    provider = FakeProvider()
    council = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    for i in range(3):
        registry.register(ScriptedMockProvider(f"mock_seat{i}"))
    ced = CEDOrchestrator(council, provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)

    def exploding(*_args, **_kwargs):
        raise RuntimeError("projection blew up")

    ced.project_governing_state = exploding
    final = asyncio.run(ced.run_registry_session(Q, session_id="h7_isolate"))
    governing = final.audit_summary["governing_release"]
    assert governing["available"] is False
    assert governing["reason"] == "RuntimeError"
    assert final.synthesis is not None                 # canonical output stands
    assert final.governing_epistemic_status is None     # and nothing was invented


# ── 15. replay ──────────────────────────────────────────────────────────────

def test_replay_reproduces_an_identical_governing_decision():
    a_ced, a_state, a_final = _run(session_id="replay_h7")
    b_ced, b_state, b_final = _run(session_id="replay_h7")
    assert a_final.audit_summary["governing_release"]["frozen_digest"] == \
        b_final.audit_summary["governing_release"]["frozen_digest"]
    assert a_final.release_decision == b_final.release_decision
    assert a_final.governing_epistemic_status == b_final.governing_epistemic_status


# ── 16. legacy compatibility is clearly non-governing ───────────────────────

def test_legacy_field_is_retained_and_explicitly_labelled():
    _ced, _state, final = _run(session_id="h7_labels")
    assert isinstance(final.epistemic_status, EpistemicStatus)   # still public
    assert final.audit_summary["legacy_epistemic_status_authority"] == \
        "legacy_non_governing"
    assert final.audit_summary["governing_release"][
        "legacy_epistemic_status_authority"] == "legacy_non_governing"


def test_the_two_statuses_are_separately_named_and_unambiguous():
    _ced, _state, final = _run(session_id="h7_unambiguous")
    dumped = final.model_dump(mode="json")
    assert "epistemic_status" in dumped              # legacy, compatibility
    assert "governing_epistemic_status" in dumped    # the authority
    assert "release_decision" in dumped              # the release verdict
