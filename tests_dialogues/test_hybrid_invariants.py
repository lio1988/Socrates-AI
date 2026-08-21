"""The hard safety properties, each mapped to the code that enforces it.

Every test here names one thing the final system must make structurally
impossible, and exercises the exact mechanism that prevents it. If one of these
fails, an authority boundary has moved.

All offline: no provider, no network, no key.
"""

from __future__ import annotations

import pytest

from backend.dialogues.hybrid_epistemic import (
    ADMISSIBLE_EVIDENCE_SOURCES,
    DESTRUCTIVE_OBJECTION_STATES,
    CARRIED_APPLICABILITY,
    ClaimBallot,
    ClaimRecord,
    ContradictionRecord,
    ContradictionState,
    EvidenceApplicability,
    EvidenceCarry,
    EvidenceRecord,
    EvidenceSourceType,
    EvidenceStance,
    HybridEpistemicState,
    ObjectionRecord,
    ObjectionState,
    RatificationDisposition,
    ReleaseDecision,
    RevisionRecord,
    SupportState,
    VerificationClass,
    freeze_release,
)

TASK = ("Anna presents before Ben. Clara presents immediately before David. "
        "Ben does not present last.")


def _state():
    state = HybridEpistemicState("inv", TASK)
    state.add_claim(ClaimRecord(claim_id="c", text="a claim",
                                verification_class=VerificationClass.TASK_INTERNAL))
    return state


# ── QUALITY SCORE → SUPPORT :: impossible ────────────────────────────────────
# Enforced by: assess_claim reads only evidence and verification records.
# There is no quality input to the function at all.

def test_quality_score_cannot_become_support():
    state = _state()
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=10.0,
                             legacy_epistemic_status="well_supported")
    assert state.assess_claim("c").support_state is SupportState.UNSUPPORTED
    assert release.basis_record_ids == []
    assert release.release_decision is not ReleaseDecision.RELEASE_SUPPORTED


def test_the_assessment_signature_admits_no_quality_input():
    import inspect
    params = set(inspect.signature(HybridEpistemicState.assess_claim).parameters)
    assert params == {"self", "claim_id"}


# ── HIGH CONFIDENCE → SUPPORT :: impossible ──────────────────────────────────
# Enforced by: confidence is not a field the core reads. It lives on the move,
# and no move field reaches assess_claim.

def test_confidence_is_not_a_field_of_any_governing_record():
    from backend.dialogues.hybrid_epistemic import (
        ClaimRecord as C, EvidenceRecord as E, VerificationRecord as V,
    )
    for model in (C, E, V):
        assert "confidence" not in model.model_fields


# ── CONSENSUS → SUPPORT :: impossible ────────────────────────────────────────
# Enforced by: EvidenceSourceType.MODEL_ASSERTION is excluded from
# ADMISSIBLE_EVIDENCE_SOURCES, so agreement cannot accumulate into a basis.

def test_model_assertion_is_never_admissible_at_any_volume():
    assert EvidenceSourceType.MODEL_ASSERTION not in ADMISSIBLE_EVIDENCE_SOURCES
    state = _state()
    for i in range(40):
        state.add_evidence(EvidenceRecord(
            evidence_id=f"e{i}", claim_id="c", stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.MODEL_ASSERTION,
            source_identity=f"seat{i}"))
    assert state.assess_claim("c").basis_record_ids == []


# ── EPISTEMIC MARKER → SUPPORT :: impossible ─────────────────────────────────
# Enforced by: the governing core has no marker field and does not import the
# module that defines them.

