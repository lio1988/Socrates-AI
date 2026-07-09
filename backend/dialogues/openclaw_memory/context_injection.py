"""
OpenClaw Memory Lessons — agent context injection (Goal 4).

Injects the *selected* memory lessons into an ``AgentTask.context`` as a clearly
labeled block, so a stateless agent receives focused behavioral guidance for the
current call — and nothing else.

Rule (README.md / FUTURE_GOALS.md Goal 4):

    Agents do not own memory.
    Agents receive selected lessons for the current call.

What the agent sees is deliberately sanitized to *guidance only*:

  - each lesson's id, lesson_type, and lesson text
  - a rendered "Relevant memory lessons:" block for the prompt

What the agent never sees through this path:

  - relevance scores or match reasons (retrieval internals, audit-only)
  - peer scorecards, leaderboards, or any epistemic scores
  - unrelated memory history

Injection is opt-in and non-mutating: it returns a copy of the task with the
two OpenClaw-owned context keys set, leaving every other field — role, phase,
task_kind, question — untouched. CED role rotation is not affected.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, Union

from backend.dialogues.models import AgentTask

from .lesson_loader import MemoryLesson
from .lesson_retriever import (
    DEFAULT_MAX_LESSONS,
    RetrievedLesson,
    retrieve_for_task,
)

# OpenClaw-owned context keys. Injection only ever writes these two.
MEMORY_LESSONS_CONTEXT_KEY = "memory_lessons"
MEMORY_LESSONS_TEXT_KEY = "memory_lessons_block"
MEMORY_LESSONS_HEADER = "Relevant memory lessons:"

LessonLike = Union[MemoryLesson, RetrievedLesson]


def _as_lesson(item: LessonLike) -> MemoryLesson:
    """Accept either a raw MemoryLesson or a RetrievedLesson wrapper."""
    if isinstance(item, RetrievedLesson):
        return item.lesson
    return item


def render_memory_lessons_block(lessons: Sequence[LessonLike]) -> str:
    """Render selected lessons as a labeled, prompt-ready text block.

    Returns "" for an empty selection so nothing is injected.
    """
    items = [_as_lesson(item) for item in lessons]
    if not items:
        return ""
    lines = [MEMORY_LESSONS_HEADER]
    for lesson in items:
        text = " ".join(lesson.lesson.split())
        lines.append(f"- {lesson.lesson_id}: {text}")
    return "\n".join(lines)


def build_memory_lessons_context(lessons: Sequence[LessonLike]) -> dict:
    """Build the sanitized, agent-facing context payload for the lessons.

    Structured entries carry only id / lesson_type / lesson text — never
    relevance scores or match reasons.
    """
    items = [_as_lesson(item) for item in lessons]
    structured = [
        {
            "lesson_id": lesson.lesson_id,
            "lesson_type": lesson.lesson_type,
            "lesson": lesson.lesson,
        }
        for lesson in items
    ]
    return {
        MEMORY_LESSONS_CONTEXT_KEY: structured,
        MEMORY_LESSONS_TEXT_KEY: render_memory_lessons_block(items),
    }


def inject_memory_lessons(task: AgentTask, lessons: Sequence[LessonLike]) -> AgentTask:
    """Return a copy of ``task`` with the selected lessons added to context.

    Non-mutating: the original task is untouched. Only the two OpenClaw-owned
    context keys are written; all other context keys and every other task field
    (role, phase, task_kind, question, ...) are preserved. An empty selection
    injects nothing and returns the task unchanged.
    """
    items = [_as_lesson(item) for item in lessons]
    if not items:
        return task
    new_context = dict(task.context)
    new_context.update(build_memory_lessons_context(items))
    return task.model_copy(update={"context": new_context})


def select_lessons_for_task(
    task: AgentTask,
    *,
    lessons: Optional[Sequence[MemoryLesson]] = None,
    max_lessons: int = DEFAULT_MAX_LESSONS,
    failure_tags: Iterable = (),
) -> list[RetrievedLesson]:
    """Retrieve relevant lessons using the task's own role / phase / kind / text.

    Returns the audit-rich RetrievedLesson list (with scores + reasons) for
    tracing; the agent-facing injection is sanitized separately.
    """
    return retrieve_for_task(
        task_text=task.question,
        role=task.role,
        phase=task.phase,
        task_kind=task.task_kind,
        failure_tags=failure_tags,
        max_lessons=max_lessons,
        lessons=lessons,
    )


def select_and_inject(
    task: AgentTask,
    *,
    lessons: Optional[Sequence[MemoryLesson]] = None,
    max_lessons: int = DEFAULT_MAX_LESSONS,
    failure_tags: Iterable = (),
) -> AgentTask:
    """One-shot: select relevant lessons for the task and inject them.

    Defaults to the stable/verified lesson pool (via retrieve_for_task).
    """
    retrieved = select_lessons_for_task(
        task,
        lessons=lessons,
        max_lessons=max_lessons,
        failure_tags=failure_tags,
    )
    return inject_memory_lessons(task, retrieved)
