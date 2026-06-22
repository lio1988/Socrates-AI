"""
Phase 8B — Registry-backed mock council execution path.

Proves the CED can drive a multi-provider council round through
CouncilProviderRegistry (quorum, timeout/error handling, structured-output
validation, audit metadata) WITHOUT real API calls and WITHOUT replacing the
existing run_session()/FakeProvider path.
"""

import asyncio

import pytest

from backend.dialogues.models import (
    AgentRole, AgentMove, DialogPhase, ProviderStatus, CouncilRoundResult,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, BaseProviderAdapter,
    AlwaysOKProvider, TimeoutProvider, MissingKeyProvider,
)


def _ced(*adapters, n_agents: int = 4):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n_agents)]
    reg = CouncilProviderRegistry()
    for a in adapters:
        reg.register(a)
    ced = CEDOrchestrator(agents, provider, registry=reg)
    ced.create_session("Is knowledge merely justified true belief?", session_id="rc")
    return ced, reg


def _round(ced, **kw):
    return asyncio.run(ced.run_registry_council_round(
        "rc", "agent_0", AgentRole.SOCRATES, DialogPhase.OPENING, **kw))


# ── Multi-provider round proceeds with quorum (one provider fails) ───────────

def test_council_round_proceeds_with_quorum():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider(), TimeoutProvider())
    result = _round(ced)
    assert result.proceed is True
    assert len(result.ok_provider_ids) == 2
    assert "mock_timeout" in result.failed_provider_ids


def test_validated_moves_are_agent_moves():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider())
    result = _round(ced)
    ok = [r for r in result.responses if r.ok]
    assert ok
    for r in ok:
        assert isinstance(r.parsed_move, AgentMove)
        assert r.parsed_move.role == AgentRole.SOCRATES
        assert r.parsed_move.phase == DialogPhase.OPENING
        assert r.status == ProviderStatus.OK


# ── Quorum not met → no proceed, no fabricated moves ─────────────────────────

def test_council_round_does_not_proceed_without_quorum():
    ced, _ = _ced(AlwaysOKProvider(), TimeoutProvider())
    result = _round(ced)
    assert result.proceed is False
    assert result.warning and "at least 2" in result.warning
    assert all(r.parsed_move is None for r in result.responses if not r.ok)


def test_no_fabricated_move_for_any_failed_provider():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider(), TimeoutProvider())
    result = _round(ced)
    for r in result.responses:
        if r.status != ProviderStatus.OK:
            assert r.parsed_move is None


# ── Readiness gate (fewer than minimum providers) ────────────────────────────

def test_not_ready_returns_warning_without_calling_providers():
    ced, _ = _ced(AlwaysOKProvider())   # only one available < minimum 2
    result = _round(ced)
    assert result.proceed is False
    assert result.warning and "at least 2" in result.warning
    assert result.responses == []       # providers not even invoked


# ── Real per-provider timeout handling (asyncio.wait_for path) ───────────────

class _SleepyProvider(BaseProviderAdapter):
    provider_id = "mock_sleepy"
    provider_name = "Mock Sleepy"
    is_fake = True

    def __init__(self):
        super().__init__(api_key="sk-fake-sleepy")

    async def generate_agent_move(self, task, agent_state):
        await asyncio.sleep(5.0)   # exceeds the round timeout → real TimeoutError
        return await super().generate_agent_move(task, agent_state)


def test_real_timeout_is_recorded_not_crashing():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider(), _SleepyProvider())
    result = _round(ced, timeout_seconds=0.1)
    assert result.proceed is True                       # 2 OK still meet quorum
    sleepy = next(r for r in result.responses if r.provider_id == "mock_sleepy")
    assert sleepy.status == ProviderStatus.TIMEOUT
    assert sleepy.parsed_move is None


# ── Audit metadata ───────────────────────────────────────────────────────────

