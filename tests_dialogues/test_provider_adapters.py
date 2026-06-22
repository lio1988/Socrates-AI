"""
Phase 8A — Provider adapter contract + registry + safe fallback (no real APIs).

Covers: registry availability/quorum, per-status provider responses, structured
output validation, fallback/quorum, audit integration, and Minimal Awareness.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AgentTask, AgentState, AgentRole, AgentMove, DialogPhase, ProviderStatus,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, parse_and_validate_move, is_placeholder_key,
    AlwaysOKProvider, TimeoutProvider, InvalidJSONProvider,
    SchemaErrorProvider, RateLimitedProvider, MissingKeyProvider,
    COUNCIL_UNAVAILABLE_WARNING,
)


def _task(agent_id="agent_0", role=AgentRole.SOCRATES, phase=DialogPhase.OPENING):
    return AgentTask(session_id="s", agent_id=agent_id, role=role, phase=phase, question="Q?")


def _state(agent_id="agent_0", role=AgentRole.SOCRATES):
    return AgentState(agent_id=agent_id, primary_role=role, assigned_role=role)


def _gen(provider):
    return asyncio.run(provider.generate_agent_move(_task(), _state()))


# ── Placeholder-key detection ─────────────────────────────────────────────────

@pytest.mark.parametrize("key", ["", "your_key_here", "changeme", "test", "placeholder", None, "  CHANGEME  "])
def test_placeholder_keys_detected(key):
    assert is_placeholder_key(key) is True


@pytest.mark.parametrize("key", ["sk-ant-real-123", "AIzaReal", "xoxb-token"])
def test_real_keys_not_placeholder(key):
    assert is_placeholder_key(key) is False


# ── Provider registry availability ────────────────────────────────────────────

def test_missing_and_placeholder_keys_are_ignored():
    reg = CouncilProviderRegistry()
    reg.register(AlwaysOKProvider())
    reg.register(MissingKeyProvider())                       # placeholder key
    reg.register(AlwaysOKProvider(api_key="changeme"))       # placeholder key
    available = [a.provider_id for a in reg.available_adapters()]
    assert available == ["mock_ok"]
    assert "mock_missing_key" in [a.provider_id for a in reg.unavailable_adapters()]


def test_available_mock_providers_are_registered():
    reg = CouncilProviderRegistry()
    reg.register(AlwaysOKProvider())
    reg.register(AlwaysOKProvider())
    assert len(reg.available_adapters()) == 2


def test_fewer_than_minimum_returns_clear_warning():
    reg = CouncilProviderRegistry()
    reg.register(AlwaysOKProvider())     # only one available
    ready, warning = reg.assess_readiness()
    assert ready is False
    assert warning == COUNCIL_UNAVAILABLE_WARNING.format(n=2)
    assert "at least 2" in warning


def test_minimum_provider_count_enforced_when_met():
    reg = CouncilProviderRegistry()
    reg.register(AlwaysOKProvider())
    reg.register(AlwaysOKProvider())
    ready, warning = reg.assess_readiness()
    assert ready is True and warning is None


# ── Provider responses per status ─────────────────────────────────────────────

def test_ok_provider_returns_valid_agent_move():
    r = _gen(AlwaysOKProvider())
    assert r.status == ProviderStatus.OK
    assert isinstance(r.parsed_move, AgentMove)
    assert r.parsed_move.role == AgentRole.SOCRATES
    assert r.parsed_move.phase == DialogPhase.OPENING
    assert r.ok is True


def test_timeout_provider_status():
    r = _gen(TimeoutProvider())
    assert r.status == ProviderStatus.TIMEOUT
    assert r.parsed_move is None and r.ok is False


def test_invalid_json_provider_status():
    r = _gen(InvalidJSONProvider())
    assert r.status == ProviderStatus.INVALID_JSON
    assert r.parsed_move is None


def test_schema_error_provider_status():
    r = _gen(SchemaErrorProvider())
    assert r.status == ProviderStatus.SCHEMA_ERROR
    assert r.parsed_move is None


def test_rate_limited_provider_status():
    r = _gen(RateLimitedProvider())
    assert r.status == ProviderStatus.RATE_LIMITED
    assert r.parsed_move is None


def test_missing_key_provider_status():
    r = _gen(MissingKeyProvider())
    assert r.status == ProviderStatus.MISSING_KEY
    assert r.parsed_move is None


# ── Structured-output validation directly ─────────────────────────────────────

def test_parse_and_validate_move_paths():
    task = _task()
    move, status, _ = parse_and_validate_move('{"content": {"x": 1}, "confidence": 0.5}', task)
    assert status == ProviderStatus.OK and move.content == {"x": 1}

    _, status, _ = parse_and_validate_move("not json", task)
    assert status == ProviderStatus.INVALID_JSON

    _, status, _ = parse_and_validate_move('{"content": "not-a-dict"}', task)
    assert status == ProviderStatus.SCHEMA_ERROR

    _, status, _ = parse_and_validate_move('{"content": {"x": 1}, "confidence": 5.0}', task)
    assert status == ProviderStatus.SCHEMA_ERROR   # confidence out of 0–1 range


# ── Fallback / quorum ─────────────────────────────────────────────────────────

def test_council_proceeds_when_one_fails_but_quorum_remains():
    reg = CouncilProviderRegistry()
    reg.register(AlwaysOKProvider())
    reg.register(AlwaysOKProvider())
    reg.register(TimeoutProvider())
    result = asyncio.run(reg.gather_council_round(_task(), _state()))
    assert result.proceed is True
    assert len(result.ok_provider_ids) == 2
    assert "mock_timeout" in result.failed_provider_ids
    assert result.warning is None


def test_council_does_not_proceed_when_quorum_not_met():
    reg = CouncilProviderRegistry()
    reg.register(AlwaysOKProvider())
    reg.register(TimeoutProvider())
    result = asyncio.run(reg.gather_council_round(_task(), _state()))
    assert result.proceed is False
    assert result.warning and "at least 2" in result.warning


def test_no_fake_move_created_for_failed_providers():
    reg = CouncilProviderRegistry()
    reg.register(AlwaysOKProvider())
    reg.register(TimeoutProvider())
    reg.register(RateLimitedProvider())
    reg.register(InvalidJSONProvider())
    result = asyncio.run(reg.gather_council_round(_task(), _state()))
    for r in result.responses:
        if not r.ok:
            assert r.parsed_move is None, f"{r.provider_id} fabricated a move"


def test_provider_failure_does_not_crash_registry():
    class ExplodingProvider(AlwaysOKProvider):
        provider_id = "mock_explode"
        async def generate_agent_move(self, task, agent_state):
            raise RuntimeError("provider blew up")

    reg = CouncilProviderRegistry()
    reg.register(AlwaysOKProvider())
    reg.register(AlwaysOKProvider())
    reg.register(ExplodingProvider())
    result = asyncio.run(reg.gather_council_round(_task(), _state()))
    assert result.proceed is True                          # 2 OK still meet quorum
    assert "mock_explode" in result.failed_provider_ids    # recorded, not crashed


# ── Audit integration (developer-visible, never on AgentState) ───────────────

def _make_ced_with_registry():
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    reg = CouncilProviderRegistry()
    reg.register(AlwaysOKProvider())
    reg.register(AlwaysOKProvider())
    reg.register(MissingKeyProvider())
    reg.register(TimeoutProvider())
    return CEDOrchestrator(agents, provider, registry=reg), reg


def test_failed_providers_recorded_in_audit_summary():
    ced, reg = _make_ced_with_registry()
    asyncio.run(reg.gather_council_round(_task(), _state()))   # populates failures
    final = ced.run_session("Is knowledge merely justified true belief?", session_id="pa-audit")

    summary = final.audit_summary.get("provider_status_summary")
    assert summary is not None
    assert "mock_timeout" in summary["failed_providers"]
    assert "mock_ok" in summary["available_providers"]
    assert "mock_missing_key" in summary["unavailable_providers"]
    assert summary["minimum_providers"] == 2


def test_registry_optional_does_not_change_default_audit():
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    ced = CEDOrchestrator(agents, provider)   # no registry
    final = ced.run_session("Q?", session_id="pa-noreg")
    assert "provider_status_summary" not in final.audit_summary


# ── Minimal Awareness ─────────────────────────────────────────────────────────

def test_agentstate_has_no_provider_status_or_failures():
    ced, _ = _make_ced_with_registry()
    ced.run_session("Q?", session_id="pa-ma")
    state = ced.get_session("pa-ma")
    for ast in state.agent_states.values():
        dumped = ast.model_dump()
        for forbidden in ("provider_status_summary", "failed_providers",
                          "available_providers", "api_key", "provider_status",
                          "unavailable_providers"):
            assert forbidden not in dumped


def test_agent_task_context_does_not_expose_provider_internals():
    ced, _ = _make_ced_with_registry()
    captured = []
    original = SocraticAgent.execute

    def capturing(self, task):
        captured.append(task)
        return original(self, task)

    import unittest.mock as mock
    with mock.patch.object(SocraticAgent, "execute", capturing):
        ced.run_session("Q?", session_id="pa-ctx")

    assert captured
    forbidden = ("api_key", "provider_status", "failed_providers",
                 "available_providers", "mock_timeout", "missing_key", "rate_limited")
    for task in captured:
        blob = (str(task.context) + " " + str(task.output_schema)).lower()
        for kw in forbidden:
            assert kw not in blob, f"'{kw}' leaked into agent task for {task.agent_id}"