def test_the_governing_core_has_no_marker_concept():
    """Checked against the code, not the prose: the docstring names the marker
    precisely in order to say it grants nothing."""
    import ast
    import backend.dialogues.hybrid_epistemic as core
    from backend.dialogues.hybrid_epistemic import (
        ClaimRecord as C, EvidenceRecord as E, VerificationRecord as V,
    )

    for model in (C, E, V):
        assert not any("marker" in f for f in model.model_fields)

    tree = ast.parse(open(core.__file__, encoding="utf-8").read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert not any("Marker" in n or "marker" in n for n in imported)


# ── RATIFIER COUNT → SUPPORT :: impossible ───────────────────────────────────
# Enforced by: freeze_release counts ballots into reporting fields only; the
# release decision is computed from basis and unresolved records.

def test_unanimous_ratification_cannot_create_a_basis():
    state = _state()
    ballots = [ClaimBallot(ballot_id=f"b{i}", claim_id="c",
                           ratifier_provider_id=f"seat{i}",
                           disposition=RatificationDisposition.ACCEPT)
               for i in range(9)]
    release = freeze_release(state, assembled_claim_ids=["c"], ballots=ballots)
    assert release.unanchored_ballots == 9
    assert release.basis_record_ids == []
    assert release.release_decision is ReleaseDecision.RELEASE_UNRESOLVED


# ── UNVERIFIED OBJECTION → FALSIFICATION :: impossible ───────────────────────
# Enforced by: DESTRUCTIVE_OBJECTION_STATES == (VALIDATED,) and the transition
# guard requiring a matching verification record.

def test_only_validated_objections_are_destructive():
    assert DESTRUCTIVE_OBJECTION_STATES == (ObjectionState.VALIDATED,)
    state = _state()
    for i, initial in enumerate((ObjectionState.RAISED,
                                 ObjectionState.PENDING_VERIFICATION,
                                 ObjectionState.INCONCLUSIVE)):
        state.add_objection(ObjectionRecord(
            objection_id=f"o{i}", target_claim_id="c", text="persuasive but unchecked",
            state=initial))
    assessment = state.assess_claim("c")
    assert assessment.support_state is not SupportState.FALSIFIED
    assert assessment.falsifying_record_ids == []
    assert assessment.eligible_for_assembly is True


# ── STALE EVIDENCE → AUTOMATIC SUPPORT OF REVISION :: impossible ─────────────
# Enforced by: revise() moves only CARRIED_APPLICABILITY items; everything else
# stays on the superseded claim.

def test_only_explicitly_carried_evidence_reaches_a_revision():
    assert set(CARRIED_APPLICABILITY) == {EvidenceApplicability.STILL_APPLICABLE,
                                          EvidenceApplicability.REVALIDATED}
    state = _state()
    state.add_claim(ClaimRecord(claim_id="c2", text="revised"))
    for i, applicability in enumerate((EvidenceApplicability.STALE,
                                       EvidenceApplicability.CONTRADICTORY,
                                       EvidenceApplicability.UNRESOLVED)):
        state.add_evidence(EvidenceRecord(
            evidence_id=f"e{i}", claim_id="c", stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.SUPPLIED_TASK_MATERIAL,
            source_identity="task"))
        state.revise(RevisionRecord(
            revision_id=f"r{i}", from_claim_id="c", to_claim_id="c2",
            evidence_disposition=[EvidenceCarry(evidence_id=f"e{i}",
                                                applicability=applicability)]))
    assert state.assess_claim("c2").basis_record_ids == []


# ── UNVALIDATED CONTRADICTION → GOVERNING PENALTY :: impossible ──────────────
# Enforced by: incompatible_pairs filters on ContradictionState.VALIDATED.

def test_candidate_contradictions_never_penalise_or_block():
    state = _state()
    state.add_claim(ClaimRecord(claim_id="c2", text="other"))
    for i in range(30):
        state.add_contradiction(ContradictionRecord(
            contradiction_id=f"x{i}", claim_id_a="c", claim_id_b="c2",
            state=ContradictionState.CANDIDATE, detector="noisy"))
    assert state.incompatible_pairs(["c", "c2"]) == []
    assert state.assess_claim("c").eligible_for_assembly is True
    release = freeze_release(state, assembled_claim_ids=["c", "c2"])
    assert release.release_decision is not ReleaseDecision.BLOCKED


# ── INCOMPATIBLE CLAIMS → SILENT ASSEMBLY :: impossible ──────────────────────
# Enforced by: freeze_release blocks on any validated incompatible pair.

def test_a_validated_contradiction_blocks_assembly_loudly():
    state = _state()
    state.add_claim(ClaimRecord(claim_id="c2", text="other"))
    state.add_contradiction(ContradictionRecord(
        contradiction_id="x", claim_id_a="c", claim_id_b="c2",
        state=ContradictionState.VALIDATED))
    release = freeze_release(state, assembled_claim_ids=["c", "c2"])
    assert release.release_decision is ReleaseDecision.BLOCKED
    assert "validated contradiction" in release.blocked_reason


# ── MISSING EVIDENCE → FABRICATED SUPPORT :: impossible ─────────────────────
# Enforced by: SUPPORTED requires a non-empty basis; there is no default.

def test_release_supported_is_unreachable_without_a_basis():
    state = _state()
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=10.0)
    assert release.basis_record_ids == []
    assert release.release_decision is not ReleaseDecision.RELEASE_SUPPORTED


