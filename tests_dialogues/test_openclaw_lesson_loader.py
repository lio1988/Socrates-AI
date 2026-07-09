"""
OpenClaw Memory Lessons — runtime lesson loader tests (Goal 1).

These tests verify deterministic Markdown parsing and clean-failure behavior
only. They do not train models, call providers, touch the network, or require
API keys.
"""

import inspect
from pathlib import Path

import pytest

from backend.dialogues.openclaw_memory import lesson_loader
from backend.dialogues.openclaw_memory import (
    LESSON_STATUSES,
    STABLE_OR_VERIFIED,
    LessonParseError,
    MemoryLesson,
    default_lessons_path,
    load_memory_lessons,
    load_stable_lessons,
    parse_memory_lessons,
)


# --------------------------------------------------------------------------- #
# Fixtures — small, self-contained Markdown so parsing is tested in isolation.
# --------------------------------------------------------------------------- #

FIXTURE = """\
# Memory Lessons fixture

## Lesson template

```markdown
### LESSON-0000 — Short name

**Status:** proposed | tested | verified | stable | deprecated
**Lesson type:** exact_output | unsupported_claim
**Lesson:** template placeholder that must never be parsed
```

## Verified / stable lessons

### LESSON-0001 — Exact output means exact output

**Status:** stable
**Lesson type:** exact_output
**Source:** Proof Sprint mini evidence fixture
**Use when:** exact text tasks, uncertainty tokens, numeric-only output

**Problem pattern:**
The agent explains even though only one exact token was requested.

**Bad pattern:**
`The answer is insufficient_information because there is not enough evidence.`

**Good pattern:**
`insufficient_information`

**Lesson:**
When a task asks for an exact token, return only the requested output.

**Risk:**
May make answers too terse if injected into open-ended tasks.

---

### LESSON-0002 — Agreement is not proof

**Status:** verified
**Lesson type:** synthesis_quality
**Source:** CED architectural invariant
**Use when:** synthesis, ratification

**Lesson:**
Agreement between agents is useful signal, but not proof.

**Risk:**
May cause excessive skepticism if used without synthesis guidance.

---

## Proposed lessons

### LESSON-0009 — Retrieval before fine-tuning

**Status:** proposed
**Lesson type:** memory_usage
**Source:** OpenClaw local learning design
**Use when:** local LLM integration

**Lesson:**
Start with trace memory and retrieval injection before fine-tuning.

**Risk:**
Retrieval alone may not fix deep model weaknesses.

---

### LESSON-0099 — Old deprecated lesson

**Status:** deprecated
**Lesson type:** provider_behavior
**Source:** historical

**Lesson:**
This lesson is no longer used and should be filtered by default.

**Risk:**
None.
"""


def _by_id(lessons):
    return {lesson.lesson_id: lesson for lesson in lessons}


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

def test_template_in_fenced_block_is_ignored():
    lessons = parse_memory_lessons(FIXTURE)
    ids = [lesson.lesson_id for lesson in lessons]
    assert "LESSON-0000" not in ids
    assert ids == ["LESSON-0001", "LESSON-0002", "LESSON-0009", "LESSON-0099"]


def test_parse_full_fields_exactly():
    lesson = _by_id(parse_memory_lessons(FIXTURE))["LESSON-0001"]
    assert lesson.name == "Exact output means exact output"
    assert lesson.status == "stable"
    assert lesson.lesson_type == "exact_output"
    assert lesson.source == "Proof Sprint mini evidence fixture"
    assert lesson.problem_pattern.startswith("The agent explains")
    assert lesson.lesson.startswith("When a task asks for an exact token")
    assert lesson.risk.startswith("May make answers too terse")


def test_use_when_split_into_tuple():
    lesson = _by_id(parse_memory_lessons(FIXTURE))["LESSON-0001"]
    assert lesson.use_when == (
        "exact text tasks",
        "uncertainty tokens",
        "numeric-only output",
    )


def test_bad_and_good_pattern_backticks_stripped():
    lesson = _by_id(parse_memory_lessons(FIXTURE))["LESSON-0001"]
    assert lesson.good_pattern == "insufficient_information"
    assert lesson.bad_pattern.startswith("The answer is insufficient_information")
    assert "`" not in lesson.good_pattern
    assert "`" not in lesson.bad_pattern


def test_minimal_lesson_without_patterns_parses():
    lesson = _by_id(parse_memory_lessons(FIXTURE))["LESSON-0002"]
    assert lesson.status == "verified"
    assert lesson.bad_pattern == ""
    assert lesson.good_pattern == ""
    assert lesson.problem_pattern == ""
    assert lesson.lesson.startswith("Agreement between agents")


def test_parsing_is_deterministic():
    first = parse_memory_lessons(FIXTURE)
    second = parse_memory_lessons(FIXTURE)
    assert first == second


