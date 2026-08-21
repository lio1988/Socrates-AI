"""H2 quality/epistemic-support separation invariants.

The locked rule: nothing a model says about itself, and nothing about how well
it said it, may create epistemic support. Markers, confidence, quality scores,
agreement and ratification are all visible in H2 and all authoritative over
nothing. Support is categorical and names the records it rests on.

All tests are offline: no provider, no network, no key.
"""

from __future__ import annotations

import asyncio
import pathlib

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_shadow import (
    HybridEpistemicLedger,
    HybridRecordKind,
    HybridShadowObserver,
)
from backend.dialogues.hybrid_support import (
    AUTHORITATIVE_SUPPORT_INPUTS,
    HYBRID_SUPPORT_SCHEMA_VERSION,
    SUPPORT_INPUT_CLASSIFICATION,
    EpistemicSupportAssessment,
    HybridSupportObserver,
    HybridSupportStatus,
    SupportInputClass,
    assess_session_support,
)
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    DialogPhase,
    EpistemicMarker,
    EpistemicStatus,
    MicroScore,
    ScoreBreakdown,
    SessionState,
    ShadowScoringMode,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider

Q = "Is consensus among AI models a reliable signal of truth?"

# Every status the support plane can currently reach. None of them is support.
_NOT_SUPPORT = {HybridSupportStatus.UNSUPPORTED, HybridSupportStatus.UNRESOLVED}


def _move(move_id, *, marker=None, confidence=0.7,
          phase=DialogPhase.INITIAL_RESPONSE, content=None):
    return AgentMove(
        move_id=move_id, task_id=f"task_{move_id}", agent_id="agent_0",
        role=AgentRole.SYNTHESIZER, phase=phase,
        content=content if content is not None else {"text": "a claim"},
        confidence=confidence,
        epistemic_markers=[marker] if marker is not None else [],
    )


def _state(moves, question=Q, session_id="s_h2"):
    return SessionState(session_id=session_id, question=question, moves=list(moves))


def _scored(state, value):
    """Give every move in `state` a peer quality score of `value` on all dimensions."""
    state.micro_scores = [
        MicroScore(
            session_id=state.session_id, output_id=m.move_id, phase=m.phase,
            author_agent_id="agent_0", voter_agent_id="agent_1",
            score_breakdown=ScoreBreakdown(
                **{d: value for d in ScoreBreakdown.model_fields}),
        )
        for m in state.moves
    ]
    return state


def _run_session():
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    for i in range(3):
        registry.register(ScriptedMockProvider(f"mock_seat{i}"))
    ced = CEDOrchestrator(agents, provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(Q, session_id="h2_sess"))
    return ced, ced.get_session("h2_sess"), final


# ── 1-4. no marker, at any strength or volume, creates support ───────────────

@pytest.mark.parametrize("marker", list(EpistemicMarker), ids=lambda m: m.value)
def test_a_marker_alone_never_creates_support(marker):
    """1-3 and the rest of the vocabulary: self-description is not evidence."""
    a = assess_session_support(_state([_move("m1", marker=marker, confidence=0.4)]))
    assert a.hybrid_h2_epistemic_status in _NOT_SUPPORT
    assert a.basis_record_ids == []
    # The marker is still recorded — visible, and powerless.
    assert a.marker_counts == {marker.value: 1}


def test_many_markers_never_create_support():
    """4. Volume of self-description is still self-description."""
    boastful = _state([_move(f"m{i}", marker=EpistemicMarker.ESTABLISHED_FACT,
                             confidence=1.0) for i in range(25)])
    a = assess_session_support(boastful)
    assert a.hybrid_h2_epistemic_status in _NOT_SUPPORT
    assert a.basis_record_ids == []
    assert a.marker_counts == {"established_fact": 25}


# ── 5-6. quality and ratification cannot substitute for records ──────────────

def test_top_quality_plus_established_fact_still_yields_no_support():
    """5. A perfect score on a self-declared fact establishes nothing."""
    state = _scored(_state([_move("m1", marker=EpistemicMarker.ESTABLISHED_FACT)],
                           session_id="s_perfect"), 10.0)
    a = assess_session_support(state)
    assert a.quality_mean == pytest.approx(10.0)      # quality at the ceiling
    assert a.hybrid_h2_epistemic_status in _NOT_SUPPORT
    assert a.basis_record_ids == []


def test_ratified_plus_established_fact_still_yields_no_support():
    """6. Ratification is agreement among readers, not corroboration."""
    _ced, state, final = _run_session()
    assert final.ratified is True
    a = assess_session_support(state, final)
    assert a.hybrid_h2_epistemic_status in _NOT_SUPPORT
    assert a.basis_record_ids == []


def test_quality_score_cannot_move_the_support_status():
    low = assess_session_support(
        _scored(_state([_move("m1")], session_id="s_low"), 1.0))
    high = assess_session_support(
        _scored(_state([_move("m1")], session_id="s_high"), 10.0))
    assert low.quality_mean != high.quality_mean
    assert low.hybrid_h2_epistemic_status == high.hybrid_h2_epistemic_status
    assert low.basis_record_ids == high.basis_record_ids == []


