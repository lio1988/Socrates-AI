"""
Phase 17 — the mathematics of epistemic discipline: Bayesian revision protocol
(Reflector), confidence-disagreement signal (variance ≠ mean ≠ content), and the
Brier-scored CalibrationLedger (proper scoring rule per seat). Offline.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AgentMove, AgentRole, AssembledAnswer, AssembledSection, DialogPhase,
    SectionDraft, SectionName, SessionState, TaskKind,
)
from backend.dialogues.reasoning_prompts import (
    build_reasoning_system_prompt, BAYESIAN_UPDATE_DIRECTIVE, CONTEXT_PROTOCOL,
)
from backend.dialogues.provider_registry import parse_and_validate_move
from backend.dialogues.self_improvement import (
    CalibrationLedger, CALIBRATION_BIAS_THRESHOLD, CALIBRATION_MIN_SAMPLES,
)
from backend.dialogues.live_providers import build_council

Q = "Is knowledge merely justified true belief?"


# ── A. Bayesian revision protocol ─────────────────────────────────────────────

def test_bayesian_directive_only_for_reflection():
    p = build_reasoning_system_prompt(AgentRole.REFLECTOR, DialogPhase.REFLECTION,
                                      TaskKind.REFLECTION_REVISION)
    assert BAYESIAN_UPDATE_DIRECTIVE.splitlines()[0] in p
    for kind in (TaskKind.SYNTHESIS_DRAFT, TaskKind.ELENCHUS_OBJECTION, TaskKind.MOVE_SCORE):
        p2 = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS, kind)
        assert BAYESIAN_UPDATE_DIRECTIVE.splitlines()[0] not in p2, kind


def test_bayesian_directive_specifies_update_semantics():
    for cue in ('"prior_confidence"', '"evidence_force"', '"posterior_confidence"',
                "decisive", "MUST equal the posterior", "calibration failure"):
        assert cue in BAYESIAN_UPDATE_DIRECTIVE, cue


def test_bayesian_directive_example_passes_validator():
    from backend.dialogues.models import AgentTask
    example = BAYESIAN_UPDATE_DIRECTIVE[BAYESIAN_UPDATE_DIRECTIVE.index('{"content"'):]
    task = AgentTask(session_id="s", agent_id="a", role=AgentRole.REFLECTOR,
                     phase=DialogPhase.REFLECTION, question="q",
                     task_kind=TaskKind.REFLECTION_REVISION)
    move, status, err = parse_and_validate_move(example, task, meta={})
    assert status.value == "ok", err
    assert move.confidence == pytest.approx(0.55)      # confidence == posterior


# ── B. confidence-disagreement signal ─────────────────────────────────────────

def _state_with_confs(ced, confs, sid="std"):
    st = SessionState(session_id=sid, question=Q)
    ced._sessions[sid] = st
    for i, c in enumerate(confs):
        st.moves.append(AgentMove(task_id="t", agent_id=f"a{i}", role=AgentRole.SYNTHESIZER,
                                  phase=DialogPhase.INITIAL_RESPONSE,
                                  content={"thesis": f"distinct position number {i} entirely"},
                                  confidence=c))
    return st


def test_high_variance_triggers_disagreement_mandate():
    ced, _ = build_council(env={}, council_size=2)
    st = _state_with_confs(ced, [0.95, 0.35])          # mean .65, std .30
    ad = ced._adaptive_dialectic(st)
    assert ad["initial_confidence_std"] == pytest.approx(0.30, abs=0.01)
    assert ad["confidence_disagreement_triggered"] is True
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "a0")
    assert "confidence_disagreement_mandate" in ctx
    assert "which premise" in ctx["confidence_disagreement_mandate"]


def test_low_variance_does_not_trigger():
    ced, _ = build_council(env={}, council_size=2)
    st = _state_with_confs(ced, [0.62, 0.68])          # std .03
    ad = ced._adaptive_dialectic(st)
    assert ad["confidence_disagreement_triggered"] is False
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "a0")
    assert "confidence_disagreement_mandate" not in ctx


def test_mean_triggers_take_precedence_over_variance():
    ced, _ = build_council(env={}, council_size=2)
    st = _state_with_confs(ced, [1.0, 0.62])           # mean .81 (devils) AND std .19<.2
    ctx = ced._registry_phase_context(st, DialogPhase.ELENCHUS, "a0")
    assert "devils_advocate_mandate" in ctx
    assert "confidence_disagreement_mandate" not in ctx


def test_new_mandate_documented_in_context_protocol():
    assert "`confidence_disagreement_mandate`" in CONTEXT_PROTOCOL


# ── C. CalibrationLedger (Brier proper scoring) ───────────────────────────────

def _session_with_outcome(conf=0.9, wins=2, total=5, seat="seatX"):
    st = SessionState(session_id="m", question=Q)
    st.moves.append(AgentMove(move_id="mv1", task_id="t", agent_id="a0",
                              role=AgentRole.SYNTHESIZER, phase=DialogPhase.SYNTHESIS,
                              content={}, confidence=conf))
    st.section_drafts = [SectionDraft(draft_id="d1", session_id="m", author_agent_id="a0",
                                      move_id="mv1", provider_id=seat,
                                      core_answer="c", crucial_stress_test="s",
                                      blind_spots="b", nuance="n", final_verdict="f")]
    st.assembled_answer = AssembledAnswer(session_id="m", sections=[
        AssembledSection(section_name=n, selected_draft_id=("d1" if i < wins else "other"),
                         selected_author_agent_id="a0", content="x", average_score=5.0)
        for i, n in enumerate(SectionName)])
    return st


def test_brier_math_is_exact():
    cal = CalibrationLedger()
    cal.ingest_session(_session_with_outcome(conf=0.9, wins=2))
    s = cal.stats()["seatX"]
    assert s.mean_outcome == pytest.approx(0.4)         # 2/5 sections won
    assert s.brier == pytest.approx((0.9 - 0.4) ** 2)   # proper scoring rule
    assert s.bias == pytest.approx(0.5)                 # overconfident by +0.5


def test_recommendations_flag_bias_with_evidence_gate():
    cal = CalibrationLedger()
    for _ in range(CALIBRATION_MIN_SAMPLES - 1):
        cal.ingest_session(_session_with_outcome(conf=0.9, wins=0))
    assert cal.recommendations() == []                  # not enough evidence yet
    cal.ingest_session(_session_with_outcome(conf=0.9, wins=0))
    recs = " | ".join(cal.recommendations())
    assert "OVERCONFIDENT" in recs and "seatX" in recs
    # underconfident direction
    cal2 = CalibrationLedger()
    for _ in range(CALIBRATION_MIN_SAMPLES):
        cal2.ingest_session(_session_with_outcome(conf=0.2, wins=5))
    assert "UNDERCONFIDENT" in " | ".join(cal2.recommendations())


def test_calibration_from_full_session_and_hidden_from_agents():
    cal = CalibrationLedger()
    ced, _ = build_council(env={}, council_size=2, calibration=cal)
    asyncio.run(ced.run_registry_session(Q, session_id="calfull"))
    assert cal.stats()                                  # populated from real assembly
    st = ced.get_session("calfull")
    for phase in (DialogPhase.ELENCHUS, DialogPhase.SYNTHESIS):
        blob = str(ced._registry_phase_context(st, phase, "agent_0")).lower()
        assert "brier" not in blob and "calibration" not in blob   # hidden


def test_calibration_persistence_round_trip(tmp_path):
    cal = CalibrationLedger()
    cal.ingest_session(_session_with_outcome())
    path = str(tmp_path / "cal.json")
    cal.save(path)
    loaded = CalibrationLedger.load(path)
    assert loaded.stats()["seatX"].brier == cal.stats()["seatX"].brier
    assert "not proof of truth" in loaded.report()["interpretation_warning"]
