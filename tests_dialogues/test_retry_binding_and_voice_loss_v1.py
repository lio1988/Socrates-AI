"""One task, one seat, for its whole life - and a second failure is a lost voice.

The failure this is written from happened live. A Q5 council met a seat that
would not answer, and the rescue handed its task to a different seat. The
protocol under which that council ran binds one logical agent to one physical
seat and prices the run on that binding, so the pre-dispatch guard refused every
handed-on call - "deliberation task is not bound to agent_1" - and the run
collapsed at four calls.

The firewall did its job. The orchestration that walked into it did not, and the
answer is not to teach the rescue which protocols permit a handover. It is that
a task carries its binding for its whole life. If a voice is lost, it is lost,
and it is recorded as lost. Should some later protocol want another agent to
cover it, that is a NEW task with a new id, a new owner and its own
authorization - not this one wearing a different seat.

So the policy has exactly three steps:

    failure -> the same seat is asked again -> second failure -> VOICE_LOST

and quorum decides one thing only: whether the phase proceeds. It does not
decide who answers.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import ProviderResponse, ProviderStatus, TaskKind
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider

QUESTION_V1 = "Is knowledge merely justified true belief?"

#: Verbatim from the live record: HTTP 200, tokens billed, no usable content.
OBSERVED_EMPTY_ANSWER_V1 = '{"confidence":0.5,"content":{\n    }\n}'


class RecordingProvider(ScriptedMockProvider):
    """Answers normally, records everything, and refuses for named agents.

    Recording every dispatch is the point: the invariant under test is about
    which seat a task reaches, and that cannot be read off a phase record
    written by the same code being tested.
    """

    def __init__(
        self,
        provider_id: str,
        refuses_for: Sequence[str] = (),
        manner: str = "content",
        **kw,
    ) -> None:
        super().__init__(provider_id=provider_id, **kw)
        self.refuses_for = set(refuses_for)
        self.manner = manner
        self.seen: List[Tuple[str, str, int, str]] = []
        self.seen_tasks: List[Tuple[str, str, str]] = []

    async def generate_agent_move(self, task, agent_state) -> ProviderResponse:
        self.seen.append(
            (task.agent_id, task.task_kind.value, task.attempt_index, task.phase.value)
        )
        self.seen_tasks.append(
            (task.agent_id, task.task_kind.value, task.task_id)
        )
        if task.agent_id in self.refuses_for:
            if self.manner == "content":
                # It spoke, and said nothing usable.
                return ProviderResponse(
                    provider_id=self.provider_id,
                    agent_id=task.agent_id,
                    status=ProviderStatus.OK,
                    raw_text=OBSERVED_EMPTY_ANSWER_V1,
                    parsed_move=None,
                    error_message="empty content object",
                )
            # It never spoke at all.
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=ProviderStatus.TIMEOUT,
                raw_text="",
                parsed_move=None,
                error_message="the line went quiet",
            )
        return await super().generate_agent_move(task, agent_state)


def _council(refuses_for: Sequence[str] = (), manner: str = "content",
             seats: int = 4, phase_retry: bool = True):
    """One seat per agent, so a handover is visible the moment it happens."""
    fake = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", fake) for i in range(seats)]
    registry = CouncilProviderRegistry()
    providers = [
        RecordingProvider(f"seat_{i}", refuses_for=refuses_for, manner=manner)
        for i in range(seats)
    ]
    for provider in providers:
        registry.register(provider)
    ced = CEDOrchestrator(agents, fake, registry=registry, phase_retry=phase_retry)
    return ced, providers


def _seats_by_agent(providers: Iterable[RecordingProvider]) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = defaultdict(set)
    for provider in providers:
        for agent_id, _kind, _attempt, _phase in provider.seen:
            out[agent_id].add(provider.provider_id)
    return dict(out)


def _attempts_for(providers: Iterable[RecordingProvider], agent_id: str) -> List[int]:
    return [
        attempt
        for provider in providers
        for aid, _kind, attempt, _phase in provider.seen
        if aid == agent_id
    ]


def _phases(ced, session_id: str) -> List[str]:
    return [m.phase.value for m in ced.get_session(session_id).moves]


# --------------------------------------------------------------- binding ----


def test_a_logical_agent_reaches_exactly_one_seat_all_session():
    """The binding invariant, checked at the wire rather than in a record."""
    ced, providers = _council()
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="binding_clean"))
    seats = _seats_by_agent(providers)
    assert seats, "nothing was dispatched"
    for agent_id, reached in seats.items():
        assert len(reached) == 1, (
            f"{agent_id} was served by {sorted(reached)}; a logical agent is "
            "bound to one seat for the life of the session"
        )
    rulings = [
        (provider.provider_id, agent_id, task_id)
        for provider in providers
        for agent_id, kind, task_id in provider.seen_tasks
        if kind == TaskKind.OBJECTION_VERIFICATION.value
    ]
    assert rulings, "the objection-ruling path was not exercised"
    assert len({task_id for _provider, _agent, task_id in rulings}) == len(rulings)
    for provider_id, agent_id, task_id in rulings:
        assert seats[agent_id] == {provider_id}
        assert task_id.endswith(f"_{provider_id}")


@pytest.mark.parametrize("manner", ["content", "silence"])
def test_a_refusing_agents_task_never_reaches_another_seat(manner):
    """Whether it spoke and said nothing, or never spoke, it stays put.

    The old rescue drew this distinction and sent the silent one onward at once.
    That is the cross-seat handover, and it is gone in both manners.
    """
    ced, providers = _council(refuses_for=["agent_0"], manner=manner)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id=f"bind_{manner}"))
    seats = _seats_by_agent(providers)
    assert len(seats.get("agent_0", set())) == 1, (
        f"agent_0's task was handed to {sorted(seats.get('agent_0', set()))}"
    )


# ------------------------------------------------------------- voice loss ----


@pytest.mark.parametrize("manner", ["content", "silence"])
def test_a_second_failure_ends_it_and_nothing_is_handed_on(manner):
    """The exact sequence that must hold, start to finish.

    agent_0 fails, the same seat is asked once more, it fails again, the voice
    is lost, and no third call is made to anyone.
    """
    ced, providers = _council(refuses_for=["agent_0"], manner=manner)
    session = f"voice_{manner}"
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id=session))

    attempts = _attempts_for(providers, "agent_0")
    assert attempts, "agent_0 was never asked at all"
    assert 1 in attempts, "the same seat was never asked a second time"
    assert 2 not in attempts, (
        f"a third attempt was dispatched: {attempts}. Two is the whole doctrine."
    )
    assert len(_seats_by_agent(providers)["agent_0"]) == 1


def test_the_lost_voice_is_named_in_the_record():
    """A voice that is lost silently is the failure this all started from."""
    ced, _providers = _council(refuses_for=["agent_0"])
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="voice_record"))
    retries = ced._phase_retries.get("voice_record", [])
    assert retries, "no rescue was recorded at all"
    assert any(r["voice_lost_slots"] for r in retries), (
        "a seat failed twice and the record does not say a voice was lost"
    )
    assert all("rerouted_distinct_seat_slots" not in r for r in retries), (
        "the record still carries a reroute field for a mechanism that is gone"
    )


def test_a_first_failure_is_asked_again_at_the_same_seat_and_can_recover():
    """Asking twice is the elenchus; the doctrine is not merely a restriction."""

    class RecoversOnRetry(RecordingProvider):
        async def generate_agent_move(self, task, agent_state):
            if task.agent_id in self.refuses_for and task.attempt_index == 0:
                return await super().generate_agent_move(task, agent_state)
            self.seen.append(
                (task.agent_id, task.task_kind.value, task.attempt_index,
                 task.phase.value)
            )
            return await ScriptedMockProvider.generate_agent_move(
                self, task, agent_state
            )

    fake = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", fake) for i in range(4)]
    registry = CouncilProviderRegistry()
    providers = [RecoversOnRetry(f"seat_{i}", refuses_for=["agent_0"])
                 for i in range(4)]
    for provider in providers:
        registry.register(provider)
    ced = CEDOrchestrator(agents, fake, registry=registry, phase_retry=True)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="recovers"))

    retries = ced._phase_retries.get("recovers", [])
    assert retries, "the rescue never fired"
    assert any(r["retry_ok_providers"] for r in retries), (
        "the second ask at the same seat produced nothing"
    )
    assert all(not r["voice_lost_slots"] for r in retries), (
        "a voice that answered on the second ask is not lost"
    )
    assert all(not r["quorum_held_but_a_voice_was_lost"] for r in retries), (
        "a recovered voice must not remain labelled as lost"
    )
    assert len(_seats_by_agent(providers)["agent_0"]) == 1


# ---------------------------------------------------------------- quorum ----


#: Role assignment derives from the session id, so the id decides which seat
#: holds the opening Socratic chair. Under this one agent_0 does not hold it,
#: which is the case this test is about: a lost voice that quorum can absorb.
#: A run where the refusing seat opens is the fail-closed case below, and the
#: two must not be conflated - the first says quorum works, the second says the
#: dialogue cannot start without its first question.
SESSION_WHERE_THE_REFUSER_IS_NOT_THE_OPENER_V1 = "quorum_survives_a_lost_voice"


def test_retry_disabled_records_terminal_loss_without_redispatch():
    """Q7's policy forbids a second ask; the first failure is therefore final."""
    ced, providers = _council(
        refuses_for=["agent_0"],
        phase_retry=False,
    )
    session = SESSION_WHERE_THE_REFUSER_IS_NOT_THE_OPENER_V1
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id=session))

    attempts = _attempts_for(providers, "agent_0")
    assert attempts and set(attempts) == {0}, (
        f"retry-disabled policy dispatched another attempt: {attempts}"
    )
    assert "synthesis" in _phases(ced, session), (
        "the council had quorum but did not proceed after naming the lost voice"
    )

    records = ced._phase_retries.get(session, [])
    opening_loss = next(
        record for record in records if record["phase"] == "initial_response"
    )
    assert opening_loss == {
        "phase": "initial_response",
        "failed_slots": [0],
        "reasked_same_seat_slots": [],
        "voice_lost_slots": [0],
        "quorum_held_but_a_voice_was_lost": True,
        "first_failed_providers": ["seat_0"],
        "retry_ok_providers": [],
        "rescued": False,
    }