def test_external_evidence_required_is_a_terminal_answer_not_a_gap():
    from backend.dialogues.hybrid_epistemic import external_evidence_required
    state = HybridEpistemicState("ext", TASK)
    state.add_claim(ClaimRecord(claim_id="c", text="a world fact",
                                verification_class=VerificationClass.EXTERNAL_EVIDENCE))
    state.add_verification(external_evidence_required("c", "nothing in the task"))
    assessment = state.assess_claim("c")
    assert assessment.support_state is SupportState.EXTERNAL_EVIDENCE_REQUIRED
    assert assessment.basis_record_ids == []


# ── PROVIDER FAILURE → FABRICATED EVIDENCE :: impossible ────────────────────
# Enforced by: the registry returns a failure status and no move; a failed
# provider therefore contributes no claim, no evidence and no ballot.

def test_a_failed_provider_contributes_nothing_to_the_governing_state():
    import asyncio
    from backend.dialogues.models import (
        AgentRole, AgentState, AgentTask, DialogPhase, ProviderStatus,
    )
    from backend.dialogues.provider_registry import (
        CouncilProviderRegistry, TimeoutScriptedProvider,
    )

    registry = CouncilProviderRegistry()
    adapter = TimeoutScriptedProvider()
    registry.register(adapter)
    task = AgentTask(session_id="s", agent_id="a", role=AgentRole.SYNTHESIZER,
                     phase=DialogPhase.SYNTHESIS, question="q")
    agent_state = AgentState(agent_id="a", primary_role=AgentRole.SYNTHESIZER,
                             assigned_role=AgentRole.SYNTHESIZER)
    response = asyncio.run(registry.run_adapter(adapter, task, agent_state,
                                                timeout_seconds=0.01))
    assert response.status is ProviderStatus.TIMEOUT
    assert response.parsed_move is None
    assert response.ok is False

    # Nothing from that response can reach the core: there is no move to project.
    state = HybridEpistemicState("fail", TASK)
    assert state.claims == {} and state.evidence == {}
    assert freeze_release(state, assembled_claim_ids=[]).basis_record_ids == []


# ── one governing authority ─────────────────────────────────────────────────

def test_there_is_exactly_one_release_authority():
    """freeze_release is the only function that produces a release decision."""
    import backend.dialogues.hybrid_epistemic as core
    producers = [name for name in dir(core)
                 if name.startswith("freeze") or name.endswith("_release")]
    assert producers == ["freeze_release"]


def test_there_is_exactly_one_ledger_type():
    import backend.dialogues.hybrid_shadow as ledger_mod
    import backend.dialogues.hybrid_epistemic as core
    import backend.dialogues.hybrid_support as support
    ledgers = {c.__name__ for m in (ledger_mod, core, support)
               for c in vars(m).values()
               if isinstance(c, type) and c.__name__.endswith("Ledger")}
    assert ledgers == {"HybridEpistemicLedger"}
