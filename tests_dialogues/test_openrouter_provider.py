import asyncio
import json

import pytest

from backend.dialogues.agent import CORE_AGENT_PROMPT
from backend.dialogues.live_providers import (
    FLAG_ENV,
    OPENROUTER_KEY_ENV,
    OPENROUTER_MODELS_ENV,
    PROVIDER_FAMILIES_ENV,
    build_council_registry,
)
from backend.dialogues.models import AgentRole, AgentState, AgentTask, DialogPhase, ProviderStatus, TaskKind
from backend.dialogues import openrouter_provider as openrouter_module
from backend.dialogues.openrouter_provider import DEFAULT_OPENROUTER_MODEL, OpenRouterProviderAdapter
from backend.dialogues.provider_registry import ScriptedMockProvider
from backend.dialogues.reasoning_prompts import (
    PHASE_REASONING,
    REASONING_PROTOCOL,
    ROLE_REASONING,
)


def _task():
    return AgentTask(
        task_id="task_openrouter_test",
        session_id="session_openrouter_test",
        agent_id="agent_openrouter_test",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.INITIAL_RESPONSE,
        task_kind=TaskKind.INITIAL_RESPONSE,
        question="q",
        context={},
        output_schema={},
    )


def _state():
    return AgentState(
        agent_id="agent_openrouter_test",
        primary_role=AgentRole.SYNTHESIZER,
        assigned_role=AgentRole.SYNTHESIZER,
    )


def _adapter(model="vendor/model"):
    return OpenRouterProviderAdapter(
        provider_id="openrouter_test",
        model_id=model,
        api_key="sk-test-real-looking",
    )


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    adapter = OpenRouterProviderAdapter(provider_id="or", model_id="vendor/model", api_key=None)
    response = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert response.status == ProviderStatus.MISSING_KEY