def test_confidence_cannot_move_the_support_status():
    timid = assess_session_support(_state(
        [_move("m1", marker=EpistemicMarker.REASONABLE_HYPOTHESIS, confidence=0.1)],
        session_id="s_timid"))
    brash = assess_session_support(_state(
        [_move("m1", marker=EpistemicMarker.REASONABLE_HYPOTHESIS, confidence=0.75)],
        session_id="s_brash"))
    assert timid.hybrid_h2_epistemic_status == brash.hybrid_h2_epistemic_status
    assert timid.basis_record_ids == brash.basis_record_ids == []


def test_consensus_cannot_move_the_support_status():
    """Ten agreeing moves are more numerous, not better supported."""
    one = assess_session_support(_state(
        [_move("m0", marker=EpistemicMarker.REASONABLE_HYPOTHESIS)],
        session_id="s_one"))
    many = assess_session_support(_state(
        [_move(f"m{i}", marker=EpistemicMarker.REASONABLE_HYPOTHESIS,
               content={"text": "the very same claim"}) for i in range(10)],
        session_id="s_many"))
    assert one.hybrid_h2_epistemic_status == many.hybrid_h2_epistemic_status
    assert one.basis_record_ids == many.basis_record_ids == []


# ── no numeric epistemic ranker anywhere ─────────────────────────────────────

def test_no_numeric_epistemic_ranker_exists():
    """The support plane exposes no score, index or rank of any kind."""
    banned = ("support_index", "epistemic_score", "truth_score", "support_score",
              "epistemic_rank", "support_rank", "supportedness")
    fields = set(EpistemicSupportAssessment.model_fields)
    assert not (fields & set(banned))
    status = EpistemicSupportAssessment.model_fields["hybrid_h2_epistemic_status"]
    assert status.annotation is HybridSupportStatus


def test_nothing_is_classified_as_an_authoritative_support_input():
    """Until H3+ can verify, no input may establish support. Pinned explicitly."""
    assert AUTHORITATIVE_SUPPORT_INPUTS == ()
    for name in ("epistemic_marker", "move_confidence"):
        assert SUPPORT_INPUT_CLASSIFICATION[name] is SupportInputClass.ADVISORY_METADATA
    for name in ("peer_quality_score", "ratification_verdict", "council_agreement",
                 "legacy_epistemic_status"):
        assert SUPPORT_INPUT_CLASSIFICATION[name] is SupportInputClass.QUALITY_SIGNAL


# ── 11. the status is categorical and names its basis ────────────────────────

def test_status_is_categorical_and_states_its_basis():
    """11. Every status exposes what it rests on and what is still open."""
    challenged = _state([
        _move("m1", marker=EpistemicMarker.REASONABLE_HYPOTHESIS),
        _move("obj1", phase=DialogPhase.ELENCHUS,
              content={"objection": "the premise is unsupported"}),
    ])
    a = assess_session_support(challenged)
    assert a.hybrid_h2_epistemic_status is HybridSupportStatus.UNRESOLVED
    assert a.basis_record_ids == []
    assert a.unresolved_record_ids == ["obj1"]
    assert a.advisory_metadata_count > 0

    quiet = assess_session_support(_state([_move("m1")], session_id="s_quiet"))
    assert quiet.hybrid_h2_epistemic_status is HybridSupportStatus.UNSUPPORTED
    assert quiet.unresolved_record_ids == []


# ── 10. legacy canonical status stays available, and stays out of the status ─

def test_legacy_canonical_status_is_carried_through_unchanged():
    """10. The old threshold result stays visible for comparison."""
    _ced, state, final = _run_session()
    a = assess_session_support(state, final)
    assert a.legacy_epistemic_status == final.epistemic_status.value
    assert a.legacy_epistemic_status in {s.value for s in EpistemicStatus}


def test_legacy_well_supported_does_not_make_the_hybrid_status_supported():
    """The threshold that promotes on quality alone must not leak through."""
    _ced, state, final = _run_session()
    final.epistemic_status = EpistemicStatus.WELL_SUPPORTED
    a = assess_session_support(state, final)
    assert a.legacy_epistemic_status == "well_supported"
    assert a.hybrid_h2_epistemic_status in _NOT_SUPPORT


def test_hybrid_status_is_absent_when_no_final_response_is_supplied():
    a = assess_session_support(_state([_move("m1")]))
    assert a.legacy_epistemic_status is None
    assert a.hybrid_h2_epistemic_status in _NOT_SUPPORT


# ── 7. markers survive as replayable metadata ────────────────────────────────

