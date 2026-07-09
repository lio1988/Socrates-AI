"""
OpenClaw Memory Lessons — runtime lesson loader (Goal 1).

Reads curated behavioral lessons from the human-authored Markdown source
(``docs/openclaw_memory_lessons/MEMORY_LESSONS.md``) and returns a structured,
deterministic list of :class:`MemoryLesson` records.

Acceptance criteria (from FUTURE_GOALS.md, Goal 1):
  - deterministic parsing (file order preserved, no randomness)
  - no provider calls, no API keys, no network access
  - ignores deprecated lessons by default
  - can load only stable / verified lessons
  - invalid records fail cleanly with a clear error

Parsing is intentionally simple and self-contained: no third-party Markdown
library is used, so the loader has no runtime dependencies beyond the stdlib.

The Markdown source contains a *template* lesson (``LESSON-0000``) inside a
fenced code block. Fenced code blocks are skipped entirely, so the template is
never parsed as a real lesson.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# Canonical lesson lifecycle states (see MEMORY_LESSONS.md / README.md).
LESSON_STATUSES: tuple[str, ...] = (
    "proposed",
    "tested",
    "verified",
    "stable",
    "deprecated",
)

# Lessons trustworthy enough to influence high-stakes runs.
STABLE_OR_VERIFIED: frozenset[str] = frozenset({"stable", "verified"})

# "### LESSON-0001 — Human readable name"
# The separator may be an em dash, en dash, or hyphen.
_HEADER_RE = re.compile(r"^###\s+(LESSON-\d+)\s*(?:—|–|-)\s*(.+)$")

# "**Field label:** inline value"  (value may be empty -> block value follows)
_FIELD_RE = re.compile(r"^\*\*([^:*]+):\*\*\s*(.*)$")

# Sentinel appended to the line stream so a trailing lesson (no closing "---")
# is still flushed. Chosen to never collide with real Markdown content.
_END_SENTINEL = "\x00openclaw-end\x00"


class LessonParseError(ValueError):
    """Raised when a lesson block is malformed (missing/invalid required field)."""


@dataclass(frozen=True)
class MemoryLesson:
    """A single curated memory lesson.

    Lessons are *behavioral guidance*, not factual evidence. They are external
    and auditable; agents never own them.
    """

    lesson_id: str
    name: str
    status: str
    lesson_type: str
    source: str
    use_when: tuple[str, ...]
    problem_pattern: str
    bad_pattern: str
    good_pattern: str
    lesson: str
    risk: str

    @property
    def is_deprecated(self) -> bool:
        return self.status == "deprecated"

    @property
    def is_stable(self) -> bool:
        """True when the lesson is trustworthy enough for high-stakes runs."""
        return self.status in STABLE_OR_VERIFIED

    def to_record(self) -> dict:
        """Return a JSONL-ready dict (forward-compatible with Goal 2)."""
        return {
            "lesson_id": self.lesson_id,
            "name": self.name,
            "status": self.status,
            "lesson_type": self.lesson_type,
            "source": self.source,
            "use_when": list(self.use_when),
            "problem_pattern": self.problem_pattern,
            "bad_pattern": self.bad_pattern,
            "good_pattern": self.good_pattern,
            "lesson": self.lesson,
            "risk": self.risk,
        }


def default_lessons_path() -> Path:
    """Absolute path to the canonical MEMORY_LESSONS.md source."""
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "docs" / "openclaw_memory_lessons" / "MEMORY_LESSONS.md"


def _strip_inline_code(value: str) -> str:
    """Strip a single wrapping pair of backticks from an inline-code value."""
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        return value[1:-1].strip()
    return value


def _build_lesson(lesson_id: str, name: str, labels: dict[str, str]) -> MemoryLesson:
    status = labels.get("status", "").strip().lower()
    if status not in LESSON_STATUSES:
        raise LessonParseError(
            f"{lesson_id}: invalid or missing status {status!r} "
            f"(expected one of {LESSON_STATUSES})"
        )

    lesson_type = labels.get("lesson type", "").strip()
    if not lesson_type:
        raise LessonParseError(f"{lesson_id}: missing 'Lesson type'")

    lesson_text = labels.get("lesson", "").strip()
    if not lesson_text:
        raise LessonParseError(f"{lesson_id}: missing 'Lesson' text")

    use_when_raw = labels.get("use when", "")
    use_when = tuple(part.strip() for part in use_when_raw.split(",") if part.strip())

    return MemoryLesson(
        lesson_id=lesson_id,
        name=name.strip(),
        status=status,
        lesson_type=lesson_type,
        source=labels.get("source", "").strip(),
        use_when=use_when,
        problem_pattern=labels.get("problem pattern", "").strip(),
        bad_pattern=_strip_inline_code(labels.get("bad pattern", "").strip()),
        good_pattern=_strip_inline_code(labels.get("good pattern", "").strip()),
        lesson=lesson_text,
        risk=labels.get("risk", "").strip(),
    )


def parse_memory_lessons(text: str) -> list[MemoryLesson]:
    """Parse Markdown lesson text into an ordered list of :class:`MemoryLesson`.

    Deterministic: output order matches source order. Fenced code blocks (```)
    are skipped so the ``LESSON-0000`` template is ignored. Raises
    :class:`LessonParseError` on a malformed lesson block.
    """
    lessons: list[MemoryLesson] = []
    header: Optional[tuple[str, str]] = None
    labels: dict[str, str] = {}
    field: Optional[str] = None
    buf: list[str] = []
    in_fence = False

    for raw in text.splitlines() + [_END_SENTINEL]:
        stripped = raw.strip()
        is_end = stripped == _END_SENTINEL

        if not is_end and stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        header_match = None if is_end else _HEADER_RE.match(stripped)
        is_separator = stripped == "---"
        field_match = None if is_end else _FIELD_RE.match(stripped)

        # Any boundary line first commits the pending field value.
        boundary = is_end or is_separator or header_match is not None or field_match is not None
        if boundary and field is not None:
            labels[field] = " ".join(buf).strip()
            field = None
            buf = []

        # A header, separator, or EOF closes the current lesson (if any).
        if header_match is not None or is_separator or is_end:
            if header is not None:
                lessons.append(_build_lesson(header[0], header[1], labels))
            header = None
            labels = {}
            if header_match is not None:
                header = (header_match.group(1), header_match.group(2))
            continue

        if header is None:
            # Prose/headings before the first lesson (e.g. rules, template intro).
            continue

        if field_match is not None:
            field = field_match.group(1).strip().lower()
            inline = field_match.group(2).strip()
            buf = [inline] if inline else []
            continue

        if field is not None and stripped:
            buf.append(stripped)

    return lessons


def load_memory_lessons(
    path: Optional[Path | str] = None,
    *,
    statuses: Optional[Iterable[str]] = None,
    include_deprecated: bool = False,
) -> list[MemoryLesson]:
    """Load lessons from ``MEMORY_LESSONS.md`` (or ``path``).

    Filtering:
      - ``statuses`` given  -> authoritative allow-list (case-insensitive);
        ``include_deprecated`` is ignored in this case.
      - ``statuses`` is None -> keep everything except ``deprecated`` unless
        ``include_deprecated=True``.

    No network access, no provider calls, no API keys. Deterministic order.
    """
    source = Path(path) if path is not None else default_lessons_path()
    text = source.read_text(encoding="utf-8")
    lessons = parse_memory_lessons(text)

    if statuses is not None:
        wanted = {s.strip().lower() for s in statuses}
        return [lesson for lesson in lessons if lesson.status in wanted]

    if not include_deprecated:
        return [lesson for lesson in lessons if lesson.status != "deprecated"]

    return lessons


def load_stable_lessons(path: Optional[Path | str] = None) -> list[MemoryLesson]:
    """Convenience: load only ``stable`` / ``verified`` lessons."""
    return load_memory_lessons(path, statuses=STABLE_OR_VERIFIED)