def test_is_stable_property():
    lessons = _by_id(parse_memory_lessons(FIXTURE))
    assert lessons["LESSON-0001"].is_stable is True   # stable
    assert lessons["LESSON-0002"].is_stable is True   # verified
    assert lessons["LESSON-0009"].is_stable is False  # proposed
    assert lessons["LESSON-0099"].is_deprecated is True


def test_to_record_shape():
    record = _by_id(parse_memory_lessons(FIXTURE))["LESSON-0001"].to_record()
    assert record["lesson_id"] == "LESSON-0001"
    assert record["status"] == "stable"
    assert record["lesson_type"] == "exact_output"
    assert isinstance(record["use_when"], list)
    assert record["use_when"][0] == "exact text tasks"


# --------------------------------------------------------------------------- #
# Clean failure
# --------------------------------------------------------------------------- #

def test_invalid_status_fails_cleanly():
    bad = "### LESSON-0500 — Bad status\n\n**Status:** totally-made-up\n**Lesson type:** x\n**Lesson:** y\n"
    with pytest.raises(LessonParseError) as excinfo:
        parse_memory_lessons(bad)
    assert "LESSON-0500" in str(excinfo.value)


def test_missing_lesson_text_fails_cleanly():
    bad = "### LESSON-0501 — No lesson body\n\n**Status:** stable\n**Lesson type:** x\n**Risk:** none\n"
    with pytest.raises(LessonParseError) as excinfo:
        parse_memory_lessons(bad)
    assert "LESSON-0501" in str(excinfo.value)
    assert "Lesson" in str(excinfo.value)


def test_missing_lesson_type_fails_cleanly():
    bad = "### LESSON-0502 — No type\n\n**Status:** stable\n**Lesson:** something\n"
    with pytest.raises(LessonParseError):
        parse_memory_lessons(bad)


# --------------------------------------------------------------------------- #
# Filtering / loading from the real file
# --------------------------------------------------------------------------- #

def test_deprecated_filtered_by_default(tmp_path):
    path = tmp_path / "lessons.md"
    path.write_text(FIXTURE, encoding="utf-8")
    lessons = load_memory_lessons(path)
    ids = {lesson.lesson_id for lesson in lessons}
    assert "LESSON-0099" not in ids  # deprecated dropped
    assert "LESSON-0001" in ids


def test_include_deprecated_opt_in(tmp_path):
    path = tmp_path / "lessons.md"
    path.write_text(FIXTURE, encoding="utf-8")
    ids = {lesson.lesson_id for lesson in load_memory_lessons(path, include_deprecated=True)}
    assert "LESSON-0099" in ids


def test_statuses_allowlist_is_authoritative(tmp_path):
    path = tmp_path / "lessons.md"
    path.write_text(FIXTURE, encoding="utf-8")
    stable = load_memory_lessons(path, statuses=STABLE_OR_VERIFIED)
    assert {lesson.lesson_id for lesson in stable} == {"LESSON-0001", "LESSON-0002"}
    assert all(lesson.is_stable for lesson in stable)

    load_stable = load_stable_lessons(path)
    assert load_stable == stable


def test_real_memory_lessons_file_loads():
    path = default_lessons_path()
    assert path.exists(), f"expected canonical lessons file at {path}"

    all_lessons = load_memory_lessons(path)
    ids = [lesson.lesson_id for lesson in all_lessons]

    # Template must be excluded; the 10 real lessons must be present.
    assert "LESSON-0000" not in ids
    for n in range(1, 11):
        assert f"LESSON-{n:04d}" in ids, f"missing LESSON-{n:04d}"

    # Deterministic, unique, valid statuses.
    assert len(ids) == len(set(ids)), "duplicate lesson ids"
    assert all(lesson.status in LESSON_STATUSES for lesson in all_lessons)

    # No deprecated leak by default (there are none today, but guard the rule).
    assert all(not lesson.is_deprecated for lesson in all_lessons)


def test_real_file_known_lesson_content():
    lessons = _by_id(load_memory_lessons())
    l1 = lessons["LESSON-0001"]
    assert l1.status == "stable"
    assert l1.lesson_type == "exact_output"
    assert l1.good_pattern == "insufficient_information"

    l10 = lessons["LESSON-0010"]
    assert l10.status == "proposed"
    assert l10.lesson_type == "ratification_quality"


# --------------------------------------------------------------------------- #
# Invariant: loader is offline and secret-free (source scan).
# --------------------------------------------------------------------------- #

def test_loader_has_no_network_or_secret_dependencies():
    source = inspect.getsource(lesson_loader)
    forbidden = (
        "import requests",
        "import urllib",
        "import httpx",
        "import anthropic",
        "import openai",
        "socket",
        "api_key",
        "ANTHROPIC_API_KEY",
        "os.environ",
    )
    for token in forbidden:
        assert token not in source, f"loader must not reference {token!r}"
