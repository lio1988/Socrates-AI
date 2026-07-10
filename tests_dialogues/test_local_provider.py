"""
Local LLM provider tests (Goal 10).

Verifies (all offline — canned transports, injected openers, NO network):
  - inert construction (no call at build time)
  - a canned OpenAI-compatible envelope parses into a real move through the
    inherited transport/validation machinery
  - a dead/failed server yields an honest ProviderResponse, never a
    fabricated move, never a crash
  - env-only gated resolution: clean skips with helpful reasons; never .env
  - no key required (local availability = enabled)
  - probe helper with injectable opener (dead server -> helpful hint)
  - the Goal 10 -> Goal 11 bridge: the local adapter as Shadow Apprentice
    wins rigged sections end-to-end
  - runtime isolation: the CED core never imports openclaw_local
"""

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    AgentRole,
    AgentState,
    AgentTask,
    DialogPhase,
    ProviderStatus,
    ScoreBreakdown,
    ShadowScoringMode,
    TaskKind,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.dialogues.nvidia_nim_provider import (
    CannedNvidiaNIMTransport,
    NvidiaNIMTransportError,
    nvidia_chat_envelope,
)
from backend.dialogues.openclaw_local import (
    DEFAULT_APPRENTICE_ID,
    DEFAULT_LOCAL_BASE_URL,
    LOCAL_GATE_ENV,
    LOCAL_MODEL_ENV,
    LOCAL_URL_ENV,
    NO_KEY,
    LocalLLMAdapter,
    build_local_shadow_apprentice,
    probe_local_server,
    resolve_local_adapter,
)

STRONG = "STRONGCONTENT"
WEAK = "WEAKCONTENT"
_SECTIONS = ("core_answer", "crucial_stress_test", "blind_spots",
             "nuance", "final_verdict")


def _sections_json(marker):
    return json.dumps({"content": {f: f"{marker} {f}" for f in _SECTIONS},
                       "confidence": 0.8})


def _synthesis_task(question="q", sid="local_1"):
    return AgentTask(
        session_id=sid, agent_id=DEFAULT_APPRENTICE_ID,
        role=AgentRole.SYNTHESIZER, phase=DialogPhase.SYNTHESIS,
        question=question, context={},
        output_schema={"_role": AgentRole.SYNTHESIZER.value,
                       "_question": question, "_sections": True},
        task_kind=TaskKind.SYNTHESIS_DRAFT, slot_index=0,
    )


def _astate():
    return AgentState(agent_id=DEFAULT_APPRENTICE_ID,
                      primary_role=AgentRole.SYNTHESIZER,
                      assigned_role=AgentRole.SYNTHESIZER)


def _adapter(transport=None, **kw):
    return LocalLLMAdapter(model="llama3.1:8b", transport=transport, **kw)


# --------------------------------------------------------------------------- #
# Adapter mechanics (canned transport, no network)
# --------------------------------------------------------------------------- #

def test_construction_is_inert_and_key_free():
    adapter = _adapter()
    assert adapter.is_available() is True          # no key needed
    assert adapter.api_key == NO_KEY
    assert adapter.base_url == DEFAULT_LOCAL_BASE_URL.rstrip("/")
    assert adapter.is_local is True
    assert "llama3.1:8b" in adapter.provider_name


def test_requires_model_name():
    with pytest.raises(ValueError, match="model"):
        LocalLLMAdapter(model="   ")


def test_canned_envelope_parses_into_real_move():
    transport = CannedNvidiaNIMTransport(
        envelope=nvidia_chat_envelope(_sections_json(STRONG)))
    adapter = _adapter(transport)
    resp = asyncio.run(adapter.generate_agent_move(_synthesis_task(), _astate()))
    assert resp.ok
    assert resp.parsed_move.content["core_answer"].startswith(STRONG)
    assert transport.calls == 1


def test_dead_server_is_honest_failure_not_crash():
    transport = CannedNvidiaNIMTransport(
        failure=NvidiaNIMTransportError("connection error: [WinError 10061]"))
    adapter = _adapter(transport)
    resp = asyncio.run(adapter.generate_agent_move(_synthesis_task(), _astate()))
    assert not resp.ok
    assert resp.status == ProviderStatus.ERROR
    assert resp.parsed_move is None                 # never fabricated
    assert "connection error" in resp.error_message


def test_disabled_adapter_is_unavailable():
    adapter = _adapter(enabled=False)
    assert adapter.is_available() is False


# --------------------------------------------------------------------------- #
# Gated env-only resolution
# --------------------------------------------------------------------------- #

def test_no_gate_is_a_clean_skip_with_instructions():
    adapter, reason = resolve_local_adapter({})
    assert adapter is None
    assert LOCAL_GATE_ENV in reason                 # tells the user what to set


