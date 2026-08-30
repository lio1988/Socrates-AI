"""
Phase 20 — Phase Rescue (one bounded re-ask of the failed slots, same seat).

The gap: a single transient failure in ANY deliberation phase used to kill the
WHOLE session — discarding every already-paid-for phase before it. Phase rescue
asks ONLY the slots that failed once more, at their own seats, with
deterministic move identity (attempt_index=1) so nothing duplicates or gets
fabricated.

These tests used to script a seat that fails FOREVER and be satisfied when the
healthy seat answered in its place. That is the cross-seat handover, and it is
gone: a task is bound to one logical agent at one seat for its whole life, so a
seat that fails twice loses its voice rather than lending its question out. The
transient case is therefore scripted as genuinely transient - it fails once and
answers when asked again - and the permanent case now asserts the loss.

Invariants checked:
- off by default on bare CEDOrchestrator (legacy behavior unchanged);
- build_council enables it by default;
- a transient single-seat failure gets rescued at its own seat;
- a seat that fails twice is a lost voice, never a handover;
- an all-seats failure is NOT rescued (honest fallback, no fabrication);
- no duplicate (phase, agent) moves; every move_id unique;
- full audit provenance per phase: failed slots, re-asked slots, lost voices;
- retry is bounded (attempted once, not looped).
Offline, mock only.
"""

import asyncio

import pytest

from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import ProviderResponse, ProviderStatus
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, TimeoutScriptedProvider,
    RateLimitedProvider,
)

Q = "Is knowledge merely justified true belief?"


class TransientlyFailingProvider(ScriptedMockProvider):
    """Fails the first ask and answers the second, at the same seat.

    What "transient" was always supposed to mean. The old fixture used a seat
    that never answered at all and relied on another seat covering for it, which
    tested the handover rather than the recovery.
    """

    def __init__(self, provider_id: str = "m_flaky", **kw) -> None:
        super().__init__(provider_id=provider_id, **kw)
        self.attempts_seen: list[int] = []

    async def generate_agent_move(self, task, agent_state):
        self.attempts_seen.append(task.attempt_index)
        if task.attempt_index == 0:
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=ProviderStatus.TIMEOUT,
                raw_text="",
                parsed_move=None,
                error_message="transient timeout",
            )
        return await super().generate_agent_move(task, agent_state)


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
    flaky = TransientlyFailingProvider()
    ced = _council(phase_retry=True,
                   providers=[flaky, ScriptedMockProvider("m_ok")])
    final = asyncio.run(ced.run_registry_session(Q, session_id="on1"))
    prs = final.audit_summary["phase_retries"]
    assert len(prs) > 0
    assert all(pr["rescued"] for pr in prs)     # every failed phase got rescued
    assert all(not pr["voice_lost_slots"] for pr in prs)
    # The seat that failed is the seat that answered. Nobody stood in for it.
    assert any(flaky.provider_id in pr["retry_ok_providers"] for pr in prs)
    assert flaky.attempts_seen and set(flaky.attempts_seen) <= {0, 1}


def test_a_seat_that_fails_twice_loses_its_voice_and_hands_nothing_on():
    """The inversion. This test asserted the handover; now it forbids it."""
    dead = TimeoutScriptedProvider()
    ced = _council(phase_retry=True,
                   providers=[dead, ScriptedMockProvider("m_ok")])
    asyncio.run(ced.run_registry_session(Q, session_id="lost_voice"))
    records = ced._phase_retries["lost_voice"]
    assert records, "the rescue never fired"
    for pr in records:
        assert dead.provider_id in pr["first_failed_providers"]
        # The healthy seat never answered in the dead seat place.
        assert "m_ok" not in pr["retry_ok_providers"]
        assert pr["voice_lost_slots"], "a seat failed twice and nothing was lost"


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
    flaky = TransientlyFailingProvider()
    ced = _council(phase_retry=True,
                   providers=[flaky, ScriptedMockProvider("m_ok")])
    asyncio.run(ced.run_registry_session(Q, session_id="attempt"))
    state = ced.get_session("attempt")
    retried = [m for m in state.moves if m.attempt_index == 1]
    assert len(retried) > 0
    assert all(m.provider_id == flaky.provider_id for m in retried)


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
    providers = [TransientlyFailingProvider(), ScriptedMockProvider("m_ok")]
    ced = _council(phase_retry=True, providers=providers)
    final = asyncio.run(ced.run_registry_session(Q, session_id="shape"))
    pr = final.audit_summary["phase_retries"][0]
    # The record is the policy written down: who failed, who was asked again at
    # their own seat, and whose voice was lost when that failed too.
    assert set(pr) == {"phase", "failed_slots", "reasked_same_seat_slots",
                       "voice_lost_slots", "quorum_held_but_a_voice_was_lost",
                       "first_failed_providers", "retry_ok_providers",
                       "rescued"}
    assert pr["failed_slots"] == pr["reasked_same_seat_slots"]
    assert isinstance(pr["voice_lost_slots"], list)


def test_healthy_session_never_triggers_retry():
    ced = _council(phase_retry=True)   # both seats healthy
    final = asyncio.run(ced.run_registry_session(Q, session_id="healthy"))
    assert final.ratified is True
    assert final.audit_summary["phase_retries"] == []


def test_build_council_enables_phase_retry_by_default():
    from backend.dialogues.live_providers import build_council
    ced, mode = build_council(env={}, council_size=2)
    assert mode == "mock" and ced.phase_retry is True
