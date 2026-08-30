"""A seat that answers with nothing must not end the dialectic.

This reproduces a real failure rather than waiting for it to happen again. In
the Q4 opener experiment Gemini returned ``{"confidence": 0.5, "content": {}}``
on an elenchus Socratic turn - HTTP 200, 956 tokens, seven required fields
absent. With no accepted question there is nothing for REFLECTION to answer, so
ced.py refused to reuse an older one and the cycle closed. One silent turn from
one seat truncated every remaining round, and the council reached its verdict on
half a dialogue.

The point of scripting it here is that a live run cannot be relied on to show
this. Across six Q4 councils there was exactly one empty answer, and a run that
happens not to produce one proves nothing about the rescue: it was simply never
needed. Constructing the silence makes the answer deterministic, repeatable and
free, and turns a one-off observation into a standing guarantee.

The failure scripted is deliberately the *content* kind, not a timeout: a seat
that answered and was refused has said something a second answer can contradict,
which is exactly what asking again tests.

The question never passes on. That distinction - re-ask a seat that spoke, hand
on a seat that went quiet - was how this file read until the handover was
removed altogether. Both kinds of failure now get the same one re-ask at their
own seat, and a second failure is a lost voice, because a task is bound to one
logical agent at one seat for its whole life.
"""

from __future__ import annotations

import asyncio
from typing import Optional

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

#: Role assignment derives from the session id, so the id decides which seat
#: holds the Socratic chair - the same positional fact that put Gemini in every
#: Q4 opening and Llama 4 Maverick in the one council that died at its first
#: call. This id is one under which the silent seat holds it, so the test
#: exercises the path it means to exercise instead of depending on a hash.
SESSION_WITH_SILENT_SOCRATES_V1 = "silent_once"

#: Verbatim from the live record, Q4 opener experiment, elenchus/socrates.
OBSERVED_EMPTY_ANSWER_V1 = '{"confidence":0.5,"content":{\n    }\n}'


class SilentOnSocraticProvider(ScriptedMockProvider):
    """Answers everything normally, and says nothing when asked to ask.

    Provider status stays OK, exactly as it did live: the seat is reachable and
    replies, and the reply carries no usable question. That is what makes this
    different from a timeout, and why the seat is asked again rather than
    replaced.
    """

    def __init__(self, provider_id: str, silent_attempts: int = 1, **kw) -> None:
        super().__init__(provider_id=provider_id, **kw)
        self.silent_attempts = silent_attempts
        self.socratic_calls = 0
        self.attempts_seen: list[int] = []

    async def generate_agent_move(self, task, agent_state) -> ProviderResponse:
        if task.task_kind is TaskKind.SOCRATIC_QUESTION:
            self.socratic_calls += 1
            self.attempts_seen.append(task.attempt_index)
            if self.socratic_calls <= self.silent_attempts:
                return ProviderResponse(
                    provider_id=self.provider_id,
                    agent_id=task.agent_id,
                    status=ProviderStatus.OK,
                    raw_text=OBSERVED_EMPTY_ANSWER_V1,
                    parsed_move=None,
                    error_message="empty content object",
                )
        return await super().generate_agent_move(task, agent_state)


def _council(*, phase_retry: bool, silent_attempts: int):
    fake = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", fake) for i in range(4)]
    registry = CouncilProviderRegistry()
    silent = SilentOnSocraticProvider("m_silent", silent_attempts=silent_attempts)
    registry.register(silent)
    registry.register(ScriptedMockProvider("m_ok"))
    ced = CEDOrchestrator(agents, fake, registry=registry, phase_retry=phase_retry)
    return ced, silent


def _phases(ced, session_id: str) -> list[str]:
    state = ced.get_session(session_id)
    return [m.phase.value for m in state.moves]


def test_without_rescue_one_silent_answer_ends_the_dialectic():
    """The failure as it actually happened, so the fix has something to fix."""

    ced, silent = _council(phase_retry=False, silent_attempts=99)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="silent_off"))
    assert silent.socratic_calls >= 1, "the silent seat was never asked"
    assert silent.attempts_seen == [0] * silent.socratic_calls, (
        "with rescue off nothing may be asked a second time"
    )
    assert "reflection" not in _phases(ced, "silent_off"), (
        "REFLECTION cannot run without an accepted Socratic question"
    )
    losses = ced._phase_retries.get("silent_off", [])
    assert losses, "retry-disabled silence vanished from the audit"
    assert all(record["reasked_same_seat_slots"] == [] for record in losses)
    assert any(record["voice_lost_slots"] for record in losses)


def test_the_same_seat_is_asked_again_before_the_question_moves_on():
    """A first silence may be misunderstanding, so the question is repeated."""

    ced, silent = _council(phase_retry=True, silent_attempts=1)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id=SESSION_WITH_SILENT_SOCRATES_V1))
    assert 1 in silent.attempts_seen, (
        "the seat that fell silent was never asked a second time"
    )
    retries = ced._phase_retries.get(SESSION_WITH_SILENT_SOCRATES_V1, [])
    assert retries, "no rescue was recorded"
    assert any(r["reasked_same_seat_slots"] for r in retries)


