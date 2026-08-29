"""The rulings must reach the outgoing request, not merely the helper.

The companion unit tests exercise the recorder and the injector directly. They
cannot show that ``generate_agent_move`` calls either one, and code reading is
not enough: twice in one session a confident reading of this code turned out to
be wrong, once about where the semantic floor had authority and once about which
guard was refusing calls.

So this test drives the real adapter along its real path - render, budget check,
claim mint, dispatch - and cuts only the socket. The assertion is made on the
bytes handed to dispatch, which is the last place the question can be settled:
if the ruling is in that body it reached the model, and if it is not it did not,
whatever the helpers do in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.dialogues.models import (
    AgentRole,
    AgentState,
    AgentTask,
    DialogPhase,
    TaskKind,
)
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    OBJECTION_RULING_CONTEXT_KEY_V1,
    SocratesLiveOpenRouterAdapter,
    recorded_objection_rulings_v1,
    reset_objection_rulings_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    OpenRouterSessionLedgerV1,
)

from tests_dialogues.test_socrates_zero_openrouter_acquisition_live_session_v1 import (  # noqa: E501
    PROFILE,
    _FakeResult,
    _policy,
    _session,
    _success_body,
)

SESSION_V1 = "rulings-wire-test"

RULING_RATIONALE_V1 = (
    "The original task explicitly requires a rule that for every profile names "
    "exactly one winner, never a tie, so randomized tie-breaking cannot refute "
    "claim 4."
)
RULING_CONTENT_V1 = {
    "condition_tested": "Whether randomized tie-breaking satisfies decisiveness.",
    "objection_holds": True,
    "objection_targets": "claim_4",
    "rationale": RULING_RATIONALE_V1,
    "cited_spans": ["names exactly one winner, never a tie"],
}


class _RecordingDispatch:
    """Stands in for the socket and keeps every body it was handed."""

    def __init__(self, bodies):
        self._bodies = list(bodies)
        self.seen = []

    def __call__(self, *, body_bytes, **kwargs):
        self.seen.append(body_bytes)
        return _FakeResult(self._bodies.pop(0))


def _adapter(tmp_path: Path, dispatch) -> SocratesLiveOpenRouterAdapter:
    policy = _policy()
    return SocratesLiveOpenRouterAdapter(
        provider_id="live_seat_1",
        policy=policy,
        profile=PROFILE,
        ledger=OpenRouterSessionLedgerV1(
            _session(
                policy=policy,
                operator_statement="offline wiring check; no socket is opened",
                session_id=SESSION_V1,
            )
        ),
        claim_directory=tmp_path,
        max_input_tokens=1_047_576,
        dispatch=dispatch,
    )


def _task(kind: TaskKind, role: AgentRole, phase: DialogPhase, turn: str) -> AgentTask:
    return AgentTask(
        task_id=turn,
        session_id=SESSION_V1,
        agent_id="agent_1",
        role=role,
        phase=phase,
        question="Assess this argument.",
        context={"dialogue_so_far": []},
        output_schema={"_role": "__objection_verification__", "_objection": "obj_1"},
        task_kind=kind,
    )


def _state() -> AgentState:
    return AgentState(
        agent_id="agent_1",
        primary_role=AgentRole.ELENCHUS_CRITIC,
        assigned_role=AgentRole.ELENCHUS_CRITIC,
    )


@pytest.fixture(autouse=True)
def _clean():
    reset_objection_rulings_v1(SESSION_V1)
    yield
    reset_objection_rulings_v1(SESSION_V1)


def _bodies_text(dispatch) -> list[str]:
    out = []
    for body in dispatch.seen:
        if body is None:
            continue
        out.append(body.decode("utf-8") if isinstance(body, bytes) else str(body))
    return out


def test_a_ruling_reaches_the_next_dialogue_request(tmp_path):
    """End to end through the real method: verify, then deliberate."""

    dispatch = _RecordingDispatch(
        [
            _success_body(json.dumps({"content": RULING_CONTENT_V1, "confidence": 0.9})),
            _success_body(
                json.dumps(
                    {
                        "content": {
                            "objection": "The rule proposed does not survive symmetric "
                            "profiles, so the impossibility stands as stated."
                        },
                        "confidence": 0.8,
                    }
                )
            ),
        ]
    )
    adapter = _adapter(tmp_path, dispatch)

    verification = _task(
        TaskKind.OBJECTION_VERIFICATION,
        AgentRole.ELENCHUS_CRITIC,
        DialogPhase.ELENCHUS,
        "turn_verify",
    )
    import asyncio

    asyncio.run(adapter.generate_agent_move(verification, _state()))
    assert recorded_objection_rulings_v1(SESSION_V1), (
        "generate_agent_move did not record the ruling it just received"
    )

    deliberation = _task(
        TaskKind.ELENCHUS_OBJECTION,
        AgentRole.ELENCHUS_CRITIC,
        DialogPhase.ELENCHUS,
        "turn_deliberate",
    )
    asyncio.run(adapter.generate_agent_move(deliberation, _state()))

    bodies = _bodies_text(dispatch)
    assert len(bodies) == 2, f"expected two dispatched bodies, saw {len(bodies)}"
    first, second = bodies
    assert OBJECTION_RULING_CONTEXT_KEY_V1 not in first, (
        "the verification request must not carry rulings back to the verifier"
    )
    assert OBJECTION_RULING_CONTEXT_KEY_V1 in second, (
        "the ruling never reached the deliberation request"
    )
    # The reason itself must be on the wire, not just the key.
    assert "randomized tie-breaking cannot refute" in second


def test_no_score_reaches_the_wire(tmp_path):
    """A scored verification must contribute its reason and nothing else."""

    contaminated = dict(RULING_CONTENT_V1)
    contaminated.update({"logical_rigor": 9, "epistemic_value": 8, "verdict": "accept"})
    dispatch = _RecordingDispatch(
        [
            _success_body(json.dumps({"content": contaminated, "confidence": 0.9})),
            _success_body(
                json.dumps({"content": {"objection": "Still not settled."}, "confidence": 0.7})
            ),
        ]
    )
    adapter = _adapter(tmp_path, dispatch)

    import asyncio

    asyncio.run(
        adapter.generate_agent_move(
            _task(
                TaskKind.OBJECTION_VERIFICATION,
                AgentRole.ELENCHUS_CRITIC,
                DialogPhase.ELENCHUS,
                "turn_verify",
            ),
            _state(),
        )
    )
    asyncio.run(
        adapter.generate_agent_move(
            _task(
                TaskKind.ELENCHUS_OBJECTION,
                AgentRole.ELENCHUS_CRITIC,
                DialogPhase.ELENCHUS,
                "turn_deliberate",
            ),
            _state(),
        )
    )

    second = _bodies_text(dispatch)[1]
    assert OBJECTION_RULING_CONTEXT_KEY_V1 in second
    for leaked in ("logical_rigor", "epistemic_value"):
        assert leaked not in second, f"{leaked} reached the model"


def test_the_record_says_how_many_rulings_the_request_carried(tmp_path):
    """Request size cannot answer this, so the count is written down.

    Two runs of one council diverge on their own: the seat answers differ and
    every later prompt inherits the difference, so a larger body is not evidence
    that a ruling was carried. Comparing byte counts across arms was tried and
    could not separate injection from ordinary divergence.
    """

    dispatch = _RecordingDispatch(
        [
            _success_body(json.dumps({"content": RULING_CONTENT_V1, "confidence": 0.9})),
            _success_body(
                json.dumps({"content": {"objection": "Not settled yet."}, "confidence": 0.7})
            ),
        ]
    )
    adapter = _adapter(tmp_path, dispatch)

    import asyncio

    asyncio.run(
        adapter.generate_agent_move(
            _task(
                TaskKind.OBJECTION_VERIFICATION,
                AgentRole.ELENCHUS_CRITIC,
                DialogPhase.ELENCHUS,
                "turn_verify",
            ),
            _state(),
        )
    )
    asyncio.run(
        adapter.generate_agent_move(
            _task(
                TaskKind.ELENCHUS_OBJECTION,
                AgentRole.ELENCHUS_CRITIC,
                DialogPhase.ELENCHUS,
                "turn_deliberate",
            ),
            _state(),
        )
    )

    rows = adapter.observability_rows()
    assert len(rows) == 2
    assert rows[0]["objection_rulings_in_context"] == 0, (
        "the verification request itself carries no rulings"
    )
    assert rows[1]["objection_rulings_in_context"] == 1, (
        "the deliberation request carried the ruling and must say so"
    )
