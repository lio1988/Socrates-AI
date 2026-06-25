"""
Phase 9A — offline-first real-provider adapter (NO real API calls).

Proves a real-shaped provider adapter plugs into CouncilProviderRegistry and the
full registry-backed session WITHOUT changing the CED protocol, using only
fixtures / canned responses. No network, no real key, no `.env`.
"""

import asyncio
import json

import pytest

from backend.dialogues.models import (
    AgentState, AgentTask, AgentRole, DialogPhase, TaskKind,
    ProviderStatus, AssembledAnswer, EpistemicLeaderboard,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.offline_provider_adapter import (
    OfflineProviderAdapter, ScriptedOfflineTransport, CannedResponseTransport,
    anthropic_text_envelope, anthropic_refusal_envelope,
    offline_scripted_adapter, offline_canned_adapter,
    OfflineTimeout, OfflineRateLimit, OfflineRefusal, OfflineTransportError,
    DEFAULT_OFFLINE_MODEL, OFFLINE_FIXTURE_KEY, is_retryable_status,
    RETRYABLE_STATUSES,
)

Q = "Is knowledge merely justified true belief?"


# ── helpers ───────────────────────────────────────────────────────────────────

def _state(agent_id="agent_0", role=AgentRole.SYNTHESIZER):
    return AgentState(agent_id=agent_id, primary_role=role, assigned_role=role)


def _task(kind, *, role=AgentRole.SYNTHESIZER, phase=DialogPhase.SYNTHESIS,
          agent_id="agent_0", context=None, output_schema=None):
    return AgentTask(
        session_id="sess_offline", agent_id=agent_id, role=role, phase=phase,
        question=Q, task_kind=kind, context=context or {}, output_schema=output_schema or {},
    )


def _move_envelope(payload, conf=0.7, model=DEFAULT_OFFLINE_MODEL):
    """Wrap a CED move payload in an Anthropic text envelope (the canned-fixture path)."""
    text = json.dumps({"content": payload, "confidence": conf})
    return anthropic_text_envelope(text, model=model)


_SCORE_PAYLOAD = {
    "epistemic_value": 7.0, "logical_rigor": 6.5, "factual_grounding": 6.0,
    "constructive_impact": 7.0, "intellectual_honesty": 8.0,
    "clarity_precision": 7.5, "grounded_creativity": 6.0,
}
_VERDICT_PAYLOAD = {"verdict": "accept", "rationale": "Meets the epistemic-discipline bar."}


def _run(coro):
    return asyncio.run(coro)


# ── (1) registers in the registry ────────────────────────────────────────────

def test_offline_adapter_registers_in_council_registry():
    reg = CouncilProviderRegistry()
    reg.register(offline_scripted_adapter("offline_a"))
    reg.register(offline_scripted_adapter("offline_b"))
    ids = [a.provider_id for a in reg.available_adapters()]
    assert ids == ["offline_a", "offline_b"]
    ready, warning = reg.assess_readiness()
    assert ready is True and warning is None


# ── (2) returns a valid ProviderResponse from a fixture ──────────────────────

def test_returns_valid_provider_response_from_fixture():
    adapter = offline_canned_adapter(
        "offline_x",
        by_task_kind={TaskKind.INITIAL_RESPONSE: _move_envelope({"text": "A grounded claim."}, 0.66)},
    )
    resp = _run(adapter.generate_agent_move(
        _task(TaskKind.INITIAL_RESPONSE, phase=DialogPhase.INITIAL_RESPONSE), _state()))
    assert resp.ok
    assert resp.status == ProviderStatus.OK
    assert resp.provider_id == "offline_x"
    assert resp.parsed_move.content == {"text": "A grounded claim."}
    assert resp.parsed_move.confidence == pytest.approx(0.66)
    assert resp.latency_ms is not None


# ── (3-6) supports every registry task kind ──────────────────────────────────

def test_supports_deliberation_output():
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.SYNTHESIS_DRAFT: _move_envelope(
            {"core_answer": "x", "crucial_stress_test": "y", "blind_spots": "z",
             "nuance": "n", "final_verdict": "v"})})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.SYNTHESIS_DRAFT), _state()))
    assert resp.ok
    assert set(resp.parsed_move.content) >= {"core_answer", "final_verdict"}


def test_supports_move_scoring_output():
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.MOVE_SCORE: _move_envelope(_SCORE_PAYLOAD)})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.MOVE_SCORE), _state()))
    assert resp.ok
    # the adapter carries the provider's score payload verbatim — it does not compute it
    assert resp.parsed_move.content == _SCORE_PAYLOAD


def test_supports_section_scoring_output():
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.SECTION_SCORE: _move_envelope(_SCORE_PAYLOAD)})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.SECTION_SCORE), _state()))
    assert resp.ok
    assert resp.parsed_move.content == _SCORE_PAYLOAD


