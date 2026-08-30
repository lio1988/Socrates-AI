"""
Phase 8C — full registry-backed mock session (no real APIs).
"""

import asyncio

import pytest

from backend.dialogues.models import AssembledAnswer, EpistemicLeaderboard, ShadowScoringMode
from backend.dialogues.providers import FakeProvider
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider, TimeoutScriptedProvider,
    RateLimitedProvider,
)

Q = "Is knowledge merely justified true belief?"


def _ced(adapters, mode=ShadowScoringMode.ALL_PHASES, *, n_agents=4,
         phase_retry=False):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(n_agents)]
    reg = CouncilProviderRegistry()
    for a in adapters:
        reg.register(a)
    return CEDOrchestrator(
        agents, provider, registry=reg, shadow_scoring_mode=mode,
        phase_retry=phase_retry,
    )


def _run(ced, sid="p8c"):
    return asyncio.run(ced.run_registry_session(Q, session_id=sid)), ced.get_session(sid)


# ── Happy path ────────────────────────────────────────────────────────────────

def test_full_registry_session_succeeds():
    ced = _ced([ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b")])
    final, state = _run(ced)
    assert final.ratified is True
    assert final.ratification_status == "ratified"
    assert isinstance(final.synthesis, AssembledAnswer)
    assert len(final.synthesis.sections) == 5
    assert final.answer
    assert isinstance(final.socratic_leaderboard, EpistemicLeaderboard)
    assert final.audit_summary["execution_mode"] == "registry"


def test_returns_synthesis_leaderboard_and_audit():
    ced = _ced([ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b")])
    final, _ = _run(ced)
    au = final.audit_summary
    for key in ("provider_status_summary", "registry_phase_rounds",
                "task_log_count", "shadow_scoring_mode", "score_coverage"):
        assert key in au
    assert au["registry_phase_rounds"]      # every phase recorded
    assert final.socratic_leaderboard.leaderboard_status.value == "complete"


def test_no_real_provider_required():
    ced = _ced([ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b")])
    for a in ced.registry.all_adapters():
        assert getattr(a, "is_fake", False)


# ── Quorum success with partial failures ─────────────────────────────────────

def test_quorum_success_with_partial_failures():
    # The session id fixes the seating, and under "p8c-partial" the dead seat
    # holds the opening Socratic chair - which is a lost role, not a quorum
    # question, and is the case in the test below. This id seats it elsewhere so
    # the quorum path is the one actually exercised.
    ced = _ced([ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b"),
                TimeoutScriptedProvider()], n_agents=3, phase_retry=True)
    final, state = _run(ced, "p8c-partial-quorum")
    assert final.ratified is True
    # at least one phase recorded a failed provider, but the session still proceeded
    rounds = final.audit_summary["registry_phase_rounds"]
    assert any(r["failed_providers"] for r in rounds)
    assert all(r["proceed"] for r in rounds)
    # no fabricated moves: task_log has entries without a move for the failures
    assert any(e.move_id is None for e in state.task_log)


def test_a_dead_socratic_seat_stops_a_run_with_no_replacement_task():
    """The cost of removing the handover, and the exact condition for it.

    A seat that never answers used to have its chair passed to a healthy seat,
    so a council could finish with one seat wholly dead. It cannot any more: the
    chair belongs to a logical agent, and moving the same task to another seat
    is the topology change a bound protocol refuses at dispatch.

    What follows is NOT a universal law that a dead Socratic seat always ends
    every CED dialogue. It is what happens under a council that has no
    authorized replacement task, which is every council today. The termination
    itself is not new and is not this change: REFLECTION has always refused to
    run without an accepted Socratic question, and CED has always refused to
    reuse an older one - see test_without_rescue_one_silent_answer_ends_the
    _dialectic, which asserts exactly this with no rescue at all. The handover
    was the only thing that ever masked it.

    A future protocol may lift this by authorizing a NEW Socratic task with its
    own task_id, its own logical owner and its own provenance. This test must
    not be read as forbidding that, and must be revisited when one exists.
    """
    ced = _ced([ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b"),
                TimeoutScriptedProvider()], n_agents=3, phase_retry=True)
    final, state = _run(ced, "p8c-partial")
    assert final.ratified is False
    assert state.moves == []
    assert final.answer == ""


# ── Quorum failure → safe fallback ───────────────────────────────────────────

def test_quorum_failure_returns_safe_fallback():
    ced = _ced([ScriptedMockProvider("mock_a"), TimeoutScriptedProvider(),
                RateLimitedProvider()])
    final, state = _run(ced, "p8c-fail")
    assert final.ratified is False
    assert final.ratification_status == "quorum_failed"
    assert final.synthesis is None                 # safe fallback, no fake answer
    assert final.answer == ""
    assert final.audit_summary["quorum_failed"] is True


def test_not_ready_returns_safe_fallback():
    ced = _ced([ScriptedMockProvider("mock_a")])   # only 1 available < minimum 2
    final, _ = _run(ced, "p8c-notready")
    assert final.ratified is False
    assert final.audit_summary["quorum_failed"] is True
    assert final.synthesis is None


def test_requires_registry():
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    ced = CEDOrchestrator(agents, provider)   # no registry
    with pytest.raises(RuntimeError, match="requires a CouncilProviderRegistry"):
        asyncio.run(ced.run_registry_session(Q, session_id="noreg"))


# ── Existing behaviour + minimal awareness ───────────────────────────────────

def test_run_session_unchanged():
    ced = _ced([ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b")])
    final = ced.run_session(Q, session_id="p8c-rs")
    assert final.ratified is True                  # standard path still works
    assert "execution_mode" not in final.audit_summary  # not a registry session


def test_minimal_awareness_no_provider_or_tasklog_on_agentstate():
    ced = _ced([ScriptedMockProvider("mock_a"), ScriptedMockProvider("mock_b")])
    _final, state = _run(ced, "p8c-ma")
    for ast in state.agent_states.values():
        dumped = ast.model_dump()
        for forbidden in ("task_log", "provider_status_summary", "registry_rounds",
                          "micro_scores", "socratic_leaderboard", "api_key"):
            assert forbidden not in dumped