def test_registry_round_audit_metadata():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider(), TimeoutProvider(), MissingKeyProvider())
    result = _round(ced)
    audit = ced.registry_round_audit(result)
    assert audit["proceed"] is True
    assert audit["validated_moves"] == 2
    assert audit["provider_status_counts"]["ok"] == 2
    assert audit["provider_status_counts"]["timeout"] == 1
    assert "mock_timeout" in audit["failed_providers"]
    # provider_status_summary (developer-visible) present and key-free
    summ = audit["provider_status_summary"]
    assert "mock_missing_key" in summ["unavailable_providers"]
    assert "api_key" not in str(audit).lower()


def test_rounds_recorded_on_session():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider())
    _round(ced)
    _round(ced)
    state = ced.get_session("rc")
    assert len(state.registry_rounds) == 2
    assert all(isinstance(r, CouncilRoundResult) for r in state.registry_rounds)


# ── Guards / regression ──────────────────────────────────────────────────────

def test_requires_registry():
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    ced = CEDOrchestrator(agents, provider)   # no registry
    ced.create_session("Q?", session_id="noreg")
    with pytest.raises(RuntimeError, match="requires a CouncilProviderRegistry"):
        asyncio.run(ced.run_registry_council_round(
            "noreg", "agent_0", AgentRole.SOCRATES, DialogPhase.OPENING))


def test_run_session_unchanged_and_independent_of_registry_path():
    """run_session still works and does not touch the registry council path."""
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider())
    final = ced.run_session("Is knowledge merely justified true belief?", session_id="rc2")
    assert final.ratified is True
    state = ced.get_session("rc2")
    assert state.registry_rounds == []   # run_session never drives the registry path


# ── Minimal Awareness ─────────────────────────────────────────────────────────

def test_agentstate_has_no_registry_round_data():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider(), TimeoutProvider())
    _round(ced)
    ced.run_session("Q?", session_id="rc")   # reuse session id is fine; new session created
    state = ced.get_session("rc")
    for ast in state.agent_states.values():
        dumped = ast.model_dump()
        for forbidden in ("registry_rounds", "provider_status_summary",
                          "failed_providers", "ok_provider_ids", "api_key"):
            assert forbidden not in dumped


# ══════════════════════════════════════════════════════════════════════════════
# Full PHASE round: one move per deterministically-assigned agent/role
# ══════════════════════════════════════════════════════════════════════════════

def _phase_round(ced, phase, **kw):
    state = ced.get_session("rc")
    return asyncio.run(ced.gather_registry_phase_round(state, phase, **kw)), state


class _RoleHijackProvider(BaseProviderAdapter):
    """Tries to dictate role/phase via its JSON — must be ignored by the CED."""
    provider_id = "mock_hijack"
    provider_name = "Mock Role Hijack"
    is_fake = True

    def __init__(self):
        super().__init__(api_key="sk-fake-hijack")

    async def _produce_raw_text(self, task, agent_state):
        import json
        return json.dumps({
            "content": {"text": "trying to seize a different role"},
            "confidence": 0.7,
            "role": "final_evaluator",     # bogus — should be ignored
            "phase": "ratification",        # bogus — should be ignored
        })


def test_phase_round_returns_one_move_per_assigned_agent():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider())
    result, state = _phase_round(ced, DialogPhase.INITIAL_RESPONSE)
    plan = ced.assign_roles_for_phase(state, DialogPhase.INITIAL_RESPONSE)

    assert result.proceed is True
    assert len(result.responses) == len(plan)
    ok_moves = {r.parsed_move.agent_id: r.parsed_move for r in result.responses if r.ok}
    assert set(ok_moves) == set(plan)
    for agent_id, role in plan.items():
        assert ok_moves[agent_id].role == role           # exactly the assigned role
        assert ok_moves[agent_id].phase == DialogPhase.INITIAL_RESPONSE


def test_phase_round_uses_deterministic_role_assignment():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider())
    state = ced.get_session("rc")
    plan = ced.assign_roles_for_phase(state, DialogPhase.INITIAL_RESPONSE)
    result = asyncio.run(ced.gather_registry_phase_round(state, DialogPhase.INITIAL_RESPONSE))
    produced = {r.parsed_move.agent_id: r.parsed_move.role for r in result.responses if r.ok}
    assert produced == plan