def test_marker_is_stored_and_replayed_as_metadata():
    """7. Powerless does not mean discarded — the marker must round-trip."""
    _ced, state, final = _run_session()
    state.moves[0].epistemic_markers = [EpistemicMarker.OPEN_UNCERTAINTY]
    ledger = HybridEpistemicLedger()
    records = HybridSupportObserver(ledger).capture_support(state, final)
    stored = {r.payload["move_id"]: r.payload.get("marker") for r in records
              if r.kind is HybridRecordKind.MOVE_SUPPORT_ASSESSED}
    assert stored[state.moves[0].move_id] == "open_uncertainty"


# ── advisory metadata remains visible ────────────────────────────────────────

def test_advisory_metadata_stays_visible_and_powerless():
    state = _state([
        _move("m1", marker=EpistemicMarker.UNSUBSTANTIATED_CLAIM, confidence=0.9),
        _move("m2"),
    ])
    a = assess_session_support(state)
    assert a.moves_total == 2 and a.moves_marked == 1
    assert a.coverage_ratio == pytest.approx(0.5)
    assert a.unmarked_assertion_ratio == pytest.approx(0.5)
    assert a.overconfidence_violations == 1        # 0.9 over the 0.4 ceiling
    assert a.hybrid_h2_epistemic_status in _NOT_SUPPORT


def test_assessment_is_deterministic():
    state = _state([
        _move("m1", marker=EpistemicMarker.ESTABLISHED_FACT),
        _move("m2", marker=EpistemicMarker.OPEN_UNCERTAINTY, confidence=0.5),
    ])
    assert assess_session_support(state) == assess_session_support(state)


def test_premise_scrutiny_requires_both_engagement_and_challenge():
    challenged = _state([_move(
        "m1", phase=DialogPhase.ELENCHUS,
        content={"objection": "The premise that consensus among models signals "
                              "truth is unsupported; agreement may be correlated error."},
    )])
    assert assess_session_support(challenged).premise_scrutinised is True

    agreeing = _state([_move(
        "m2", phase=DialogPhase.ELENCHUS,
        content={"note": "Consensus among models is a reliable signal of truth."},
    )])
    assert assess_session_support(agreeing).premise_scrutinised is False


# ── ledger integration and the canonical boundary ────────────────────────────

def test_capture_appends_to_the_single_existing_ledger():
    _ced, state, final = _run_session()
    ledger = HybridEpistemicLedger()
    records = HybridSupportObserver(ledger).capture_support(state, final)
    assert HybridRecordKind.SESSION_SUPPORT_ASSESSED in {r.kind for r in records}
    assert all(r.authority == "shadow_non_authoritative" for r in records)
    assert records[0].payload["schema_version"] == HYBRID_SUPPORT_SCHEMA_VERSION


def test_capture_is_idempotent_and_does_not_mutate_canonical_state():
    """13. FinalResponse and SessionState stay byte-identical in shadow mode."""
    _ced, state, final = _run_session()
    before_state = state.model_dump(mode="json")
    before_final = final.model_dump(mode="json")

    observer = HybridSupportObserver(HybridEpistemicLedger())
    first = observer.capture_support(state, final)
    second = observer.capture_support(state, final)

    assert [r.record_id for r in first] == [r.record_id for r in second]
    assert state.model_dump(mode="json") == before_state
    assert final.model_dump(mode="json") == before_final


_H2_KINDS = {HybridRecordKind.SESSION_SUPPORT_ASSESSED,
             HybridRecordKind.MOVE_SUPPORT_ASSESSED}


def test_h1_replay_stays_deterministic_alongside_h2():
    """12. Adding H2 records must not disturb H1 identity, ordering or replay."""
    _ced, state, final = _run_session()
    sid = state.session_id

    alone = HybridEpistemicLedger()
    HybridShadowObserver(alone).capture_session(state, final)
    h1_alone = [r.record_id for r in alone.records(sid)]

    shared = HybridEpistemicLedger()
    HybridShadowObserver(shared).capture_session(state, final)
    before = [r.record_id for r in shared.records(sid)]
    HybridSupportObserver(shared).capture_support(state, final)

    h1_after = [r.record_id for r in shared.records(sid) if r.kind not in _H2_KINDS]
    assert h1_alone == before                  # H2 absent changes nothing
    assert h1_after == before                  # H2 present changes nothing
    assert shared.replay(sid) == shared.records(sid)   # replay stays exact


def test_the_two_planes_are_reported_side_by_side_never_merged():
    _ced, state, final = _run_session()
    payload = HybridSupportObserver(HybridEpistemicLedger()).capture_support(
        state, final)[0].payload
    assert "quality_mean" in payload                       # quality plane
    assert "hybrid_h2_epistemic_status" in payload         # support plane
    assert "legacy_epistemic_status" in payload            # legacy comparison
    assert not any(k.startswith("combined") or "overall_epistemic" in k
                   for k in payload)


def test_no_canonical_module_imports_hybrid_support():
    """The canonical path must not be able to read H2 even by accident."""
    root = pathlib.Path(__file__).resolve().parents[1] / "backend"
    offenders = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if path.name != "hybrid_support.py"
        and "hybrid_support" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"canonical code reads H2: {offenders}"
