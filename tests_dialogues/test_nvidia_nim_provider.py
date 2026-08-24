"""
Phase 26A/B — NVIDIA NIM provider adapter + mixed-provider council selection.

All tests are offline: no NVIDIA calls, no Anthropic calls, no keys, no .env.
They verify the adapter contract and the registry builder wiring only.
"""

import asyncio
import json

import pytest

from backend.dialogues.live_providers import (
    FLAG_ENV,
    KEY_ENV,
    NVIDIA_KEY_ENV,
    NVIDIA_MODELS_ENV,
    PROVIDER_FAMILIES_ENV,
    build_council_registry,
)
from backend.dialogues.models import (
    AgentRole,
    AgentState,
    AgentTask,
    DialogPhase,
    ProviderStatus,
    TaskKind,
)
from backend.dialogues.nvidia_nim_provider import (
    CannedNvidiaNIMTransport,
    LiveNvidiaNIMAdapter,
    NvidiaNIMRateLimit,
    NvidiaNIMTimeout,
    nvidia_chat_envelope,
)
from backend.dialogues.live_providers import LiveAnthropicAdapter
from backend.dialogues.provider_registry import ScriptedMockProvider
from backend.dialogues.reasoning_prompts import REASONING_PROTOCOL

FAKE_NVIDIA_KEY = "nvapi-FAKE-not-a-real-key-000000"
FAKE_ANTHROPIC_KEY = "sk-ant-FAKE-not-a-real-key-000000"


def _task(kind=TaskKind.SYNTHESIS_DRAFT):
    return AgentTask(
        session_id="s",
        agent_id="agent_0",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.SYNTHESIS,
        question="Is knowledge merely justified true belief?",
        task_kind=kind,
        output_schema={"type": "object"},
    )


def _state():
    return AgentState(
        agent_id="agent_0",
        primary_role=AgentRole.SYNTHESIZER,
        assigned_role=AgentRole.SYNTHESIZER,
    )


def _adapter(envelope=None, failure=None, key=FAKE_NVIDIA_KEY):
    return LiveNvidiaNIMAdapter(
        "nvidia_seat0",
        key,
        model="nvidia/test-model",
        transport=CannedNvidiaNIMTransport(envelope=envelope, failure=failure),
        retry_delay_seconds=0.0,
    )


# ── adapter contract ─────────────────────────────────────────────────────────

def test_nvidia_adapter_missing_or_placeholder_key_is_honest():
    adapter = _adapter(key="your_key_here")
    resp = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert resp.status == ProviderStatus.MISSING_KEY
    assert resp.parsed_move is None


def test_nvidia_request_carries_full_reasoning_prompt_and_schema_context():
    adapter = _adapter(envelope=nvidia_chat_envelope(json.dumps({
        "content": {"text": "ok"}, "confidence": 0.7,
    })))
    req = adapter._build_request(_task(), _state())
    payload = req.to_chat_completions_payload()
    assert REASONING_PROTOCOL.splitlines()[0] in payload["messages"][0]["content"]
    user_payload = json.loads(payload["messages"][1]["content"])
    assert user_payload["task_kind"] == TaskKind.SYNTHESIS_DRAFT.value
    assert user_payload["output_schema"] == {"type": "object"}
    assert "score" not in user_payload


def test_nvidia_valid_envelope_parses_through_existing_registry_validation():
    adapter = _adapter(envelope=nvidia_chat_envelope(json.dumps({
        "content": {"text": "NVIDIA seat response",
                    "epistemic_marker": "reasonable_hypothesis"},
        "confidence": 0.72,
    })))
    resp = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert resp.status == ProviderStatus.OK
    assert resp.parsed_move is not None
    assert resp.parsed_move.content["text"] == "NVIDIA seat response"
    assert adapter.last_request is not None and adapter.last_envelope is not None


