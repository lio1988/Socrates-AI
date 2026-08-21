"""H2 quality/epistemic-support separation invariants.

H2 may measure support and append it to the existing ledger, but it must not
touch canonical state, output, scoring, assembly or ratification, and it must
never fabricate a measure it does not have.

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
)
from backend.dialogues.hybrid_support import (
    HYBRID_SUPPORT_SCHEMA_VERSION,
    MARKER_SELF_DECLARATION_WEIGHTS,
    HybridSupportObserver,
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


def _move(move_id, *, marker=None, confidence=0.7, phase=DialogPhase.INITIAL_RESPONSE,
          content=None):
    return AgentMove(
        move_id=move_id, task_id=f"task_{move_id}", agent_id="agent_0",
        role=AgentRole.SYNTHESIZER, phase=phase,
        content=content if content is not None else {"text": "a claim"},
        confidence=confidence,
        epistemic_markers=[marker] if marker is not None else [],
    )


def _state(moves, question=Q, session_id="s_h2"):
    return SessionState(session_id=session_id, question=question, moves=list(moves))


# ── the measure itself ───────────────────────────────────────────────────────

def test_support_index_weights_markers_by_epistemic_strength():
    strong = _state([_move("m1", marker=EpistemicMarker.ESTABLISHED_FACT)])
    weak = _state([_move("m2", marker=EpistemicMarker.UNSUBSTANTIATED_CLAIM)])
    assert assess_session_support(strong).self_declared_support_index == 1.0
    assert assess_session_support(weak).self_declared_support_index == 0.0


def test_support_index_separates_sessions_quality_scoring_cannot():
    """The acceptance criterion for H2.

    Two sessions, identical move count and identical (absent) quality scores.
    One asserts everything as established fact, the other as unsubstantiated.
    The seven quality dimensions cannot tell these apart; support must.
    """
    grounded = _state([_move(f"g{i}", marker=EpistemicMarker.ESTABLISHED_FACT)
                       for i in range(4)], session_id="grounded")
    ungrounded = _state([_move(f"u{i}", marker=EpistemicMarker.UNSUBSTANTIATED_CLAIM)
                         for i in range(4)], session_id="ungrounded")

    a = assess_session_support(grounded)
    b = assess_session_support(ungrounded)
    assert a.quality_mean is None and b.quality_mean is None   # nothing to tell apart
    assert a.self_declared_support_index is not None
    assert b.self_declared_support_index is not None
    assert (a.self_declared_support_index
            - b.self_declared_support_index) == pytest.approx(1.0)


def test_unmarked_assertions_are_counted_not_scored():
    state = _state([
        _move("m1", marker=EpistemicMarker.LOGICAL_INFERENCE),
        _move("m2"),
        _move("m3"),
    ])
    a = assess_session_support(state)
    assert a.moves_total == 3 and a.moves_marked == 1
    assert a.unmarked_assertion_ratio == pytest.approx(2 / 3)
    assert a.coverage_ratio == pytest.approx(1 / 3)
    # An unmarked move must not be silently treated as zero support: the index
    # is the mean over MARKED moves only.
    assert a.self_declared_support_index == pytest.approx(
        MARKER_SELF_DECLARATION_WEIGHTS[EpistemicMarker.LOGICAL_INFERENCE])


def test_no_marked_move_leaves_support_index_missing_not_zero():
    a = assess_session_support(_state([_move("m1"), _move("m2")]))
    assert a.self_declared_support_index is None   # missing, never faked as 0.0
    assert a.coverage_ratio == 0.0
    assert a.unmarked_assertion_ratio == 1.0


def test_overconfidence_against_the_marker_band_is_recorded():
    # unsubstantiated_claim allows at most 0.4 confidence.
    state = _state([
        _move("m1", marker=EpistemicMarker.UNSUBSTANTIATED_CLAIM, confidence=0.9),
        _move("m2", marker=EpistemicMarker.UNSUBSTANTIATED_CLAIM, confidence=0.4),
    ])
    a = assess_session_support(state)
    assert a.overconfidence_violations == 1
    assert [m.overconfident for m in a.moves] == [True, False]


# ── premise scrutiny ─────────────────────────────────────────────────────────

def test_premise_scrutiny_requires_both_engagement_and_challenge():
    challenged = _state([_move(
        "m1", phase=DialogPhase.ELENCHUS,
        content={"objection": "The premise that consensus among models signals "
                              "truth is unsupported; agreement may be correlated error."},
    )])
    assert assess_session_support(challenged).premise_scrutinised is True

    # Engages the terms but never challenges them.
    agreeing = _state([_move(
        "m2", phase=DialogPhase.ELENCHUS,
        content={"note": "Consensus among models is a reliable signal of truth."},
    )])
    assert assess_session_support(agreeing).premise_scrutinised is False


def test_premise_scrutiny_is_only_credited_in_pressure_phases():
    """An opening question restating the prompt is not scrutiny of it."""
    opening = _state([_move(
        "m1", phase=DialogPhase.OPENING,
        content={"question": "Is the premise that consensus signals truth "
                             "unsupported by the evidence?"},
    )])
    assert assess_session_support(opening).premise_scrutinised is False


def test_assessment_is_deterministic():
    state = _state([
        _move("m1", marker=EpistemicMarker.ESTABLISHED_FACT),
        _move("m2", marker=EpistemicMarker.OPEN_UNCERTAINTY, confidence=0.5),
    ])
    assert assess_session_support(state) == assess_session_support(state)


# ── ledger integration and authority boundary ────────────────────────────────

def _run_session(hybrid_support=None):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    for i in range(3):
        registry.register(ScriptedMockProvider(f"mock_seat{i}"))
    ced = CEDOrchestrator(agents, provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(Q, session_id="h2_sess"))
    return ced, ced.get_session("h2_sess"), final


def test_capture_appends_to_the_single_existing_ledger():
    _ced, state, final = _run_session()
    ledger = HybridEpistemicLedger()
    records = HybridSupportObserver(ledger).capture_support(state, final)
    kinds = {r.kind for r in records}
    assert HybridRecordKind.SESSION_SUPPORT_ASSESSED in kinds
    assert all(r.authority == "shadow_non_authoritative" for r in records)
    assert records[0].payload["schema_version"] == HYBRID_SUPPORT_SCHEMA_VERSION


def test_capture_is_idempotent_and_does_not_mutate_canonical_state():
    _ced, state, final = _run_session()
    before_state = state.model_dump(mode="json")
    before_final = final.model_dump(mode="json")

    ledger = HybridEpistemicLedger()
    observer = HybridSupportObserver(ledger)
    first = observer.capture_support(state, final)
    second = observer.capture_support(state, final)

    assert [r.record_id for r in first] == [r.record_id for r in second]
    assert state.model_dump(mode="json") == before_state
    assert final.model_dump(mode="json") == before_final


def test_quality_and_support_are_reported_side_by_side_never_merged():
    _ced, state, final = _run_session()
    a = assess_session_support(state)
    payload = HybridSupportObserver(HybridEpistemicLedger()).capture_support(
        state, final)[0].payload
    # Both present, as distinct fields. H2 exposes no combined figure.
    assert "quality_mean" in payload and "self_declared_support_index" in payload
    assert payload["quality_mean"] == a.quality_mean
    assert not any("combined" in k or "overall_epistemic" in k for k in payload)


def test_h2_is_off_by_default_on_the_orchestrator():
    """Nothing in CED reaches H2 unless a caller injects it explicitly."""
    _ced, state, final = _run_session()
    assert final.ratified in (True, False)          # canonical run completed
    assert not hasattr(_ced, "hybrid_support")      # no implicit wiring added


# ── H2 boundary: nothing may manufacture epistemic support ───────────────────
#
# A marker is the model's own label for its own claim. Quality is how well a move
# reads. Confidence is how sure it says it is. Agreement is how many said it.
# None of those is evidence, so none of them may promote epistemic status. These
# four tests pin each arrow to ABSENT.

def _scored(moves, values, session_id="s_q"):
    """A session whose peer quality scores are all `values` on every dimension."""
    state = _state(moves, session_id=session_id)
    state.micro_scores = [
        MicroScore(
            session_id=session_id, output_id=m.move_id, phase=m.phase,
            author_agent_id="agent_0", voter_agent_id="agent_1",
            score_breakdown=ScoreBreakdown(**{d: values for d in
                                              ScoreBreakdown.model_fields}),
        )
        for m in moves
    ]
    return state


def test_quality_score_cannot_create_support():
    moves = [_move("m1", marker=EpistemicMarker.REASONABLE_HYPOTHESIS)]
    low = assess_session_support(_scored(moves, 1.0, "s_low"))
    high = assess_session_support(_scored(moves, 10.0, "s_high"))
    # Quality moved from the floor to the ceiling.
    assert low.quality_mean != high.quality_mean
    # Support did not move at all.
    assert low.self_declared_support_index == high.self_declared_support_index
    assert low.coverage_ratio == high.coverage_ratio


def test_confidence_cannot_create_support():
    timid = _state([_move("m1", marker=EpistemicMarker.REASONABLE_HYPOTHESIS,
                          confidence=0.1)], session_id="s_timid")
    brash = _state([_move("m1", marker=EpistemicMarker.REASONABLE_HYPOTHESIS,
                          confidence=0.75)], session_id="s_brash")
    a, b = assess_session_support(timid), assess_session_support(brash)
    assert a.self_declared_support_index == b.self_declared_support_index
    # Confidence only ever registers as a consistency observation.
    assert a.overconfidence_violations == b.overconfidence_violations == 0


def test_consensus_cannot_create_support():
    """Ten agreeing moves are not more supported than one — only more numerous."""
    one = _state([_move("m0", marker=EpistemicMarker.REASONABLE_HYPOTHESIS)],
                 session_id="s_one")
    many = _state([_move(f"m{i}", marker=EpistemicMarker.REASONABLE_HYPOTHESIS,
                         content={"text": "the very same claim"})
                   for i in range(10)], session_id="s_many")
    a, b = assess_session_support(one), assess_session_support(many)
    assert a.self_declared_support_index == b.self_declared_support_index
    assert a.coverage_ratio == b.coverage_ratio == 1.0


def test_marker_cannot_promote_canonical_epistemic_status():
    """Self-labelling everything `established_fact` promotes nothing anywhere."""
    boastful = _state([_move(f"m{i}", marker=EpistemicMarker.ESTABLISHED_FACT,
                             confidence=1.0) for i in range(5)], session_id="s_boast")
    a = assess_session_support(boastful)
    assert a.self_declared_support_index == 1.0     # it said so...

    # ...and nothing in the assessment carries canonical epistemic authority.
    dumped = a.model_dump(mode="json")
    statuses = {s.value for s in EpistemicStatus}
    assert not (statuses & set(dumped))                       # no such field
    assert not (statuses & _flatten_values(dumped))           # no such value
    assert dumped["authority"] == "shadow_non_authoritative"


def _flatten_values(value):
    out = set()
    if isinstance(value, dict):
        for v in value.values():
            out |= _flatten_values(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            out |= _flatten_values(v)
    elif isinstance(value, str):
        out.add(value)
    return out


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
