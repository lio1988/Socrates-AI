"""
OpenClaw → CED runtime wiring tests.

Verifies that when openclaw_lessons is provided to CEDOrchestrator:
  - deliberation tasks receive memory lessons in their context
  - judging tasks (scoring, ratification) do NOT receive memory lessons
  - agents never see relevance_scores, match_reasons, or scorecards
  - default (openclaw_lessons=None) is byte-for-byte unchanged
  - audit records which lessons were selected (CED-owned, hidden from agents)
  - a full mock session still passes (ratified or not) with lessons enabled
"""

import asyncio
import json

import pytest

from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.live_providers import build_council
from backend.dialogues.models import (
    AgentRole,
    DialogPhase,
    ShadowScoringMode,
    SessionState,
    TaskKind,
)
from backend.dialogues.openclaw_memory import (
    MEMORY_LESSONS_HEADER,
    load_stable_lessons,
)


@pytest.fixture(scope="module")
def stable_pool():
    return load_stable_lessons()


def _build(openclaw_lessons=None, **kw):
    ced, mode = build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.OFF,
        openclaw_lessons=openclaw_lessons,
        **kw,
    )
    ced.debug_task_log = True
    return ced, mode


_SID = 0

DELIBERATION_PHASES = {
    DialogPhase.OPENING, DialogPhase.INITIAL_RESPONSE, DialogPhase.ELENCHUS,
    DialogPhase.REFLECTION, DialogPhase.RECONSTRUCTION, DialogPhase.SYNTHESIS,
}

JUDGING_KINDS = {
    TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE,
    TaskKind.COUNCIL_RATIFICATION,
    TaskKind.RATIFICATION_INITIAL, TaskKind.RATIFICATION_REVISION,
    TaskKind.RATIFICATION_FINAL,
}


def _run(ced, question="Τι είναι η αλήθεια;"):
    global _SID
    _SID += 1
    sid = f"test_openclaw_{_SID}"
    final = asyncio.run(ced.run_registry_session(question, session_id=sid))
    return final, ced.get_session(sid)


def _ctx_str(entry):
    """Serialize the debug_context of a TaskLogEntry to JSON."""
    ctx = entry.debug_context or {}
    return json.dumps(ctx, default=str)


# --------------------------------------------------------------------------- #
# Default: no lessons → unchanged
# --------------------------------------------------------------------------- #

def test_default_no_lessons_unchanged():
    ced, _ = _build()
    final, state = _run(ced)
    for entry in state.task_log:
        s = _ctx_str(entry)
        assert "openclaw_memory_lessons" not in s
        assert MEMORY_LESSONS_HEADER not in s
    audit = final.audit_summary or {}
    assert audit.get("openclaw_lessons") is None


# --------------------------------------------------------------------------- #
# With lessons: present in deliberation, absent from judging
# --------------------------------------------------------------------------- #

def test_lessons_injected_into_deliberation(stable_pool):
    ced, _ = _build(openclaw_lessons=stable_pool)
    final, state = _run(ced)

    deliberation_tasks = [e for e in state.task_log if e.phase in DELIBERATION_PHASES]
    assert deliberation_tasks, "expected at least one deliberation task"

    found_lessons = False
    for entry in deliberation_tasks:
        ctx = entry.debug_context or {}
        if "openclaw_memory_lessons" in ctx:
            found_lessons = True
            block = ctx["openclaw_memory_lessons"]
            assert block.startswith(MEMORY_LESSONS_HEADER)
            assert "LESSON-" in block
    assert found_lessons, "no deliberation task received openclaw lessons"


def test_lessons_absent_from_judging_tasks(stable_pool):
    ced, mode = build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.SYNTHESIS_ONLY,
        openclaw_lessons=stable_pool,
    )
    ced.debug_task_log = True
    final, state = _run(ced)

    judging_tasks = [e for e in state.task_log if e.task_kind in JUDGING_KINDS]
    for entry in judging_tasks:
        s = _ctx_str(entry)
        assert "openclaw_memory_lessons" not in s, (
            f"judging task {entry.task_kind} must not see lessons"
        )


# --------------------------------------------------------------------------- #
# No score / match_reason leak into agent context
# --------------------------------------------------------------------------- #

def test_no_relevance_leak(stable_pool):
    ced, _ = _build(openclaw_lessons=stable_pool)
    final, state = _run(ced)
    for entry in state.task_log:
        s = _ctx_str(entry)
        for forbidden in ("relevance_score", "match_reasons", "scorecard", "leaderboard"):
            assert forbidden not in s


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #

def test_audit_records_selected_lessons(stable_pool):
    ced, _ = _build(openclaw_lessons=stable_pool)
    final, state = _run(ced)
    audit = final.audit_summary or {}
    oc = audit.get("openclaw_lessons")
    assert oc is not None
    assert oc["enabled"] is True
    assert oc["pool_size"] == len(stable_pool)
    assert isinstance(oc["selected"], list)
    assert all(lid.startswith("LESSON-") for lid in oc["selected"])


# --------------------------------------------------------------------------- #
# Full session still works
# --------------------------------------------------------------------------- #

def test_full_session_completes_with_lessons(stable_pool):
    ced, _ = _build(openclaw_lessons=stable_pool)
    final, state = _run(ced, question="What is the nature of evidence?")
    assert final is not None
    assert final.synthesis is not None or final.ratification_status is not None


# --------------------------------------------------------------------------- #
# build_council passthrough
# --------------------------------------------------------------------------- #

def test_build_council_passes_openclaw_lessons(stable_pool):
    ced, mode = build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.OFF,
        openclaw_lessons=stable_pool,
    )
    assert ced.openclaw_lessons is stable_pool
    assert mode in ("mock", "live")
