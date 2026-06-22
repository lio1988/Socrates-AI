"""
Phase 8B.2 — Registry-backed mock council demo / dev entry point tests.

Verifies the demo module builds only mock providers, the two required scenarios
behave (quorum success with partial failure / quorum failure), the report
carries the required safe labels and leaks no secrets, and Minimal Awareness
holds (no provider metadata in AgentState or AgentTask). Deterministic.
"""

import pytest

from backend.dialogues import demo_registry as dr
from backend.dialogues.models import AgentRole, DialogPhase
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator


# ── Module / builder ──────────────────────────────────────────────────────────

def test_demo_module_imports_and_has_entrypoints():
    assert hasattr(dr, "main")
    assert hasattr(dr, "render_report")
    assert hasattr(dr, "build_scenario")
    assert set(dr.SCENARIOS) >= {"A", "B"}


def test_scenario_builder_creates_only_mock_providers():
    for name, (_title, classes) in dr.SCENARIOS.items():
        _ced, _state, registry = dr.build_scenario(classes, session_id=f"t_{name}")
        adapters = registry.all_adapters()
        assert adapters
        assert all(getattr(a, "is_fake", False) for a in adapters), (
            f"scenario {name} registered a non-mock provider"
        )
        # provider ids are safe mock labels, never key-like
        assert all(a.provider_id.startswith("mock_") for a in adapters)


# ── Scenario behaviour ────────────────────────────────────────────────────────

def test_scenario_a_quorum_success_with_partial_failure():
    _ced, _state, _reg, result = dr.run_scenario("A")
    assert result.proceed is True
    assert len(result.ok_provider_ids) == 2
    assert "mock_timeout" in result.failed_provider_ids
    assert "mock_invalid_json" in result.failed_provider_ids
    # no fabricated moves for failed providers
    for r in result.responses:
        if not r.ok:
            assert r.parsed_move is None


def test_scenario_b_quorum_failure_non_proceed():
    _ced, _state, _reg, result = dr.run_scenario("B")
    assert result.proceed is False
    assert result.warning and "at least 2" in result.warning
    assert len(result.ok_provider_ids) < 2
    for r in result.responses:
        if not r.ok:
            assert r.parsed_move is None


def test_scenario_c_mixed_failures_no_crash():
    _ced, _state, _reg, result = dr.run_scenario("C")
    assert result.proceed is False
    assert all(r.parsed_move is None for r in result.responses if not r.ok)


# ── Report content / safety ───────────────────────────────────────────────────

def test_report_contains_required_labels():
    report = dr.render_report()
    assert "REGISTRY-BACKED MOCK COUNCIL DEMO" in report
    assert "NO REAL API CALLS" in report
    assert "CED-OWNED PROVIDER AUDIT" in report


def test_report_leaks_no_secrets_or_keys():
    report = dr.render_report()
    low = report.lower()
    assert ".env" not in low
    assert "api_key" not in low
    assert "secret" not in low
    # mock providers' api_key values (e.g. "sk-fake-ok") must never be printed
    assert "sk-" not in low
    assert "your_key_here" not in low


# ── Existing behaviour unchanged ──────────────────────────────────────────────

def test_run_session_behaviour_unchanged():
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    ced = CEDOrchestrator(agents, provider)   # plain CED, no registry
    final = ced.run_session("Is knowledge merely justified true belief?", session_id="dr_reg")
    assert final.ratified is True
    assert ced.get_session("dr_reg").registry_rounds == []


# ── Minimal Awareness ─────────────────────────────────────────────────────────

_FORBIDDEN = (
    "provider_status_summary", "failed_providers", "available_providers",
    "api_key", "provider_status", "ok_provider_ids", "registry_rounds",
)


def test_provider_metadata_not_in_agentstate():
    _title, classes = dr.SCENARIOS["A"]
    ced, state, _reg, _result = dr.run_scenario("A")
    state = ced.get_session("registry_demo_A")
    for ast in state.agent_states.values():
        dumped = ast.model_dump()
        for forbidden in _FORBIDDEN:
            assert forbidden not in dumped


def test_provider_metadata_not_in_agent_task():
    _title, classes = dr.SCENARIOS["A"]
    ced, state, _reg = dr.build_scenario(classes, session_id="dr_task")
    task = ced._build_round_task(state, "agent_0", AgentRole.SYNTHESIZER, dr.DEMO_PHASE)
    blob = (str(task.context) + " " + str(task.output_schema)).lower()
    for kw in ("api_key", "provider_status", "failed_providers",
               "available_providers", "mock_timeout", "sk-"):
        assert kw not in blob
