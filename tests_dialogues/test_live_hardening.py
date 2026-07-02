"""
Regression tests for the live-council hardening (commit e3c5b3f).

Every fix here was discovered via REAL live runs and then locked in offline:
  - parse_and_validate_move ignores trailing prose after the JSON object
  - assembly_fallback populates sections from real drafts when peer scores are
    missing (opt-in; default stays strict no-score -> unresolved)
  - per-task content directives tell real models the EXACT structure to return
    (synthesis 5 sections, score 7 dims, ratification verdict shape)
  - the live council factory enables the fallback + long timeout + big max_tokens

All offline — no network, no keys, no .env.
"""

import asyncio
import json

import pytest

from backend.dialogues.models import (
    AgentRole, AgentTask, DialogPhase, SectionDraft, SectionName, SessionState,
    ShadowScoringMode, TaskKind, CouncilVerdict, ScoreBreakdown,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, parse_and_validate_move,
)
from backend.dialogues.reasoning_prompts import (
    build_reasoning_system_prompt,
    SYNTHESIS_CONTENT_DIRECTIVE, SCORE_CONTENT_DIRECTIVE, RATIFICATION_CONTENT_DIRECTIVE,
)
from backend.dialogues import live_providers as LP


def _task(kind=TaskKind.ELENCHUS_OBJECTION, phase=DialogPhase.ELENCHUS,
          role=AgentRole.ELENCHUS_CRITIC):
    return AgentTask(session_id="s", agent_id="a", role=role, phase=phase,
                     question="q", task_kind=kind)


# ── raw_decode: trailing prose after the JSON object is tolerated ─────────────

def test_trailing_prose_after_json_is_parsed():
    raw = ('```json\n{"content": {"x": "ok"}, "confidence": 0.8}\n```\n\n'
           "Note: here is my additional commentary that used to break parsing.")
    move, status, err = parse_and_validate_move(raw, _task(), meta={})
    assert status.value == "ok" and move.content == {"x": "ok"}


def test_second_json_block_after_first_is_ignored():
    raw = ('{"content": {"x": "first"}, "confidence": 0.7}\n'
           '{"content": {"x": "second"}, "confidence": 0.9}')
    move, status, _ = parse_and_validate_move(raw, _task(), meta={})
    assert status.value == "ok" and move.content == {"x": "first"}


def test_pure_garbage_still_rejected():
    move, status, _ = parse_and_validate_move("<<< not json at all >>>", _task(), meta={})
    assert move is None and status.value == "invalid_json"


# ── assembly_fallback: never-empty answers for live, strict default kept ──────

def _ced_with_draft(fallback: bool):
    p = FakeProvider()
    agents = [SocraticAgent(f"a{i}", p) for i in range(2)]
    ced = CEDOrchestrator(agents, p, assembly_fallback=fallback)
    sid = f"fb_{fallback}"
    ced._sessions[sid] = SessionState(session_id=sid, question="q")
    ced._sessions[sid].section_drafts = [
        SectionDraft(draft_id="d2", session_id=sid, author_agent_id="a1", move_id="m2",
                     core_answer="B core", crucial_stress_test="B stress",
                     blind_spots="B blind", nuance="B nuance", final_verdict="B verdict"),
        SectionDraft(draft_id="d1", session_id=sid, author_agent_id="a0", move_id="m1",
                     core_answer="A core", crucial_stress_test="A stress",
                     blind_spots="A blind", nuance="A nuance", final_verdict="A verdict"),
    ]
    return ced, sid


def test_fallback_on_uses_real_draft_deterministically():
    ced, sid = _ced_with_draft(fallback=True)
    ans = ced.assemble_sections(sid)         # NO peer scores at all
    core = ans.section(SectionName.CORE_ANSWER)
    assert core.unresolved is False
    assert core.content == "A core"           # lowest draft_id wins (deterministic)
    assert core.selected_draft_id == "d1"
    assert core.score_count == 0               # honest: no scores backed this choice


def test_fallback_off_keeps_strict_unresolved():
    ced, sid = _ced_with_draft(fallback=False)
    ans = ced.assemble_sections(sid)
    core = ans.section(SectionName.CORE_ANSWER)
    assert core.unresolved is True and core.content == ""


def test_fallback_defaults_off():
    p = FakeProvider()
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", p) for i in range(2)], p)
    assert ced.assembly_fallback is False


def test_full_registry_session_unchanged_with_default(monkeypatch):
    # mock registry session (scores present) is identical with fallback on/off
    for fb in (False, True):
        p = FakeProvider()
        agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
        reg = CouncilProviderRegistry()
        reg.register(ScriptedMockProvider("m_a")); reg.register(ScriptedMockProvider("m_b"))
        ced = CEDOrchestrator(agents, p, registry=reg, assembly_fallback=fb)
        final = asyncio.run(ced.run_registry_session("Is knowledge JTB?", session_id=f"s{fb}"))
        assert final.ratified is True
        assert all(not s.unresolved for s in final.synthesis.sections)


# ── per-task content directives (exact names real models must return) ─────────

def test_synthesis_directive_lists_exact_section_names():
    p = build_reasoning_system_prompt(AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS,
                                      TaskKind.SYNTHESIS_DRAFT)
    for name in SectionName:
        assert f'"{name.value}"' in p


def test_score_directive_matches_scorebreakdown_exactly():
    p = build_reasoning_system_prompt(AgentRole.FINAL_EVALUATOR, DialogPhase.SYNTHESIS,
                                      TaskKind.SECTION_SCORE)
    for dim in ScoreBreakdown.model_fields:
        assert f'"{dim}"' in p


