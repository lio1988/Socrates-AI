"""
PART 7 — minimal, safe JSON repair pass (behind json_repair_attempts).
"""

import asyncio

import pytest

from backend.dialogues.models import AgentTask, AgentRole, DialogPhase, ProviderStatus
from backend.dialogues.provider_registry import (
    parse_and_validate_move, BaseProviderAdapter,
)


def _task():
    return AgentTask(session_id="s", agent_id="a0", role=AgentRole.SOCRATES,
                     phase=DialogPhase.OPENING, question="Q?")


# ── Direct validation paths ──────────────────────────────────────────────────

def test_valid_json_no_repair():
    meta = {}
    move, status, _ = parse_and_validate_move('{"content": {"x": 1}}', _task(), meta=meta)
    assert status == ProviderStatus.OK and move is not None
    assert meta["repair_attempted"] is False


def test_trailing_comma_is_repaired():
    meta = {}
    move, status, _ = parse_and_validate_move('{"content": {"x": 1},}', _task(), meta=meta)
    assert status == ProviderStatus.OK
    assert meta["repair_attempted"] and meta["repair_succeeded"]


def test_code_fence_is_repaired():
    meta = {}
    move, status, _ = parse_and_validate_move('```json\n{"content": {"x": 1}}\n```',
                                              _task(), meta=meta)
    assert status == ProviderStatus.OK
    assert meta["repair_succeeded"]


def test_hopeless_json_fails_cleanly():
    meta = {}
    move, status, _ = parse_and_validate_move("<<< not json >>>", _task(), meta=meta)
    assert status == ProviderStatus.INVALID_JSON and move is None
    assert meta["repair_attempted"] and not meta["repair_succeeded"]


def test_repaired_json_still_must_pass_schema():
    # parses after repair, but `content` is missing → schema error, not a free pass
    move, status, _ = parse_and_validate_move('{"nope": 1,}', _task())
    assert status == ProviderStatus.SCHEMA_ERROR and move is None


def test_repair_disabled():
    move, status, _ = parse_and_validate_move('{"content": {"x": 1},}', _task(),
                                              repair_attempts=0)
    assert status == ProviderStatus.INVALID_JSON


# ── Provider response carries repair metadata ────────────────────────────────

class _TrailingCommaProvider(BaseProviderAdapter):
    provider_id = "mock_trailing"
    provider_name = "Mock Trailing Comma"
    is_fake = True

    def __init__(self):
        super().__init__(api_key="sk-fake-tc")

    async def _produce_raw_text(self, task, agent_state):
        return '{"content": {"text": "ok"}, "confidence": 0.7,}'   # trailing comma


def test_provider_response_records_repair():
    p = _TrailingCommaProvider()
    resp = asyncio.run(p.generate_agent_move(_task(), agent_state=None))
    assert resp.status == ProviderStatus.OK
    assert resp.repair_attempted and resp.repair_succeeded
    assert resp.parsed_move is not None
