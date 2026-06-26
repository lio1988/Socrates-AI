"""
Phase 11 — real-agent (live council) readiness (NO live calls).

Proves the council can be switched to real agents by env gating while defaulting
to a deterministic mock council, with NO network call at build time and the
`anthropic` SDK never imported. The reasoning prompt (Phase 10) reaches live
agents. No keys, no `.env`.
"""

import asyncio

import pytest

from backend.dialogues import live_providers as LP
from backend.dialogues.live_providers import (
    build_council, build_council_registry, LiveAnthropicAdapter,
    live_enabled, resolve_key, resolve_models, resolve_max_tokens,
    DEFAULT_LIVE_MODEL, DEFAULT_COUNCIL_SIZE,
)
from backend.dialogues.models import (
    AgentRole, AgentState, AgentTask, DialogPhase, ProviderStatus, TaskKind,
)
from backend.dialogues.reasoning_prompts import REASONING_PROTOCOL

FAKE_KEY = "sk-ant-FAKE-not-a-real-key-000000"


# ── gating helpers ───────────────────────────────────────────────────────────

def test_gating_helpers():
    assert live_enabled({LP.FLAG_ENV: "1"}) is True
    assert live_enabled({LP.FLAG_ENV: "0"}) is False and live_enabled({}) is False
    assert resolve_key({LP.KEY_ENV: FAKE_KEY}) == FAKE_KEY
    assert resolve_key({LP.KEY_ENV: "your_key_here"}) is None
    assert resolve_models({}, 3) == [DEFAULT_LIVE_MODEL] * 3
    assert resolve_models({LP.MODELS_ENV: "a, b ,c"}, 4) == ["a", "b", "c"]
    assert resolve_max_tokens({LP.MAXTOK_ENV: "512"}) == 512
    assert resolve_max_tokens({LP.MAXTOK_ENV: "nope"}) == LP.DEFAULT_MAX_TOKENS


# ── default = offline mock council ───────────────────────────────────────────

def test_default_is_mock_council():
    reg, mode = build_council_registry(env={})
    assert mode == "mock"
    adapters = reg.all_adapters()
    assert len(adapters) == DEFAULT_COUNCIL_SIZE
    assert all(getattr(a, "is_fake", False) for a in adapters)


@pytest.mark.parametrize("env", [
    {LP.FLAG_ENV: "1"},                              # flag, no key
    {LP.FLAG_ENV: "1", LP.KEY_ENV: "your_key_here"}, # flag, placeholder key
    {LP.FLAG_ENV: "0", LP.KEY_ENV: FAKE_KEY},        # key, flag off
    {LP.KEY_ENV: FAKE_KEY},                          # key, no flag
])
def test_falls_back_to_mock_unless_doubly_gated(env):
    reg, mode = build_council_registry(env=env, council_size=3)
    assert mode == "mock"
    assert all(getattr(a, "is_fake", False) for a in reg.all_adapters())


# ── gated = live council (built, NOT called) ─────────────────────────────────

def test_doubly_gated_builds_live_council_without_calling():
    env = {LP.FLAG_ENV: "1", LP.KEY_ENV: FAKE_KEY}
    reg, mode = build_council_registry(env=env, council_size=3)
    assert mode == "live"
    adapters = reg.all_adapters()
    assert len(adapters) == 3
    assert all(isinstance(a, LiveAnthropicAdapter) for a in adapters)
    assert all(a.is_live and not a.is_fake and not a.is_offline for a in adapters)
    assert all(a.is_available() for a in adapters)        # fake key is non-placeholder
    # built but NOT invoked → the anthropic SDK was never imported
    assert not hasattr(LP, "anthropic")


def test_live_models_env_sets_seats():
    env = {LP.FLAG_ENV: "1", LP.KEY_ENV: FAKE_KEY,
           LP.MODELS_ENV: "claude-opus-4-8,claude-sonnet-4-6"}
    reg, mode = build_council_registry(env=env)
    assert mode == "live"
    models = [a.model for a in reg.all_adapters()]
    assert models == ["claude-opus-4-8", "claude-sonnet-4-6"]


# ── the readiness switch produces a WORKING council (mock fallback runs) ──────

def test_build_council_runs_end_to_end_on_mock():
    ced, mode = build_council(env={})
    assert mode == "mock"
    final = asyncio.run(ced.run_registry_session("Is knowledge JTB?", session_id="rc"))
    assert final.ratified is True
    assert final.audit_summary["execution_mode"] == "registry"


def test_build_council_live_mode_is_gated():
    ced, mode = build_council(env={LP.FLAG_ENV: "1", LP.KEY_ENV: FAKE_KEY}, council_size=2)
    assert mode == "live"
    assert ced.registry is not None
    assert all(isinstance(a, LiveAnthropicAdapter) for a in ced.registry.all_adapters())
    # we do NOT run it — that would require a real network call.


# ── live agents receive the full reasoning prompt (Phase 10 × 11) ────────────

def test_live_agent_request_carries_full_reasoning_prompt():
    adapter = LiveAnthropicAdapter("seat0", FAKE_KEY, model=DEFAULT_LIVE_MODEL)
    task = AgentTask(session_id="s", agent_id="agent_0", role=AgentRole.ELENCHUS_CRITIC,
                     phase=DialogPhase.ELENCHUS, question="Is knowledge JTB?",
                     task_kind=TaskKind.ELENCHUS_OBJECTION)
    state = AgentState(agent_id="agent_0", primary_role=AgentRole.ELENCHUS_CRITIC,
                       assigned_role=AgentRole.ELENCHUS_CRITIC)
    req = adapter._build_request(task, state)
    assert REASONING_PROTOCOL.splitlines()[0] in req.system
    assert req.model == DEFAULT_LIVE_MODEL
    # no SDK import just from building a request
    assert not hasattr(LP, "anthropic")


def test_live_adapter_missing_key_is_honest():
    adapter = LiveAnthropicAdapter("seat0", "your_key_here")   # placeholder
    task = AgentTask(session_id="s", agent_id="a", role=AgentRole.SYNTHESIZER,
                     phase=DialogPhase.SYNTHESIS, question="q", task_kind=TaskKind.SYNTHESIS_DRAFT)
    state = AgentState(agent_id="a", primary_role=AgentRole.SYNTHESIZER,
                       assigned_role=AgentRole.SYNTHESIZER)
    resp = asyncio.run(adapter.generate_agent_move(task, state))
    assert resp.status == ProviderStatus.MISSING_KEY
    assert resp.parsed_move is None


def test_no_anthropic_import_at_module_load():
    assert not hasattr(LP, "anthropic")