def test_ratification_directive_matches_verdict_enum_exactly():
    p = build_reasoning_system_prompt(AgentRole.FINAL_EVALUATOR, DialogPhase.RATIFICATION,
                                      TaskKind.COUNCIL_RATIFICATION)
    for v in CouncilVerdict:
        assert v.value in p
    for field in ("rationale", "target_section", "required_fix", "caveat", "severity"):
        assert field in p


def test_directives_do_not_leak_into_other_tasks():
    p = build_reasoning_system_prompt(AgentRole.SOCRATES, DialogPhase.OPENING,
                                      TaskKind.SOCRATIC_QUESTION)
    assert SYNTHESIS_CONTENT_DIRECTIVE.splitlines()[0] not in p
    assert SCORE_CONTENT_DIRECTIVE.splitlines()[0] not in p
    assert RATIFICATION_CONTENT_DIRECTIVE.splitlines()[0] not in p


def test_directive_examples_are_valid_json_and_schema():
    # the examples we show the models must themselves parse through our validator
    for directive, kind in ((SYNTHESIS_CONTENT_DIRECTIVE, TaskKind.SYNTHESIS_DRAFT),
                            (SCORE_CONTENT_DIRECTIVE, TaskKind.SECTION_SCORE),
                            (RATIFICATION_CONTENT_DIRECTIVE, TaskKind.COUNCIL_RATIFICATION)):
        example = directive[directive.index('{"content"'):]
        move, status, err = parse_and_validate_move(example, _task(kind=kind), meta={})
        assert status.value == "ok", (kind, err)


# ── live council factory wiring ───────────────────────────────────────────────

def test_live_factory_enables_fallback_and_long_timeout():
    ced, mode = LP.build_council(env={}, council_size=2,
                                 shadow_scoring_mode=ShadowScoringMode.OFF)
    assert mode == "mock"
    assert ced.assembly_fallback is True                     # live path: never-empty answers
    # registry budget covers every attempt: (retries+1)*timeout + delays + margin
    expected = (LP.DEFAULT_RETRIES + 1) * LP.DEFAULT_REGISTRY_TIMEOUT \
        + LP.DEFAULT_RETRIES * LP.DEFAULT_RETRY_DELAY + 5.0
    assert ced.registry.provider_timeout_seconds == expected
    assert LP.DEFAULT_MAX_TOKENS == 8192 and LP.DEFAULT_REGISTRY_TIMEOUT == 180.0


# ── deterministic retry: transient-only, bounded, recorded ────────────────────

FAKE_KEY = "sk-ant-FAKE-not-a-real-key-000000"


def _adapter(retries=1):
    return LP.LiveAnthropicAdapter("seat0", FAKE_KEY, retries=retries,
                                   retry_delay_seconds=0.0)


def _fake_exc(name):
    return type(name, (Exception,), {})()


def test_retry_recovers_from_transient_rate_limit(monkeypatch):
    calls = {"n": 0}

    async def flaky(self, task, agent_state):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _fake_exc("RateLimitError")
        return '{"content": {"x": "recovered"}, "confidence": 0.8}'

    monkeypatch.setattr(LP.LiveAnthropicAdapter, "_produce_raw_text", flaky)
    resp = asyncio.run(_adapter(retries=1).generate_agent_move(
        _task(TaskKind.INITIAL_RESPONSE, DialogPhase.INITIAL_RESPONSE, AgentRole.SYNTHESIZER),
        None))
    assert resp.ok and resp.parsed_move.content == {"x": "recovered"}
    assert resp.retry_count == 1 and calls["n"] == 2


def test_retry_is_bounded(monkeypatch):
    calls = {"n": 0}

    async def always_limited(self, task, agent_state):
        calls["n"] += 1
        raise _fake_exc("RateLimitError")

    monkeypatch.setattr(LP.LiveAnthropicAdapter, "_produce_raw_text", always_limited)
    resp = asyncio.run(_adapter(retries=2).generate_agent_move(_task(), None))
    assert resp.status.value == "rate_limited"
    assert calls["n"] == 3 and resp.retry_count == 2          # 1 attempt + 2 retries, no more


def test_no_retry_on_deterministic_error(monkeypatch):
    calls = {"n": 0}

    async def credit_error(self, task, agent_state):
        calls["n"] += 1
        raise RuntimeError("Your credit balance is too low")

    monkeypatch.setattr(LP.LiveAnthropicAdapter, "_produce_raw_text", credit_error)
    resp = asyncio.run(_adapter(retries=3).generate_agent_move(_task(), None))
    assert resp.status.value == "error"
    assert calls["n"] == 1 and resp.retry_count == 0          # money not wasted on retries


def test_council_adapter_disambiguates_timeout_vs_connection(monkeypatch):
    async def raise_timeout(self, task, agent_state):
        raise _fake_exc("APITimeoutError")
    monkeypatch.setattr(LP.LiveAnthropicAdapter, "_produce_raw_text", raise_timeout)
    r1 = asyncio.run(_adapter(retries=0).generate_agent_move(_task(), None))
    assert r1.status.value == "timeout" and "CED_LIVE_TIMEOUT" in r1.error_message

    async def raise_conn(self, task, agent_state):
        raise _fake_exc("APIConnectionError")
    monkeypatch.setattr(LP.LiveAnthropicAdapter, "_produce_raw_text", raise_conn)
    r2 = asyncio.run(_adapter(retries=0).generate_agent_move(_task(), None))
    assert r2.status.value == "error" and "network" in r2.error_message.lower()


def test_resolve_retries_env():
    assert LP.resolve_retries({}) == LP.DEFAULT_RETRIES == 1
    assert LP.resolve_retries({LP.RETRIES_ENV: "3"}) == 3
    assert LP.resolve_retries({LP.RETRIES_ENV: "0"}) == 0
    assert LP.resolve_retries({LP.RETRIES_ENV: "junk"}) == LP.DEFAULT_RETRIES