def test_quorum_decides_whether_the_phase_proceeds_not_who_answers():
    """One voice lost out of four: the phase goes on, short of a voice."""
    ced, providers = _council(refuses_for=["agent_0"])
    session = SESSION_WHERE_THE_REFUSER_IS_NOT_THE_OPENER_V1
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id=session))
    assert "agent_0" not in [m.agent_id for m in ced.get_session(session).moves
                             if m.phase.value == "opening"], (
        "the id no longer puts another seat in the opening chair"
    )
    phases = _phases(ced, session)
    assert "synthesis" in phases, (
        f"quorum held and the session still did not finish: {sorted(set(phases))}"
    )
    assert len(_seats_by_agent(providers)["agent_0"]) == 1, (
        "the phase proceeded by moving a task rather than by counting quorum"
    )
    retries = ced._phase_retries.get(session, [])
    assert any(r["voice_lost_slots"] for r in retries), (
        "the session finished without recording that a voice was missing"
    )


def test_a_refusing_opener_stops_a_run_that_has_no_replacement_task():
    """The opening question is role-critical, and its chair does not move.

    Scoped deliberately: this is what a council with no authorized replacement
    task does, not a law that a dead Socratic seat must always end every CED
    dialogue. The termination is pre-existing generic behaviour - REFLECTION has
    never run without an accepted Socratic question - and what changed is only
    that the handover no longer masks it. A protocol that authorizes a NEW
    Socratic task, with its own id, owner and provenance, may finish; nothing
    here forbids that.
    """
    ced, providers = _council(refuses_for=["agent_0"])
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="quorum_holds"))
    assert _phases(ced, "quorum_holds") == [], (
        "the dialogue started without its opening question"
    )
    assert len(_seats_by_agent(providers).get("agent_0", set())) == 1, (
        "the opening chair was moved to another seat to save the session"
    )


