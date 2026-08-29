"""
Phase 20 — Phase Rescue (bounded retry of only the failed slots, rerouted).

The gap: a single transient failure in ANY deliberation phase used to kill the
WHOLE session — discarding every already-paid-for phase before it. Phase rescue
retries ONLY the slots that failed in a quorum-failed phase, exactly once,
rerouted to the next seat (never the same one), with deterministic move
identity (attempt_index=1) so nothing duplicates or gets fabricated.

Invariants checked:
- off by default on bare CEDOrchestrator (legacy behavior unchanged);
- build_council enables it by default;
- a transient single-seat failure gets rescued (session survives);
- an all-seats failure is NOT rescued (honest fallback, no fabrication);
- no duplicate (phase, agent) moves; every move_id unique;
- full audit provenance per phase: failed slots, first/retry providers, rescued;
- retry is bounded (attempted once, not looped).
Offline, mock only.
"""

import asyncio

import pytest

from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, TimeoutScriptedProvider,
    RateLimitedProvider,
)

Q = "Is knowledge merely justified true belief?"


def _council(phase_retry=False, providers=None):
    p = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", p) for i in range(4)]
    reg = CouncilProviderRegistry()
    for adapter in providers or [ScriptedMockProvider("m_a"), ScriptedMockProvider("m_b")]:
        reg.register(adapter)
    return CEDOrchestrator(agents, p, registry=reg, phase_retry=phase_retry)


# ── default off / bare orchestrator unchanged ─────────────────────────────────

def test_phase_retry_default_is_off():
    ced = _council()
    assert ced.phase_retry is False


def test_off_by_default_a_transient_failure_kills_the_session():
    providers = [TimeoutScriptedProvider(), ScriptedMockProvider("m_ok")]
    ced = _council(phase_retry=False, providers=providers)
    final = asyncio.run(ced.run_registry_session(Q, session_id="off1"))
    assert final.ratified is False
    assert "phase_retries" not in final.audit_summary or not final.audit_summary["phase_retries"]


# ── rescue succeeds on a transient single-seat failure ────────────────────────

def test_transient_failure_is_rescued():
    providers = [TimeoutScriptedProvider(), ScriptedMockProvider("m_ok")]
    ced = _council(phase_retry=True, providers=providers)
    final = asyncio.run(ced.run_registry_session(Q, session_id="on1"))
    prs = final.audit_summary["phase_retries"]
    assert len(prs) > 0
    assert all(pr["rescued"] for pr in prs)     # every failed phase got rescued
    # The healthy seat carried the rescue. Not an exact list: the elenchus fills
    # three slots now, so more than one may be rerouted onto it.
    assert any("m_ok" in pr["retry_ok_providers"] for pr in prs)


def test_rescue_reroutes_to_a_different_seat():
    providers = [TimeoutScriptedProvider(), ScriptedMockProvider("m_ok")]
    ced = _council(phase_retry=True, providers=providers)
    asyncio.run(ced.run_registry_session(Q, session_id="reroute"))
    for pr in ced._phase_retries["reroute"]:
        assert "mock_scripted_timeout" in pr["first_failed_providers"]
        assert "m_ok" in pr["retry_ok_providers"]   # rerouted, not retried same seat


def test_no_duplicate_moves_and_unique_ids_after_rescue():
    providers = [TimeoutScriptedProvider(), ScriptedMockProvider("m_ok")]
    ced = _council(phase_retry=True, providers=providers)
    asyncio.run(ced.run_registry_session(Q, session_id="dup"))
    state = ced.get_session("dup")
    move_ids = [m.move_id for m in state.moves]
    assert len(move_ids) == len(set(move_ids))
    from collections import Counter
    counts = Counter((m.phase.value, m.agent_id) for m in state.moves)
    assert all(v == 1 for v in counts.values())


def test_retried_moves_carry_attempt_index_one():
    providers = [TimeoutScriptedProvider(), ScriptedMockProvider("m_ok")]
    ced = _council(phase_retry=True, providers=providers)
    asyncio.run(ced.run_registry_session(Q, session_id="attempt"))
    state = ced.get_session("attempt")
    retried = [m for m in state.moves if m.attempt_index == 1]
    assert len(retried) > 0
    assert all(m.provider_id == "m_ok" for m in retried)


# ── honest fallback when rescue cannot help ───────────────────────────────────

def test_all_seats_failing_is_not_fabricated():
    providers = [TimeoutScriptedProvider(), RateLimitedProvider()]
    ced = _council(phase_retry=True, providers=providers)
    final = asyncio.run(ced.run_registry_session(Q, session_id="allfail"))
    assert final.ratified is False
    assert final.answer == ""
    prs = ced._phase_retries.get("allfail", [])
    assert prs and all(not pr["rescued"] for pr in prs)


# ── audit shape + boundedness ──────────────────────────────────────────────────

def test_audit_shape_is_complete():
    providers = [TimeoutScriptedProvider(), ScriptedMockProvider("m_ok")]
    ced = _council(phase_retry=True, providers=providers)
    final = asyncio.run(ced.run_registry_session(Q, session_id="shape"))
    pr = final.audit_summary["phase_retries"][0]
    # The two rescue attempts are recorded apart, because they are different
    # acts: the first repeats the question to a seat that answered and was
    # refused, the second hands it to another seat after that failed too. A seat
    # that never spoke - a timeout - skips the repeat, since there is no first
    # answer for a second one to contradict.
    assert set(pr) == {"phase", "failed_slots", "retried_slots",
                       "degraded_duplicate_slots", "degraded_reason",
                       "first_failed_providers", "retry_ok_providers",
                       "reasked_same_seat_slots", "rerouted_on_first_attempt_slots",
                       "rerouted_distinct_seat_slots",
                       "reroute_ok_providers", "quorum_held_but_a_voice_was_lost",
                       "rescued"}
    # A reroute onto a seat already serving a sibling is now recorded rather
    # than invisible: the four-seat council took that path silently for two
    # live runs and halved its own peer pool.
    assert isinstance(pr["retried_slots"], list)
    assert isinstance(pr["degraded_duplicate_slots"], list)


def test_healthy_session_never_triggers_retry():
    ced = _council(phase_retry=True)   # both seats healthy
    final = asyncio.run(ced.run_registry_session(Q, session_id="healthy"))
    assert final.ratified is True
    assert final.audit_summary["phase_retries"] == []


def test_build_council_enables_phase_retry_by_default():
    from backend.dialogues.live_providers import build_council
    ced, mode = build_council(env={}, council_size=2)
    assert mode == "mock" and ced.phase_retry is True
