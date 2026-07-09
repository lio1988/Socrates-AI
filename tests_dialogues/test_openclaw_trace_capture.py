"""
OpenClaw trace capture tests (Goal 5).

Verifies:
  - trace is captured at session-end via duck-typed .ingest_session()
  - trace contains required fields (session_id, question, moves, assembly,
    ratification, selected_openclaw_lessons, audit_keys)
  - trace NEVER contains secrets (api_key, sk-ant-, Bearer)
  - trace records selected openclaw lesson ids when lessons are enabled
  - trace can be written to a JSONL file
  - default (no trace_capturer) = unchanged behavior
  - full mock session completes with trace_capturer attached

No provider calls, no network, no keys.
"""

import asyncio
import json

import pytest

from backend.dialogues.live_providers import build_council
from backend.dialogues.models import ShadowScoringMode
from backend.dialogues.openclaw_memory import (
    TraceCapturer,
    build_session_trace,
    load_stable_lessons,
)


@pytest.fixture(scope="module")
def stable_pool():
    return load_stable_lessons()


_SID = 0


def _run_with_capturer(capturer, openclaw_lessons=None, question="Τι είναι η αλήθεια;"):
    global _SID
    _SID += 1
    sid = f"trace_test_{_SID}"
    ced, _ = build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.OFF,
        openclaw_lessons=openclaw_lessons,
        trace_capturer=capturer,
    )
    final = asyncio.run(ced.run_registry_session(question, session_id=sid))
    return final, ced.get_session(sid)


# --------------------------------------------------------------------------- #
# Trace shape and required fields
# --------------------------------------------------------------------------- #

def test_trace_captured_at_session_end():
    capturer = TraceCapturer()
    assert capturer.session_count == 0
    _run_with_capturer(capturer)
    assert capturer.session_count == 1
    trace = capturer.latest_trace()
    assert trace is not None


def test_trace_has_required_fields():
    capturer = TraceCapturer()
    _run_with_capturer(capturer)
    trace = capturer.latest_trace()
    for key in ("trace_version", "session_id", "question", "timestamp",
                "move_count", "moves", "assembly", "ratification", "audit_keys"):
        assert key in trace, f"missing trace field: {key}"
    assert trace["trace_version"] == "openclaw_trace_v0"
    assert trace["move_count"] == len(trace["moves"])
    assert isinstance(trace["moves"], list)


def test_move_summaries_have_expected_shape():
    capturer = TraceCapturer()
    _run_with_capturer(capturer)
    for move in capturer.latest_trace()["moves"]:
        assert "move_id" in move
        assert "phase" in move
        assert "role" in move
        assert "confidence" in move
        assert "content_keys" in move or "content" in move


def test_assembly_and_ratification_present():
    capturer = TraceCapturer()
    _run_with_capturer(capturer)
    trace = capturer.latest_trace()
    rat = trace["ratification"]
    assert "ratified" in rat
    assert "ratification_status" in rat


# --------------------------------------------------------------------------- #
# No secrets
# --------------------------------------------------------------------------- #

def test_trace_contains_no_secrets():
    capturer = TraceCapturer()
    _run_with_capturer(capturer)
    trace = capturer.latest_trace()
    text = json.dumps(trace, default=str)
    for forbidden in ("api_key", "ANTHROPIC_API_KEY", "sk-ant-", "Bearer "):
        assert forbidden not in text, f"trace leaked {forbidden!r}"


# --------------------------------------------------------------------------- #
# OpenClaw lesson ids appear in trace when lessons enabled
# --------------------------------------------------------------------------- #

def test_trace_records_openclaw_lesson_ids(stable_pool):
    capturer = TraceCapturer()
    _run_with_capturer(capturer, openclaw_lessons=stable_pool,
                       question="deliberation scoring assembly")
    trace = capturer.latest_trace()
    lessons = trace.get("selected_openclaw_lessons", [])
    assert isinstance(lessons, list)
    assert len(lessons) > 0
    assert all(lid.startswith("LESSON-") for lid in lessons)


def test_trace_without_lessons_has_empty_list():
    capturer = TraceCapturer()
    _run_with_capturer(capturer, openclaw_lessons=None)
    trace = capturer.latest_trace()
    assert trace.get("selected_openclaw_lessons") == []


# --------------------------------------------------------------------------- #
# File output
# --------------------------------------------------------------------------- #

def test_trace_writes_to_jsonl(tmp_path):
    capturer = TraceCapturer(output_dir=tmp_path / "traces")
    _run_with_capturer(capturer)
    trace = capturer.latest_trace()
    path = tmp_path / "traces" / f"{trace['session_id']}.jsonl"
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    loaded = json.loads(lines[0])
    assert loaded["session_id"] == trace["session_id"]


# --------------------------------------------------------------------------- #
# Include content opt-in
# --------------------------------------------------------------------------- #

def test_include_content_off_by_default():
    capturer = TraceCapturer()
    _run_with_capturer(capturer)
    for move in capturer.latest_trace()["moves"]:
        assert "content" not in move
        assert "content_keys" in move


def test_include_content_opt_in():
    capturer = TraceCapturer(include_content=True)
    _run_with_capturer(capturer)
    for move in capturer.latest_trace()["moves"]:
        assert "content" in move
        assert "content_keys" not in move


# --------------------------------------------------------------------------- #
# Default: no capturer = unchanged
# --------------------------------------------------------------------------- #

def test_default_no_capturer():
    ced, _ = build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.OFF,
    )
    assert ced.trace_capturer is None
    final = asyncio.run(ced.run_registry_session("test", session_id="no_trace"))
    assert final is not None


# --------------------------------------------------------------------------- #
# build_council passthrough
# --------------------------------------------------------------------------- #

def test_build_council_passes_trace_capturer():
    capturer = TraceCapturer()
    ced, mode = build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.OFF,
        trace_capturer=capturer,
    )
    assert ced.trace_capturer is capturer