def test_exact_model_and_valid_move(monkeypatch):
    adapter = _adapter()

    async def fake_request(task, state):
        return {
            "id": "resp_1",
            "model": "vendor/model",
            "choices": [{"message": {"content": json.dumps({"content": {"text": "ok"}, "confidence": 0.8})}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }

    monkeypatch.setattr(adapter, "_request", fake_request)
    response = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert response.status == ProviderStatus.OK
    assert response.parsed_move is not None
    assert adapter.last_receipt["requested_model"] == "vendor/model"
    assert adapter.last_receipt["returned_model"] == "vendor/model"
    assert adapter.last_receipt["verified_exact_model"] is True


def test_model_substitution_is_rejected(monkeypatch):
    adapter = _adapter()

    async def fake_request(task, state):
        return {
            "id": "resp_2",
            "model": "other/model",
            "choices": [{"message": {"content": json.dumps({"content": {"text": "wrong"}, "confidence": 0.8})}}],
        }

    monkeypatch.setattr(adapter, "_request", fake_request)
    response = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert response.status == ProviderStatus.ERROR
    assert response.parsed_move is None
    assert adapter.last_receipt["verified_exact_model"] is False


def test_rate_limit_maps_to_provider_status(monkeypatch):
    adapter = _adapter()

    async def fake_request(task, state):
        raise RuntimeError("rate_limited")

    monkeypatch.setattr(adapter, "_request", fake_request)
    response = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert response.status == ProviderStatus.RATE_LIMITED


def test_invalid_content_fails_closed(monkeypatch):
    adapter = _adapter()

    async def fake_request(task, state):
        return {"id": "resp_3", "model": "vendor/model", "choices": []}

    monkeypatch.setattr(adapter, "_request", fake_request)
    response = asyncio.run(adapter.generate_agent_move(_task(), _state()))
    assert response.status == ProviderStatus.INVALID_JSON
    assert response.parsed_move is None


def test_transport_delivers_canonical_prompt_kernel_and_devil_mandate(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def text(self):
            return json.dumps({
                "id": "resp_prompt_delivery",
                "model": "vendor/model",
                "choices": [{"message": {"content": json.dumps({
                    "content": {"objection": "The consensus assumes its conclusion."},
                    "confidence": 0.81,
                })}}],
            })

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, body=json)
            return FakeResponse()

    monkeypatch.setattr(openrouter_module.aiohttp, "ClientSession", FakeSession)
    mandate = "Construct the strongest case against the emerging consensus."
    task = AgentTask(
        task_id="task_prompt_delivery",
        session_id="session_prompt_delivery",
        agent_id="agent_prompt_delivery",
        role=AgentRole.ELENCHUS_CRITIC,
        phase=DialogPhase.ELENCHUS,
        task_kind=TaskKind.ELENCHUS_OBJECTION,
        question="q",
        context={"devils_advocate_mandate": mandate},
        output_schema={},
    )
    state = AgentState(
        agent_id=task.agent_id,
        primary_role=AgentRole.SYNTHESIZER,
        assigned_role=AgentRole.ELENCHUS_CRITIC,
    )

    response = asyncio.run(_adapter().generate_agent_move(task, state))

    assert response.status == ProviderStatus.OK
    system_message = captured["body"]["messages"][0]["content"]
    user_message = captured["body"]["messages"][1]["content"]
    assert CORE_AGENT_PROMPT[:40] in system_message
    assert REASONING_PROTOCOL.splitlines()[0] in system_message
    assert ROLE_REASONING[AgentRole.ELENCHUS_CRITIC] in system_message
    assert PHASE_REASONING[DialogPhase.ELENCHUS] in system_message
    assert '"devils_advocate_mandate"' in user_message
    assert mandate in user_message


def test_model_and_provider_id_are_required():
    with pytest.raises(ValueError):
        OpenRouterProviderAdapter(provider_id="", model_id="vendor/model", api_key="k")
    with pytest.raises(ValueError):
        OpenRouterProviderAdapter(provider_id="or", model_id="", api_key="k")


# ── mixed provider registry (OpenRouter as a council family) ─────────────────

def test_openrouter_family_registers_seats_without_calling():
    env = {
        FLAG_ENV: "1",
        PROVIDER_FAMILIES_ENV: "openrouter,mock,openrouter",
        OPENROUTER_KEY_ENV: "sk-or-v1-fake-not-a-real-key",
        OPENROUTER_MODELS_ENV: "vendor/model-a,vendor/model-b",
    }
    registry, mode = build_council_registry(env=env)
    adapters = registry.all_adapters()
    assert mode == "mixed"
    assert isinstance(adapters[0], OpenRouterProviderAdapter)
    assert isinstance(adapters[1], ScriptedMockProvider)
    assert isinstance(adapters[2], OpenRouterProviderAdapter)
    assert adapters[0].model_id == "vendor/model-a"
    assert adapters[2].model_id == "vendor/model-b"
    assert adapters[0].model == "vendor/model-a"
    assert adapters[2].model == "vendor/model-b"
    # Registration must never touch the network.
    assert adapters[0].last_receipt is None
    assert adapters[2].last_receipt is None


def test_openrouter_family_defaults_model_when_unset():
    env = {
        FLAG_ENV: "1",
        PROVIDER_FAMILIES_ENV: "openrouter",
        OPENROUTER_KEY_ENV: "sk-or-v1-fake-not-a-real-key",
    }
    registry, _ = build_council_registry(env=env)
    assert registry.all_adapters()[0].model_id == DEFAULT_OPENROUTER_MODEL
    assert registry.all_adapters()[0].model == DEFAULT_OPENROUTER_MODEL


def test_openrouter_family_without_live_flag_falls_back_to_mock():
    registry, mode = build_council_registry(
        env={PROVIDER_FAMILIES_ENV: "openrouter,openrouter"})
    assert mode == "mock"
    assert all(isinstance(a, ScriptedMockProvider) for a in registry.all_adapters())


def test_openrouter_seat_without_key_is_unavailable_not_fabricated():
    env = {FLAG_ENV: "1", PROVIDER_FAMILIES_ENV: "openrouter"}
    registry, mode = build_council_registry(env=env)
    adapter = registry.all_adapters()[0]
    assert mode == "mixed"
    assert isinstance(adapter, OpenRouterProviderAdapter)
    assert adapter.is_available() is False


def test_openrouter_seat_uses_the_configured_registry_timeout():
    env = {
        FLAG_ENV: "1",
        PROVIDER_FAMILIES_ENV: "openrouter",
        OPENROUTER_KEY_ENV: "sk-or-v1-fake-not-a-real-key",
        "CED_LIVE_TIMEOUT": "175",
    }
    registry, _ = build_council_registry(env=env)
    assert registry.all_adapters()[0].timeout_seconds == 175.0