def test_gate_without_model_is_a_clean_skip():
    adapter, reason = resolve_local_adapter({LOCAL_GATE_ENV: "1"})
    assert adapter is None
    assert LOCAL_MODEL_ENV in reason


def test_full_env_builds_adapter():
    adapter, reason = resolve_local_adapter({
        LOCAL_GATE_ENV: "1",
        LOCAL_MODEL_ENV: "llama3.1:8b",
        LOCAL_URL_ENV: "http://localhost:1234/v1",   # LM Studio
        "CED_LOCAL_LLM_TIMEOUT": "60",
    })
    assert adapter is not None
    assert adapter.provider_id == DEFAULT_APPRENTICE_ID
    assert adapter.base_url == "http://localhost:1234/v1"
    assert adapter.timeout == 60.0
    assert "enabled" in reason


def test_invalid_timeout_is_a_clean_skip():
    adapter, reason = resolve_local_adapter({
        LOCAL_GATE_ENV: "1", LOCAL_MODEL_ENV: "m",
        "CED_LOCAL_LLM_TIMEOUT": "soon"})
    assert adapter is None and "TIMEOUT" in reason


# --------------------------------------------------------------------------- #
# Probe (injected opener — no real network)
# --------------------------------------------------------------------------- #

def test_probe_ok_with_injected_opener():
    ok, msg = probe_local_server(
        opener=lambda url, t: json.dumps({"object": "list", "data": []}))
    assert ok is True and DEFAULT_LOCAL_BASE_URL in msg


def test_probe_dead_server_gives_helpful_hint():
    def _dead(url, t):
        raise ConnectionRefusedError("refused")
    ok, msg = probe_local_server(opener=_dead)
    assert ok is False
    assert "running" in msg                         # actionable hint
    assert "Ollama" in msg


# --------------------------------------------------------------------------- #
# The bridge: local model as Shadow Apprentice (Goal 10 hosts Goal 11)
# --------------------------------------------------------------------------- #

class MarkerJudge(ScriptedMockProvider):
    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SECTION_SCORE:
            text = str(task.context.get("output_to_score", ""))
            value = 9.0 if STRONG in text else 5.0
            breakdown = {k: value for k in ScoreBreakdown.model_fields}
            return json.dumps({"content": {"score_breakdown": breakdown,
                                           "confidence": 0.8,
                                           "justification": "rig",
                                           "penalty_flags": [],
                                           "provider_status": "ok"},
                               "confidence": 0.8})
        return await super()._produce_raw_text(task, agent_state)


class WeakDrafter(MarkerJudge):
    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind == TaskKind.SYNTHESIS_DRAFT:
            return _sections_json(WEAK)
        return await super()._produce_raw_text(task, agent_state)


def _weak_council():
    reg = CouncilProviderRegistry(provider_timeout_seconds=10.0)
    reg.register(WeakDrafter("council_seat0"))
    reg.register(WeakDrafter("council_seat1"))
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(2)]
    return CEDOrchestrator(agents, provider, registry=reg,
                           assembly_fallback=True,
                           shadow_scoring_mode=ShadowScoringMode.OFF)


def test_gated_builder_skips_cleanly_without_env():
    runner, reason = build_local_shadow_apprentice(
        {}, judges=[MarkerJudge("shadow_judge0")])
    assert runner is None and LOCAL_GATE_ENV in reason


def test_local_apprentice_shadows_and_wins_e2e():
    # The local adapter (canned strong output, zero network) enters the
    # Goal 11 runner and beats a weak council on every resolved section.
    runner, reason = build_local_shadow_apprentice(
        {LOCAL_GATE_ENV: "1", LOCAL_MODEL_ENV: "llama3.1:8b"},
        judges=[MarkerJudge("shadow_judge0")])
    assert runner is not None, reason
    runner.apprentice.transport = CannedNvidiaNIMTransport(
        envelope=nvidia_chat_envelope(_sections_json(STRONG)))
    final, record = asyncio.run(runner.shadow_session(
        _weak_council(), "q", session_id="local_shadow_1"))
    assert final.ratified is True                   # council untouched
    assert record["ok"] is True
    assert record["apprentice_id"] == DEFAULT_APPRENTICE_ID
    assert record["shadow_run"] is True
    assert record["shadow_wins"] == len(record["shadow_comparison"]) > 0


# --------------------------------------------------------------------------- #
# Runtime isolation
# --------------------------------------------------------------------------- #

def test_ced_core_never_imports_local_package():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "backend" / "dialogues"
    for name in ("ced.py", "live_providers.py", "provider_registry.py",
                 "models.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "openclaw_local" not in source, (
            f"{name} must not import the local provider — the apprentice "
            "enters the council only through the Promotion Arena")