def test_supports_council_ratification_output():
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.COUNCIL_RATIFICATION: _move_envelope(_VERDICT_PAYLOAD, 0.85)})
    resp = _run(adapter.generate_agent_move(
        _task(TaskKind.COUNCIL_RATIFICATION, phase=DialogPhase.RATIFICATION), _state()))
    assert resp.ok
    assert resp.parsed_move.content["verdict"] == "accept"


# ── (7) invalid fixture JSON / schema is honestly rejected, not accepted ─────

def test_invalid_fixture_json_is_invalid_json():
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.INITIAL_RESPONSE: anthropic_text_envelope("<<< not json >>>")})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.INITIAL_RESPONSE), _state()))
    assert resp.status == ProviderStatus.INVALID_JSON
    assert resp.parsed_move is None


def test_non_dict_content_is_schema_error():
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.INITIAL_RESPONSE:
                           anthropic_text_envelope(json.dumps({"content": "not-a-dict"}))})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.INITIAL_RESPONSE), _state()))
    assert resp.status == ProviderStatus.SCHEMA_ERROR
    assert resp.parsed_move is None


def test_json_repair_still_works_through_offline_adapter():
    # code-fenced + trailing comma → repaired, then schema-validated (not bypassed)
    fenced = "```json\n{\"content\": {\"text\": \"ok\"}, \"confidence\": 0.7,}\n```"
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.INITIAL_RESPONSE: anthropic_text_envelope(fenced)})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.INITIAL_RESPONSE), _state()))
    assert resp.ok
    assert resp.repair_attempted and resp.repair_succeeded
    assert resp.parsed_move.content == {"text": "ok"}


# ── (8) missing / failed output → honest provider status, no fabrication ──────

def test_timeout_failure_is_honest():
    adapter = offline_canned_adapter(
        "p", failures={TaskKind.MOVE_SCORE: OfflineTimeout("simulated timeout")})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.MOVE_SCORE), _state()))
    assert resp.status == ProviderStatus.TIMEOUT
    assert resp.parsed_move is None and resp.ok is False


def test_rate_limit_failure_is_honest_with_retry_after():
    adapter = offline_canned_adapter(
        "p", failures={TaskKind.INITIAL_RESPONSE: OfflineRateLimit(retry_after=12.0)})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.INITIAL_RESPONSE), _state()))
    assert resp.status == ProviderStatus.RATE_LIMITED
    assert "retry_after=12.0" in resp.error_message
    assert resp.parsed_move is None


def test_refusal_envelope_is_honest_error():
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.INITIAL_RESPONSE: anthropic_refusal_envelope()})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.INITIAL_RESPONSE), _state()))
    assert resp.status == ProviderStatus.ERROR
    assert "refusal" in resp.error_message
    assert resp.parsed_move is None


def test_fixture_miss_is_honest_error():
    adapter = offline_canned_adapter("p")   # no fixtures at all
    resp = _run(adapter.generate_agent_move(_task(TaskKind.INITIAL_RESPONSE), _state()))
    assert resp.status == ProviderStatus.ERROR
    assert resp.parsed_move is None


def test_disabled_adapter_is_missing_key():
    adapter = offline_scripted_adapter("p")
    adapter.enabled = False
    resp = _run(adapter.generate_agent_move(_task(TaskKind.INITIAL_RESPONSE), _state()))
    assert resp.status == ProviderStatus.MISSING_KEY
    assert resp.parsed_move is None


# ── (9) no CED semantic scoring is introduced by the adapter ─────────────────

def test_adapter_never_fabricates_a_score_on_failure():
    # a scoring task that fails must produce NO move (no zero-score fabrication)
    adapter = offline_canned_adapter(
        "p", failures={TaskKind.MOVE_SCORE: OfflineTimeout()})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.MOVE_SCORE), _state()))
    assert resp.parsed_move is None
    assert resp.status in RETRYABLE_STATUSES


def test_adapter_carries_score_verbatim_no_recompute():
    # the adapter returns exactly the provider's payload — it does not re-derive scores
    custom = dict(_SCORE_PAYLOAD, epistemic_value=2.5)
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.MOVE_SCORE: _move_envelope(custom)})
    resp = _run(adapter.generate_agent_move(_task(TaskKind.MOVE_SCORE), _state()))
    assert resp.parsed_move.content["epistemic_value"] == 2.5


# ── real-adapter SHAPE: request construction is faithful + minimal-awareness ──

