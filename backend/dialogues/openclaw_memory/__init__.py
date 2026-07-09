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
from .context_injection import (
    MEMORY_LESSONS_CONTEXT_KEY,
    MEMORY_LESSONS_HEADER,
    MEMORY_LESSONS_TEXT_KEY,
    build_memory_lessons_context,
    inject_memory_lessons,
    render_memory_lessons_block,
    select_and_inject,
    select_lessons_for_task,
)
from .trace_capture import (
    TraceCapturer,
    build_session_trace,
)
from .lesson_proposer import (
    DEFAULT_MIN_OCCURRENCES,
    PROPOSAL_ID_START,
    aggregate_failures,
    detect_trace_failures,
    propose_from_capturer,
    propose_lessons,
    render_proposed_lessons,
    write_proposed_lessons,
)
from .lesson_ab import (
    AB_SCHEMA_VERSION,
    run_lesson_ab,
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
    "MEMORY_LESSONS_CONTEXT_KEY",
    "MEMORY_LESSONS_TEXT_KEY",
    "MEMORY_LESSONS_HEADER",
    "build_memory_lessons_context",
    "inject_memory_lessons",
    "render_memory_lessons_block",
    "select_and_inject",
    "select_lessons_for_task",
    "TraceCapturer",
    "build_session_trace",
    "DEFAULT_MIN_OCCURRENCES",
    "PROPOSAL_ID_START",
    "aggregate_failures",
    "detect_trace_failures",
    "propose_from_capturer",
    "propose_lessons",
    "render_proposed_lessons",
    "write_proposed_lessons",
    "AB_SCHEMA_VERSION",
    "run_lesson_ab",
]
