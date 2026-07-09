"""
OpenClaw Memory Lessons — runtime layer (v0).

This subpackage is the first *runtime* step of the OpenClaw Memory Lessons
layer documented in ``docs/openclaw_memory_lessons/``. It gives the system a
way to load curated, external, auditable *behavioral lessons* that can later be
selectively injected into otherwise stateless agent calls.

Design invariants (see docs/openclaw_memory_lessons/README.md):

  - It does NOT change the CED core, role rotation, or scoring.
  - Agents do not own memory; the system owns memory and lends lessons.
  - Lessons are guidance, not hidden factual evidence.
  - No provider calls, no API keys, no network access happen here.

Goal 1 of the roadmap (``FUTURE_GOALS.md``) is the runtime lesson loader,
implemented in :mod:`backend.dialogues.openclaw_memory.lesson_loader`.
"""

from .lesson_loader import (
    LESSON_STATUSES,
    STABLE_OR_VERIFIED,
    LessonParseError,
    MemoryLesson,
    default_lessons_path,
    load_memory_lessons,
    load_stable_lessons,
    parse_memory_lessons,
)
from .lesson_retriever import (
    DEFAULT_MAX_LESSONS,
    RetrievedLesson,
    retrieve_for_task,
    retrieve_lessons,
    score_lesson,
)

__all__ = [
    "LESSON_STATUSES",
    "STABLE_OR_VERIFIED",
    "LessonParseError",
    "MemoryLesson",
    "default_lessons_path",
    "load_memory_lessons",
    "load_stable_lessons",
    "parse_memory_lessons",
    "DEFAULT_MAX_LESSONS",
    "RetrievedLesson",
    "retrieve_for_task",
    "retrieve_lessons",
    "score_lesson",
]