def test_nvidia_invalid_json_is_rejected_not_fabricated():
    adapter = _adapter(envelope=nvidia_chat_envelope("<<< not json >>>"))
    resp = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert resp.status == ProviderStatus.INVALID_JSON
    assert resp.parsed_move is None


def test_nvidia_schema_error_is_rejected_not_fabricated():
    adapter = _adapter(envelope=nvidia_chat_envelope(json.dumps({
        "content": "not an object", "confidence": 0.7,
    })))
    resp = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert resp.status == ProviderStatus.SCHEMA_ERROR
    assert resp.parsed_move is None


@pytest.mark.parametrize("failure,status", [
    (NvidiaNIMRateLimit("rate limited"), ProviderStatus.RATE_LIMITED),
    (NvidiaNIMTimeout("timed out"), ProviderStatus.TIMEOUT),
])
def test_nvidia_transient_failures_are_honest_statuses(failure, status):
    adapter = _adapter(failure=failure)
    resp = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert resp.status == status
    assert resp.parsed_move is None


def test_nvidia_adapter_construction_makes_no_network_call():
    adapter = LiveNvidiaNIMAdapter("seat", FAKE_NVIDIA_KEY, model="nvidia/test-model")
    assert adapter.last_request is None
    assert adapter.last_envelope is None


# ── mixed provider registry ──────────────────────────────────────────────────

def test_legacy_behavior_is_unchanged_when_provider_families_absent():
    reg, mode = build_council_registry(env={})
    assert mode == "mock"
    assert all(isinstance(a, ScriptedMockProvider) for a in reg.all_adapters())

    reg2, mode2 = build_council_registry(env={FLAG_ENV: "1", KEY_ENV: FAKE_ANTHROPIC_KEY}, council_size=2)
    assert mode2 == "live"
    assert all(isinstance(a, LiveAnthropicAdapter) for a in reg2.all_adapters())


def test_provider_families_without_live_flag_falls_back_to_mock():
    reg, mode = build_council_registry(env={PROVIDER_FAMILIES_ENV: "nvidia,nvidia"})
    assert mode == "mock"
    assert len(reg.all_adapters()) == 2
    assert all(isinstance(a, ScriptedMockProvider) for a in reg.all_adapters())


def test_mixed_registry_can_register_nvidia_and_mock_seats_without_calling():
    env = {
        FLAG_ENV: "1",
        PROVIDER_FAMILIES_ENV: "nvidia,mock,nvidia",
        NVIDIA_KEY_ENV: FAKE_NVIDIA_KEY,
        NVIDIA_MODELS_ENV: "nvidia/model-a,nvidia/model-b",
    }
    reg, mode = build_council_registry(env=env)
    adapters = reg.all_adapters()
    assert mode == "mixed"
    assert isinstance(adapters[0], LiveNvidiaNIMAdapter)
    assert isinstance(adapters[1], ScriptedMockProvider)
    assert isinstance(adapters[2], LiveNvidiaNIMAdapter)
    assert adapters[0].model == "nvidia/model-a"
    assert adapters[2].model == "nvidia/model-b"
    assert adapters[0].last_request is None and adapters[2].last_request is None


def test_mixed_registry_missing_nvidia_key_keeps_nvidia_seat_unavailable():
    env = {FLAG_ENV: "1", PROVIDER_FAMILIES_ENV: "nvidia,mock"}
    reg, mode = build_council_registry(env=env)
    assert mode == "mixed"
    adapters = reg.all_adapters()
    assert isinstance(adapters[0], LiveNvidiaNIMAdapter)
    assert not adapters[0].is_available()
    ready, warning = reg.assess_readiness()
    assert ready is False and warning


def test_unknown_provider_family_raises_clear_error():
    env = {FLAG_ENV: "1", PROVIDER_FAMILIES_ENV: "nvidia,alien", NVIDIA_KEY_ENV: FAKE_NVIDIA_KEY}
    with pytest.raises(ValueError, match="Unknown provider family"):
        build_council_registry(env=env)