def test_a_seat_silent_twice_loses_its_voice():
    """A second silence after being asked again ends it, and is recorded.

    This asserted the opposite: that the question passed to a different seat.
    It does not any more. What a second silence buys is an entry saying which
    argument the council never heard, which is the thing that was missing when
    a seat dropped out of a live Q5 phase and nothing said so.
    """

    ced, silent = _council(phase_retry=True, silent_attempts=99)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id=SESSION_WITH_SILENT_SOCRATES_V1))
    assert silent.attempts_seen[:2] == [0, 1], (
        f"expected the same seat asked twice, saw {silent.attempts_seen[:2]}"
    )
    assert 2 not in silent.attempts_seen, "a third attempt was dispatched"
    retries = ced._phase_retries.get(SESSION_WITH_SILENT_SOCRATES_V1, [])
    assert any(r["voice_lost_slots"] for r in retries), (
        "a seat fell silent twice and no voice was recorded as lost"
    )


def test_the_dialectic_survives_a_silent_seat():
    """The point of all of it: the remaining rounds still happen."""

    ced, _silent = _council(phase_retry=True, silent_attempts=1)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="silent_survive"))
    assert "reflection" in _phases(ced, "silent_survive"), (
        "one silent answer still truncated the dialogue"
    )


def test_every_attempt_stays_in_the_record():
    """Nothing is discarded - that is what separates this from laundering."""

    ced, silent = _council(phase_retry=True, silent_attempts=1)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="silent_record"))
    retries = ced._phase_retries.get("silent_record", [])
    assert retries
    for entry in retries:
        assert "first_failed_providers" in entry
        assert "reasked_same_seat_slots" in entry
        assert "voice_lost_slots" in entry
    assert silent.attempts_seen, "the silent seat's attempts were not observable"


def test_a_lost_voice_is_asked_again_even_when_quorum_holds():
    """Quorum decides whether the phase proceeds. Nothing else.

    A seat could fail and never be asked again, because two of three voices were
    enough for the phase to go on. Quorum is the right test for a vote and the
    wrong one for a dialectic, where each seat is an argument rather than a
    ballot: a missing argument is worth asking for twice whether or not the
    count already stands.
    """

    ced, silent = _council(phase_retry=True, silent_attempts=99)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id=SESSION_WITH_SILENT_SOCRATES_V1))
    retries = ced._phase_retries.get(SESSION_WITH_SILENT_SOCRATES_V1, [])
    assert any(r["reasked_same_seat_slots"] for r in retries), (
        "a seat failed and was never asked again"
    )
    assert silent.attempts_seen[:2] == [0, 1]


def test_a_seat_that_went_quiet_is_asked_again_at_its_own_seat_too():
    """A timeout and a refused answer are now treated the same way.

    They were not. A seat that never spoke was handed on immediately, on the
    reasoning that re-dialling a dead line is an infrastructure retry rather
    than an elenchus. That reasoning is sound about what a re-ask *means* and
    irrelevant to where the task may go: handing it on changes which agent
    answers, which is the binding, and the binding is not ours to trade for a
    better chance of an answer.
    """

    from backend.dialogues.provider_registry import TimeoutScriptedProvider

    fake = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", fake) for i in range(4)]
    registry = CouncilProviderRegistry()
    dead = TimeoutScriptedProvider()
    registry.register(dead)
    registry.register(ScriptedMockProvider("m_ok"))
    ced = CEDOrchestrator(agents, fake, registry=registry, phase_retry=True)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id="timeout_label"))
    records = ced._phase_retries.get("timeout_label", [])
    assert records, "the rescue never fired"
    for entry in records:
        assert entry["reasked_same_seat_slots"] == entry["failed_slots"], (
            "a seat that went quiet was not asked again at its own seat"
        )
        assert entry["voice_lost_slots"], (
            "the line stayed quiet and no voice was recorded as lost"
        )
        assert "m_ok" not in entry["retry_ok_providers"], (
            "the healthy seat answered in place of the one that went quiet"
        )


def test_an_existing_task_stays_at_its_seat_without_a_protocol_switch():
    """A task_id keeps its binding by default, not by configuration.

    Q2d binds one physical seat to each logical agent and prices the run on that
    binding, so its pre-dispatch guard refuses any task arriving at the wrong
    seat: "deliberation task is not bound to agent_1". A live council paid for
    that - every handed-on task was refused at the wire and the run collapsed at
    four calls - and the repair was briefly a per-protocol switch.

    A switch was the wrong shape for THIS invariant. Whether an existing task_id
    may change its logical agent, seat and model is not a protocol preference:
    it is what the run was authorized and priced on, and leaving it reachable by
    default meant every protocol that had not thought about it inherited the
    unsafe path.

    That is a narrow claim, and deliberately so. It says nothing about whether a
    protocol may authorize a NEW task to cover a lost voice - new task_id, new
    logical owner, explicit authorization, its own provenance. That remains open
    and is where coverage belongs; what is closed is moving an existing task.
    """

    ced, silent = _council(phase_retry=True, silent_attempts=99)
    asyncio.run(ced.run_registry_session(QUESTION_V1, session_id=SESSION_WITH_SILENT_SOCRATES_V1))
    retries = ced._phase_retries.get(SESSION_WITH_SILENT_SOCRATES_V1, [])
    assert retries, "the rescue did not run at all"
    assert 1 in silent.attempts_seen, "the seat was not asked again"
    assert 2 not in silent.attempts_seen, "a third attempt was dispatched"
    assert any(r["voice_lost_slots"] for r in retries), (
        "the lost voice was not recorded"
    )
