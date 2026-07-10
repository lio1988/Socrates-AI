"""Tests for exact curated Memory lesson binding."""

import dataclasses

import pytest

from backend.dialogues.openclaw_memory import (
    MemoryLesson,
    load_lesson_fingerprints,
    load_stable_lesson_fingerprints,
    memory_lesson_fingerprint,
)


def _lesson():
    return MemoryLesson(
        lesson_id="LESSON-0007",
        name="Exact-output discipline",
        status="stable",
        lesson_type="behavioral",
        source="test",
        use_when=("synthesis", "exact output"),
        problem_pattern="Rushes exact-output tasks.",
        bad_pattern="Ignore exact constraints.",
        good_pattern="Check every exact constraint.",
        lesson="Verify every exact-output constraint before finalizing.",
        risk="May over-constrain open-ended tasks.",
    )


def _catalogue():
    return """# Test catalogue

### LESSON-0007 — Exact-output discipline

**Status:** stable
**Lesson type:** behavioral
**Source:** test
**Use when:** synthesis
**Problem pattern:** Rushes.
**Bad pattern:** Ignore constraints.
**Good pattern:** Check constraints.
**Lesson:** Verify constraints.
**Risk:** Over-constraint.

---

### LESSON-0008 — Retired guidance

**Status:** deprecated
**Lesson type:** behavioral
**Source:** test
**Use when:** review
**Problem pattern:** Old pattern.
**Bad pattern:** Old bad.
**Good pattern:** Old good.
**Lesson:** Old lesson retained for rollback audit.
**Risk:** Deprecated.

---
"""


def test_memory_lesson_fingerprint_is_deterministic_sha256():
    lesson = _lesson()
    first = memory_lesson_fingerprint(lesson)
    second = memory_lesson_fingerprint(lesson)

    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


def test_every_governed_lesson_field_changes_the_fingerprint():
    lesson = _lesson()
    baseline = memory_lesson_fingerprint(lesson)

    variants = (
        dataclasses.replace(lesson, status="verified"),
        dataclasses.replace(lesson, lesson="Changed guidance."),
        dataclasses.replace(lesson, risk="Changed risk."),
        dataclasses.replace(lesson, use_when=("synthesis",)),
        dataclasses.replace(lesson, source="different source"),
    )
    assert all(memory_lesson_fingerprint(value) != baseline for value in variants)


def test_memory_lesson_fingerprint_refuses_untyped_records():
    with pytest.raises(ValueError, match="requires a MemoryLesson"):
        memory_lesson_fingerprint({"lesson_id": "LESSON-0007"})


def test_complete_map_includes_deprecated_for_governed_unlink(tmp_path):
    path = tmp_path / "MEMORY_LESSONS.md"
    path.write_text(_catalogue(), encoding="utf-8")

    complete = load_lesson_fingerprints(path)
    stable = load_stable_lesson_fingerprints(path)

    assert set(complete) == {"LESSON-0007", "LESSON-0008"}
    assert set(stable) == {"LESSON-0007"}
    assert all(len(value) == 64 for value in complete.values())
