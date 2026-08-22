"""Who raised an objection, and whether the projection can read a vote at all.

Two bugs in `project_governing_state`, both silent, both found while looking at
something else. Neither changes what counts as support; they decide who is
allowed to check a criticism, and whether the governing layer survives a
populated ratification vote.

All offline: scripted providers, no network, no key.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    ObjectionSeverity, RatificationDecision, RatificationVote, ShadowScoringMode,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider


class TargetingMock(ScriptedMockProvider):
    """A seat whose elenchus objections name the section they are about.

    Without a declared target an objection maps to nothing and is never put to
    a vote, so these tests would exercise no peer selection at all.
    """

    async def _produce_raw_text(self, task, agent_state) -> str:
        if task.task_kind is TaskKind.ELENCHUS_OBJECTION:
            return json.dumps({"content": {
                "critique": "the load-bearing assumption was asserted, not shown",
                "target_section": "core_answer"}, "confidence": 0.8})
        return await super()._produce_raw_text(task, agent_state)

TASK = ("Four researchers present once each. Anna presents before Ben. "
        "Clara presents immediately before David. Ben does not present last.")


def _run(session_id, seats=4):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    for i in range(seats):
        registry.register(TargetingMock(f"seat{i}"))
    ced = CEDOrchestrator(agents, provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(TASK, session_id=session_id))
    return ced, final, {f"seat{i}" for i in range(seats)}


def test_an_objection_is_attributed_to_the_seat_that_raised_it():
    """`raised_by` held an agent_id while peer filtering compares provider_ids.

    They never matched, so `run_objection_verification`'s "every seat that did
    not raise it" excluded nobody, and a seat could corroborate its own
    objection. The independence the corroboration gate rests on was not there.
    """
    ced, final, seat_ids = _run("identity")
    core = ced.project_governing_state(ced.get_session("identity"), final)
    assert core.objections, "elenchus moves should project as objections"
    for objection in core.objections.values():
        assert objection.raised_by in seat_ids, "an agent_id can never match a seat"
        peers = [s for s in seat_ids if s != objection.raised_by]
        assert len(peers) == len(seat_ids) - 1, "the raiser must be excluded"


def test_the_raiser_is_never_asked_to_verify_its_own_objection():
    """The behaviour, not the field: who actually receives a verification task.

    Before the fix every seat received one for every objection, including the
    seat that raised it.
    """
    ced, final, _ = _run("identity_peers")
    session = ced.get_session("identity_peers")
    core = ced.project_governing_state(session, final)
    assert core.objections, "there must be something to verify"

    asked: dict[str, set] = {}
    original = ced.registry.run_adapter

    async def spy(adapter, task, agent_state, timeout=None):
        if task.task_id.startswith("verify_"):
            asked.setdefault(task.task_id, set()).add(adapter.provider_id)
        return await original(adapter, task, agent_state, timeout)

    ced.registry.run_adapter = spy
    asyncio.run(ced.run_objection_verification(session, core))

    assert asked, "verification must have been attempted"
    total = len(ced.registry.all_adapters())
    for objection_id, objection in core.objections.items():
        seats = asked.get(f"verify_{objection_id}")
        assert seats is not None
        assert objection.raised_by not in seats
        # The count is the part that catches the bug: with an agent_id in
        # `raised_by` nothing matched, so every seat was asked and the line
        # above passed while excluding nobody.
        assert len(seats) == total - 1, f"{objection.raised_by} was not excluded"


def test_a_critical_ratification_vote_projects_without_crashing():
    """The loop called three names RatificationVote does not have.

    Dead while `ratification_votes` stayed empty. The first populated vote would
    have raised AttributeError inside `_apply_governing_release`, whose guard
    catches everything and reports the governing verdict as unavailable — the
    whole layer switched off by a typo, with no signal but an exception name.
    """
    ced, final, _ = _run("votes", seats=3)
    final.ratification_votes = [
        RatificationVote(voter_agent_id="agent_1",
                         decision=RatificationDecision.BLOCKING_OBJECTION,
                         severity=ObjectionSeverity.CRITICAL,
                         reason="the core answer contradicts the second constraint"),
        RatificationVote(voter_agent_id="agent_2",
                         decision=RatificationDecision.APPROVE,
                         severity=ObjectionSeverity.NONE,
                         reason="reads fine to me"),
    ]
    core = ced.project_governing_state(ced.get_session("votes"), final)
    texts = [o.text for o in core.objections.values()]
    assert "the core answer contradicts the second constraint" in texts
    assert "reads fine to me" not in texts     # only a critical block projects


def test_a_non_critical_vote_projects_nothing():
    """Approval is not a criticism, and neither is a non-critical objection."""
    ced, final, _ = _run("votes_soft", seats=3)
    before = len(ced.project_governing_state(
        ced.get_session("votes_soft"), final).objections)
    final.ratification_votes = [
        RatificationVote(voter_agent_id="agent_1",
                         decision=RatificationDecision.BLOCKING_OBJECTION,
                         severity=ObjectionSeverity.MINOR, reason="a quibble"),
    ]
    after = len(ced.project_governing_state(
        ced.get_session("votes_soft"), final).objections)
    assert after == before