def test_without_quorum_the_phase_fails_closed():
    """Too few voices is a stop, never a reason to widen the search for one."""
    ced, providers = _council(refuses_for=["agent_0", "agent_1", "agent_2"])
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="quorum_fails"))
    phases = _phases(ced, "quorum_fails")
    assert "synthesis" not in phases, (
        "the session synthesised without a quorum of voices"
    )
    seats = _seats_by_agent(providers)
    for agent_id in ("agent_0", "agent_1", "agent_2"):
        reached = seats.get(agent_id, set())
        assert len(reached) <= 1, (
            f"{agent_id} was spread across {sorted(reached)} to chase a quorum"
        )


# ------------------------------------------------------------ provenance ----


def test_every_attempt_stays_in_the_record():
    """Nothing is discarded: a rescued round must not look like a clean one."""
    ced, _providers = _council(refuses_for=["agent_0"])
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="provenance"))
    retries = ced._phase_retries.get("provenance", [])
    assert retries
    for entry in retries:
        assert entry["first_failed_providers"], (
            "a rescue fired and no failing provider is named"
        )
        assert entry["failed_slots"] == entry["reasked_same_seat_slots"], (
            "every failure is asked again at its own seat, and nowhere else"
        )


def test_the_record_shape_is_exactly_the_policy():
    """The audit keys are the policy written down; no reroute survives in them."""
    ced, _providers = _council(refuses_for=["agent_0"])
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="shape"))
    retries = ced._phase_retries.get("shape", [])
    assert retries
    expected = {
        "phase", "failed_slots", "reasked_same_seat_slots",
        "voice_lost_slots", "quorum_held_but_a_voice_was_lost",
        "first_failed_providers", "retry_ok_providers", "rescued",
    }
    for entry in retries:
        assert set(entry) == expected, (
            f"unexpected {set(entry) ^ expected} in the phase retry record"
        )


def test_no_attempt_index_above_one_is_ever_built():
    """Two attempts is the whole doctrine, everywhere, for every task kind."""
    ced, providers = _council(refuses_for=["agent_0", "agent_1"])
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="attempts"))
    seen = {attempt for p in providers for _a, _k, attempt, _ph in p.seen}
    assert seen <= {0, 1}, f"attempt indices dispatched: {sorted(seen)}"