def test_provider_cannot_change_role_assignment():
    # Even a provider that returns a bogus role/phase cannot override the plan,
    # and swapping the provider set does not change which agent gets which role.
    ced_a, _ = _ced(_RoleHijackProvider(), _RoleHijackProvider())
    state_a = ced_a.get_session("rc")
    plan_a = ced_a.assign_roles_for_phase(state_a, DialogPhase.INITIAL_RESPONSE)
    res_a = asyncio.run(ced_a.gather_registry_phase_round(state_a, DialogPhase.INITIAL_RESPONSE))
    for r in res_a.responses:
        if r.ok:
            assert r.parsed_move.role == plan_a[r.parsed_move.agent_id]
            assert r.parsed_move.role != AgentRole.FINAL_EVALUATOR  # hijack ignored

    ced_b, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider(), AlwaysOKProvider())
    state_b = ced_b.get_session("rc")
    plan_b = ced_b.assign_roles_for_phase(state_b, DialogPhase.INITIAL_RESPONSE)
    assert plan_a == plan_b   # role plan independent of provider set


def test_phase_round_proceeds_when_one_provider_fails_but_quorum_remains():
    # 3 assigned agents over [OK, Timeout] round-robin → 2 OK ≥ quorum(2).
    ced, _ = _ced(AlwaysOKProvider(), TimeoutProvider())
    result, _ = _phase_round(ced, DialogPhase.INITIAL_RESPONSE)
    assert result.proceed is True
    assert len(result.ok_provider_ids) == 2
    assert "mock_timeout" in result.failed_provider_ids
    assert all(r.parsed_move is None for r in result.responses if not r.ok)


def test_phase_round_below_quorum_no_fabricated_moves():
    # 3 assigned agents over [OK, Timeout, Timeout] → only 1 OK < quorum(2).
    ced, _ = _ced(AlwaysOKProvider(), TimeoutProvider(), TimeoutProvider())
    result, _ = _phase_round(ced, DialogPhase.INITIAL_RESPONSE)
    assert result.proceed is False
    assert result.warning is not None
    assert all(r.parsed_move is None for r in result.responses if not r.ok)


def test_phase_round_recorded_on_session():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider())
    _phase_round(ced, DialogPhase.OPENING)
    _phase_round(ced, DialogPhase.INITIAL_RESPONSE)
    state = ced.get_session("rc")
    assert len(state.registry_rounds) == 2


def test_phase_round_requires_registry():
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    ced = CEDOrchestrator(agents, provider)   # no registry
    state = ced.create_session("Q?", session_id="noreg2")
    with pytest.raises(RuntimeError, match="requires a CouncilProviderRegistry"):
        asyncio.run(ced.gather_registry_phase_round(state, DialogPhase.INITIAL_RESPONSE))


def test_phase_round_does_not_touch_run_session():
    ced, _ = _ced(AlwaysOKProvider(), AlwaysOKProvider())
    state = ced.get_session("rc")
    asyncio.run(ced.gather_registry_phase_round(state, DialogPhase.SYNTHESIS))
    # A fresh run_session is fully independent and unaffected.
    final = ced.run_session("Is knowledge merely justified true belief?", session_id="rc_session")
    assert final.ratified is True
    assert ced.get_session("rc_session").registry_rounds == []


def test_phase_round_no_provider_metadata_in_agentstate_or_task():
    ced, _ = _ced(AlwaysOKProvider(), TimeoutProvider())
    result, state = _phase_round(ced, DialogPhase.INITIAL_RESPONSE)

    # AgentState carries no provider metadata.
    for ast in state.agent_states.values():
        dumped = ast.model_dump()
        for forbidden in ("provider_id", "provider_status", "api_key",
                          "failed_providers", "registry_rounds"):
            assert forbidden not in dumped

    # The AgentTask sent to providers exposes no key/provider-failure internals.
    for r in result.responses:
        if r.ok:
            blob = str(r.parsed_move.content).lower()
            for kw in ("api_key", "provider_status", "failed_providers", "mock_timeout"):
                assert kw not in blob