def test_request_is_shaped_for_a_live_messages_call():
    adapter = offline_canned_adapter(
        "p", by_task_kind={TaskKind.INITIAL_RESPONSE: _move_envelope({"text": "ok"})})
    _run(adapter.generate_agent_move(
        _task(TaskKind.INITIAL_RESPONSE, role=AgentRole.SOCRATES,
              context={"a": 1}, output_schema={"_role": "synthesizer"}), _state()))
    req = adapter.last_request
    assert req.model == DEFAULT_OFFLINE_MODEL == "claude-opus-4-8"
    kwargs = req.to_messages_kwargs()
    # adaptive thinking, no temperature/top_p/budget_tokens (opus-4-8 surface)
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert set(kwargs) == {"model", "max_tokens", "system", "messages", "thinking"}
    assert "socrates" in kwargs["system"]
    # minimal awareness: the user turn only carries task-provided fields
    user = json.loads(kwargs["messages"][0]["content"])
    assert set(user) == {"question", "context", "output_schema", "task_kind"}
    assert user["context"] == {"a": 1}
    # routing metadata is NOT part of the live payload
    assert "routing" not in kwargs


def test_no_real_key_and_no_env_read():
    adapter = offline_scripted_adapter("p")
    assert adapter.api_key == OFFLINE_FIXTURE_KEY
    assert "offline" in adapter.api_key and "real" not in adapter.api_key.replace("not-a-real", "")
    assert adapter.is_available() is True          # available without a real key
    assert adapter.is_offline and adapter.is_real_shaped and adapter.is_fake
    # no "sk-...live" secret is exposed anywhere on the adapter
    assert not adapter.api_key.startswith("sk-ant-api")


def test_retryable_status_scaffolding():
    assert is_retryable_status(ProviderStatus.RATE_LIMITED)
    assert is_retryable_status(ProviderStatus.TIMEOUT)
    assert is_retryable_status(ProviderStatus.ERROR)
    assert not is_retryable_status(ProviderStatus.OK)
    assert not is_retryable_status(ProviderStatus.SCHEMA_ERROR)


# ── (10) full registry session runs through the offline adapters ─────────────

def _registry_ced(adapters):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    reg = CouncilProviderRegistry()
    for a in adapters:
        reg.register(a)
    return CEDOrchestrator(agents, provider, registry=reg)


def test_run_registry_session_with_offline_adapters():
    ced = _registry_ced([offline_scripted_adapter("offline_a"),
                         offline_scripted_adapter("offline_b")])
    final = asyncio.run(ced.run_registry_session(Q, session_id="offline-sess"))
    state = ced.get_session("offline-sess")

    assert final.ratified is True
    assert final.ratification_status == "ratified"
    assert isinstance(final.synthesis, AssembledAnswer)
    assert len(final.synthesis.sections) == 5
    assert isinstance(final.socratic_leaderboard, EpistemicLeaderboard)

    au = final.audit_summary
    assert au["execution_mode"] == "registry"
    assert au["scoring"]["scoring_backend"] == "registry"
    assert au["scoring"]["self_scoring_violations"] == 0
    # peer scoring ran through the registry providers (voters are providers)
    assert au["scoring"]["scores_collected"] > 0
    assert final.socratic_leaderboard.leaderboard_status.value == "complete"

    # no fabricated moves: failed providers (none here) would leave move_id=None
    assert any(e.move_id for e in state.task_log)   # at least some real moves recorded


def test_offline_session_quorum_failure_is_safe_fallback():
    # only one available provider < minimum 2 → safe fallback, no fake answer
    ced = _registry_ced([offline_scripted_adapter("offline_a")])
    final = asyncio.run(ced.run_registry_session(Q, session_id="offline-notready"))
    assert final.ratified is False
    assert final.synthesis is None
    assert final.answer == ""
    assert final.audit_summary["quorum_failed"] is True


# ── (11) existing mock providers still work, incl. mixed with offline ────────

def test_existing_scripted_mock_still_works():
    ced = _registry_ced([ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b")])
    final = asyncio.run(ced.run_registry_session(Q, session_id="offline-mock"))
    assert final.ratified is True


def test_offline_and_scripted_mock_can_be_mixed():
    ced = _registry_ced([offline_scripted_adapter("offline_a"),
                         ScriptedMockProvider("mock_b")])
    final = asyncio.run(ced.run_registry_session(Q, session_id="offline-mixed"))
    assert final.ratified is True
    assert isinstance(final.synthesis, AssembledAnswer)


# ── envelope helpers are faithful to the Anthropic Messages shape ────────────

def test_text_envelope_shape():
    env = anthropic_text_envelope("hi", model="claude-opus-4-8")
    assert env["type"] == "message" and env["role"] == "assistant"
    assert env["model"] == "claude-opus-4-8"
    assert env["content"][0] == {"type": "text", "text": "hi"}
    assert env["stop_reason"] == "end_turn"


def test_refusal_envelope_shape():
    env = anthropic_refusal_envelope(category="cyber")
    assert env["stop_reason"] == "refusal"
    assert env["content"] == []
    assert env["stop_details"]["category"] == "cyber"
