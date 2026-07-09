"""
OpenClaw Memory Lessons — agent context injection tests (Goal 4).

Verifies the Goal 4 acceptance criteria:
  - agents receive selected lessons only
  - agents do not receive raw scorecards
  - agents do not receive full unrelated history
  - existing CED role rotation stays unchanged

No provider calls, no network, no keys.
"""

import inspect
import io
import json
import tokenize

import pytest

from backend.dialogues.models import AgentRole, AgentTask, DialogPhase, TaskKind
from backend.dialogues.openclaw_memory import (
    MEMORY_LESSONS_CONTEXT_KEY,
    MEMORY_LESSONS_HEADER,
    MEMORY_LESSONS_TEXT_KEY,
    MemoryLesson,
    build_memory_lessons_context,
    inject_memory_lessons,
    load_stable_lessons,
    render_memory_lessons_block,
    retrieve_for_task,
    select_and_inject,
    select_lessons_for_task,
)
from backend.dialogues.openclaw_memory import context_injection


def _task(**overrides):
    base = dict(
        session_id="sess-1",
        agent_id="agent-1",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.SYNTHESIS,
        question="Assemble the strongest final answer.",
        task_kind=TaskKind.SYNTHESIS_DRAFT,
        context={"allowed_history": ["prior move summary"]},
    )
    base.update(overrides)
    return AgentTask(**base)


def _lessons(*ids):
    by_id = {lesson.lesson_id: lesson for lesson in load_stable_lessons()}
    return [by_id[i] for i in ids]


# --------------------------------------------------------------------------- #
# Rendering + payload
# --------------------------------------------------------------------------- #

def test_render_block_format():
    block = render_memory_lessons_block(_lessons("LESSON-0001", "LESSON-0003"))
    lines = block.splitlines()
    assert lines[0] == MEMORY_LESSONS_HEADER
    assert lines[1].startswith("- LESSON-0001: ")
    assert lines[2].startswith("- LESSON-0003: ")


def test_render_block_empty_selection():
    assert render_memory_lessons_block([]) == ""


def test_payload_is_guidance_only_no_scores():
    payload = build_memory_lessons_context(_lessons("LESSON-0001"))
    entry = payload[MEMORY_LESSONS_CONTEXT_KEY][0]
    assert set(entry.keys()) == {"lesson_id", "lesson_type", "lesson"}
    # no retrieval internals or scores leak into the agent-facing payload
    assert "relevance_score" not in entry
    assert "match_reasons" not in entry
    assert "confidence" not in entry


def test_payload_accepts_retrieved_lessons():
    retrieved = retrieve_for_task(role=AgentRole.EMPIRICIST)
    payload = build_memory_lessons_context(retrieved)
    assert payload[MEMORY_LESSONS_CONTEXT_KEY]
    text = json.dumps(payload)
    assert "relevance_score" not in text
    assert "match_reasons" not in text


# --------------------------------------------------------------------------- #
# Injection
# --------------------------------------------------------------------------- #

def test_inject_adds_keys_and_preserves_context():
    task = _task()
    out = inject_memory_lessons(task, _lessons("LESSON-0002", "LESSON-0006"))
    assert MEMORY_LESSONS_CONTEXT_KEY in out.context
    assert MEMORY_LESSONS_TEXT_KEY in out.context
    # unrelated context preserved
    assert out.context["allowed_history"] == ["prior move summary"]
    assert out.context[MEMORY_LESSONS_TEXT_KEY].startswith(MEMORY_LESSONS_HEADER)


def test_inject_does_not_change_role_or_routing():
    task = _task()
    out = inject_memory_lessons(task, _lessons("LESSON-0002"))
    assert out.role == task.role
    assert out.phase == task.phase
    assert out.task_kind == task.task_kind
    assert out.question == task.question
    assert out.session_id == task.session_id
    assert out.agent_id == task.agent_id


def test_inject_is_non_mutating():
    task = _task()
    original_context = dict(task.context)
    inject_memory_lessons(task, _lessons("LESSON-0002"))
    # original task untouched
    assert task.context == original_context
    assert MEMORY_LESSONS_CONTEXT_KEY not in task.context


def test_inject_empty_returns_task_unchanged():
    task = _task()
    out = inject_memory_lessons(task, [])
    assert MEMORY_LESSONS_CONTEXT_KEY not in out.context


def test_injected_context_has_no_score_or_history_leak():
    task = _task()
    out = inject_memory_lessons(task, retrieve_for_task(role=AgentRole.SYNTHESIZER))
    dumped = json.dumps(out.context)
    for forbidden in ("relevance_score", "match_reasons", "scorecard", "leaderboard", "peer_score"):
        assert forbidden not in dumped


# --------------------------------------------------------------------------- #
# End-to-end selection + injection
# --------------------------------------------------------------------------- #

def test_select_lessons_uses_task_fields():
    task = _task()  # synthesizer / synthesis / synthesis_draft
    retrieved = select_lessons_for_task(task)
    ids = {r.lesson_id for r in retrieved}
    assert {"LESSON-0002", "LESSON-0006"} <= ids


def test_select_and_inject_end_to_end():
    task = _task()
    out = select_and_inject(task)
    block = out.context[MEMORY_LESSONS_TEXT_KEY]
    assert "LESSON-0002" in block
    assert "LESSON-0006" in block
    # role rotation untouched
    assert out.role == AgentRole.SYNTHESIZER


def test_select_and_inject_with_no_matches_is_noop():
    # final_evaluator maps only to ratification_quality, whose only lesson
    # (LESSON-0010) is *proposed* and thus absent from the stable pool.
    task = _task(
        role=AgentRole.FINAL_EVALUATOR,
        phase=DialogPhase.COMPLETE,
        question="unrelated small talk about the weather",
        task_kind=None,
    )
    out = select_and_inject(task)
    assert MEMORY_LESSONS_CONTEXT_KEY not in out.context


# --------------------------------------------------------------------------- #
# Invariant: injection code touches no scores / leaderboard / network.
# --------------------------------------------------------------------------- #

def _code_identifiers(module):
    source = inspect.getsource(module)
    names = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.NAME:
            names.add(tok.string)
    return names


def test_injection_has_no_score_or_network_dependencies():
    names = _code_identifiers(context_injection)
    forbidden = (
        "leaderboard",
        "scorecard",
        "peer_score",
        "SectionScore",
        "requests",
        "anthropic",
        "environ",
        "api_key",
    )
    for token in forbidden:
        assert token not in names, f"injection code must not reference {token!r}"
