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
    _, state = _run_with_capturer(capturer)
    trace = capturer.latest_trace()
    assert len(trace["moves"]) == len(state.moves)
    for captured, accepted in zip(trace["moves"], state.moves):
        assert captured["content"] == accepted.content
        assert captured["content"] is not accepted.content
        assert "content_keys" not in captured

    before = json.dumps(trace["moves"][0]["content"], sort_keys=True)
    state.moves[0].content["post_capture_mutation"] = "must not enter trace"
    assert json.dumps(trace["moves"][0]["content"], sort_keys=True) == before

    nested = next(
        (index, key, value)
        for index, move in enumerate(state.moves)
        for key, value in move.content.items()
        if isinstance(value, list)
    )
    nested_index, nested_key, nested_value = nested
    nested_before = json.dumps(
        trace["moves"][nested_index]["content"][nested_key],
        sort_keys=True,
    )
    nested_value.append({"post_capture": "must not enter nested trace content"})
    assert json.dumps(
        trace["moves"][nested_index]["content"][nested_key],
        sort_keys=True,
    ) == nested_before


def test_include_content_excludes_private_provider_and_ced_state(tmp_path):
    harmless = TraceCapturer()
    final, state = _run_with_capturer(harmless)
    provider_raw = "Bearer private-provider-token-12345678"
    provider_error = "PRIVATE_PROVIDER_ERROR_SENTINEL"
    request_payload = "PRIVATE_REQUEST_PAYLOAD_SENTINEL"
    hidden_score = "PRIVATE_PEER_SCORE_SENTINEL"
    rejected_move_content = "PRIVATE_REJECTED_MOVE_SENTINEL"
    assert state.registry_rounds and state.registry_rounds[0].responses
    assert state.task_log
    state.registry_rounds[0].responses[0].raw_text = provider_raw
    state.registry_rounds[0].responses[0].error_message = provider_error
    state.task_log[0].debug_context = {"request_payload": request_payload}
    final.audit_summary["private_peer_score"] = hidden_score

    rejected_move = state.moves[0].model_copy(deep=True)
    rejected_move.move_id = "move_rejected_private"
    rejected_move.content = {"question": rejected_move_content}
    rejected_response = state.registry_rounds[0].responses[0].model_copy(deep=True)
    rejected_response.provider_id = "provider_rejected_private"
    rejected_response.parsed_move = rejected_move
    state.registry_rounds[0].responses.append(rejected_response)

    capturer = TraceCapturer(
        output_dir=tmp_path / "traces",
        include_content=True,
    )
    trace = capturer.ingest_session(state, final)
    path = tmp_path / "traces" / f"{state.session_id}.jsonl"
    persisted = json.loads(path.read_text(encoding="utf-8").strip())
    for artifact in (trace, persisted):
        encoded = json.dumps(artifact, default=str)
        for private_value in (
            provider_raw,
            provider_error,
            request_payload,
            hidden_score,
            rejected_move_content,
        ):
            assert private_value not in encoded
        for private_field in (
            '"raw_text"',
            '"error_message"',
            '"debug_context"',
            '"registry_rounds"',
            '"task_log"',
        ):
            assert private_field not in encoded
        assert all(set(move) <= {
            "move_id",
            "phase",
            "role",
            "confidence",
            "provider_id",
            "task_kind",
            "content",
        } for move in artifact["moves"])
    assert [move["content"] for move in trace["moves"]] == [
        move.content for move in state.moves
    ]
    assert [move["move_id"] for move in trace["moves"]] == [
        move.move_id for move in state.moves
    ]


def test_include_content_secret_refusal_precedes_memory_and_disk_mutation(tmp_path):
    harmless = TraceCapturer()
    final, state = _run_with_capturer(harmless)
    state.moves[0].content["public_text"] = "Bearer private-token-12345678"
    output_dir = tmp_path / "traces"
    capturer = TraceCapturer(
        output_dir=output_dir,
        include_content=True,
    )

    with pytest.raises(ValueError, match="trace refused because secret-shaped data"):
        capturer.ingest_session(state, final)

    assert capturer.traces == []
    assert not output_dir.exists()


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
