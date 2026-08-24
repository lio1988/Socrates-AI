"""
Phase 18 — the honesty vocabulary made machine-readable: epistemic markers lift
into moves on the live path, marker↔confidence consistency is checked
mechanically (recorded, never rewritten), role exemplars show the FORM of an
excellent move, and the pre-mortem closes the reasoning protocol. Offline.
"""

import asyncio
import json

import pytest

from backend.dialogues.models import (
    AgentMove, AgentRole, AgentTask, DialogPhase, EpistemicMarker, SessionState, TaskKind,
)
from backend.dialogues.provider_registry import parse_and_validate_move
from backend.dialogues.reasoning_prompts import (
    build_reasoning_system_prompt, EPISTEMIC_MARKER_DIRECTIVE,
    MARKER_CONFIDENCE_BANDS, ROLE_EXEMPLARS, REASONING_PROTOCOL,
)
from backend.dialogues.live_providers import build_council

Q = "Is knowledge merely justified true belief?"


def _task(kind=TaskKind.INITIAL_RESPONSE):
    return AgentTask(session_id="s", agent_id="a", role=AgentRole.SYNTHESIZER,
                     phase=DialogPhase.INITIAL_RESPONSE, question="q", task_kind=kind)


# ── marker extraction on the live path ────────────────────────────────────────

def test_marker_lifted_from_content():
    raw = json.dumps({"content": {"thesis": "x", "epistemic_marker": "reasonable_hypothesis"},
                      "confidence": 0.7})
    move, status, _ = parse_and_validate_move(raw, _task(), meta={})
    assert status.value == "ok"
    assert [m.value for m in move.epistemic_markers] == ["reasonable_hypothesis"]
    assert move.content["epistemic_marker"] == "reasonable_hypothesis"   # content kept intact


def test_invalid_or_missing_required_marker_rejects():
    for content in (
        {"thesis": "x", "epistemic_marker": "nonsense"},
        {"thesis": "x", "epistemic_marker": 3},
        {"thesis": "x"},
    ):
        move, status, error = parse_and_validate_move(
            json.dumps({"content": content, "confidence": 0.7}), _task(), meta={})
        assert status.value == "schema_error" and move is None
        assert "epistemic_marker" in error


def test_marker_on_evaluative_task_is_rejected_as_wrong_contract():
    move, status, error = parse_and_validate_move(
        json.dumps({"content": {
            "score": 8,
            "epistemic_marker": "reasonable_hypothesis",
        }, "confidence": 0.7}),
        _task(TaskKind.MOVE_SCORE),
        meta={},
    )
    assert status.value == "schema_error" and move is None
    assert "not permitted" in error


def test_evaluative_task_without_marker_remains_valid_envelope():
    move, status, error = parse_and_validate_move(
        json.dumps({"content": {"score": 8}, "confidence": 0.7}),
        _task(TaskKind.MOVE_SCORE),
        meta={},
    )
    assert status.value == "ok" and error is None
    assert move.epistemic_markers == []


# ── bands ↔ enum alignment + directive contract ───────────────────────────────

def test_bands_cover_the_enum_exactly():
    assert set(MARKER_CONFIDENCE_BANDS) == {e.value for e in EpistemicMarker}
    # ceilings are monotone: stronger epistemic status → higher allowed confidence
    assert (MARKER_CONFIDENCE_BANDS["established_fact"]
            > MARKER_CONFIDENCE_BANDS["reasonable_hypothesis"]
            > MARKER_CONFIDENCE_BANDS["unsubstantiated_claim"])


def test_marker_directive_names_all_values_and_ceilings():
    for e in EpistemicMarker:
        assert f'"{e.value}"' in EPISTEMIC_MARKER_DIRECTIVE, e.value
    assert "MUST respect the ceiling" in EPISTEMIC_MARKER_DIRECTIVE


def test_marker_directive_and_exemplar_deliberation_only():
    p = build_reasoning_system_prompt(AgentRole.ELENCHUS_CRITIC, DialogPhase.ELENCHUS,
                                      TaskKind.ELENCHUS_OBJECTION)
    assert EPISTEMIC_MARKER_DIRECTIVE.splitlines()[0] in p
    assert ROLE_EXEMPLARS[AgentRole.ELENCHUS_CRITIC] in p
    for kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE, TaskKind.COUNCIL_RATIFICATION):
        pj = build_reasoning_system_prompt(AgentRole.FINAL_EVALUATOR, DialogPhase.RATIFICATION, kind)
        assert EPISTEMIC_MARKER_DIRECTIVE.splitlines()[0] not in pj, kind
        assert "imitate the FORM" not in pj, kind


# ── exemplars: every role has the form of excellence ──────────────────────────

def test_every_role_has_an_exemplar():
    for role in AgentRole:
        assert role in ROLE_EXEMPLARS and len(ROLE_EXEMPLARS[role]) > 50, role


def test_premortem_closes_the_protocol():
    assert "Pre-mortem" in REASONING_PROTOCOL
    assert "never ship a move you" in REASONING_PROTOCOL


# ── marker↔confidence consistency (mechanical; recorded, never rewritten) ─────

def _ced():
    ced, _ = build_council(env={}, council_size=2)
    return ced


def _move(conf, marker=None):
    m = AgentMove(task_id="t", agent_id="a", role=AgentRole.SYNTHESIZER,
                  phase=DialogPhase.SYNTHESIS, content={}, confidence=conf)
    if marker:
        m.epistemic_markers = [marker]
    return m


def test_consistency_catches_violation_exactly():
    ced = _ced()
    st = SessionState(session_id="ec", question=Q)
    st.moves.append(_move(0.9, EpistemicMarker.UNSUBSTANTIATED_CLAIM))   # ceiling 0.40
    st.moves.append(_move(0.95, EpistemicMarker.ESTABLISHED_FACT))       # fine
    st.moves.append(_move(0.99))                                          # untagged → ignored
    ec = ced._epistemic_consistency(st)
    assert ec["moves_tagged"] == 2 and ec["violation_count"] == 1
    v = ec["violations"][0]
    assert v["marker"] == "unsubstantiated_claim" and v["ceiling"] == 0.40


def test_boundary_confidence_is_not_a_violation():
    ced = _ced()
    st = SessionState(session_id="ec2", question=Q)
    st.moves.append(_move(0.75, EpistemicMarker.REASONABLE_HYPOTHESIS))  # exactly at ceiling
    assert ced._epistemic_consistency(st)["violation_count"] == 0


def test_full_session_audits_epistemic_consistency():
    ced = _ced()
    final = asyncio.run(ced.run_registry_session(Q, session_id="ecfull"))
    ec = final.audit_summary["epistemic_consistency"]
    assert set(ec) == {"moves_tagged", "violations", "violation_count"}
    # the mock's Socratic opening is tagged — the vocabulary flows end-to-end
    assert ec["moves_tagged"] >= 1
