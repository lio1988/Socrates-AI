"""Provider-OK is not CED acceptance for a Socratic move."""

from __future__ import annotations

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
    ShadowScoringMode,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
    parse_and_validate_move,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.socratic import (
    InquiryState,
    MaieuticOperator,
    validate_socratic_content,
)


PUBLIC = {
    "commitment": {"cmt_live"},
    "critique": {"move_critique"},
    "aporia": set(),
    "socratic_question": {"move_opening"},
}


def _opening(**updates):
    content = {
        "question": "Which premise should the council state first?",
        "operator": MaieuticOperator.ELICIT_COMMITMENT.value,
    }
    content.update(updates)
    return content


def _followup(**updates):
    content = {
        "question": "What follows from the commitment you just made?",
        "operator": MaieuticOperator.DRAW_CONSEQUENCE.value,
        "grounded_in": [{"ref_type": "commitment", "ref_id": "cmt_live"}],
        "introduces_new_proposition": False,
        "inquiry_state": InquiryState.CONTINUE_INQUIRY.value,
    }
    content.update(updates)
    return content


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ({}, "question must be a string"),
        (_opening(question=""), "question must be non-empty"),
        (_opening(question="   \t"), "question must be non-empty"),
        (_opening(question=17), "question must be a string"),
        (_opening(operator=None), "canonical maieutic operator"),
        (_opening(operator="invented_operator"), "canonical maieutic operator"),
    ],
)
def test_opening_contract_rejects_missing_or_malformed_question_fields(content, reason):
    result = validate_socratic_content(content, followup=False)
    assert result.accepted is False
    assert reason in result.reason


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (_followup(grounded_in=None), "non-empty list"),
        (_followup(grounded_in=[]), "non-empty list"),
        (_followup(grounded_in=["not-a-reference"]), "malformed reference"),
        (_followup(grounded_in=[{"ref_type": "unknown", "ref_id": "x"}]),
         "malformed reference"),
        (_followup(grounded_in=[{"ref_type": "commitment", "ref_id": "missing"}]),
         "unresolved reference"),
        (_followup(introduces_new_proposition="false"), "must be a boolean"),
        (_followup(introduces_new_proposition=True), "may not introduce"),
        (_followup(inquiry_state="unknown"), "canonical inquiry state"),
    ],
)
def test_followup_contract_rejects_invalid_epistemic_fields(content, reason):
    result = validate_socratic_content(
        content, followup=True, public_ids=PUBLIC
    )
    assert result.accepted is False
    assert reason in result.reason


def test_opening_and_fully_grounded_followup_are_distinct_valid_contracts():
    opening = validate_socratic_content(_opening(), followup=False)
    followup = validate_socratic_content(
        _followup(), followup=True, public_ids=PUBLIC
    )
    assert opening.accepted and opening.grounded_in == ()
    assert followup.accepted
    assert followup.grounded_in == (("commitment", "cmt_live"),)


class EmptySocrates(ScriptedMockProvider):
    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is TaskKind.SOCRATIC_QUESTION:
            return json.dumps({"content": {}, "confidence": 0.7})
        return await super()._produce_raw_text(task, agent_state)


def _council() -> CEDOrchestrator:
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(4):
        registry.register(EmptySocrates(f"seat{index}"))
    return CEDOrchestrator(
        [SocraticAgent(f"a{index}", provider) for index in range(4)],
        provider,
        registry=registry,
        phase_retry=True,
        shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
    )


def test_provider_ok_empty_question_never_receives_an_accepted_move_id():
    task = AgentTask(
        session_id="s",
        agent_id="a",
        role=AgentRole.SOCRATES,
        phase=DialogPhase.OPENING,
        question="What is knowledge?",
        task_kind=TaskKind.SOCRATIC_QUESTION,
    )
    move, status, error = parse_and_validate_move(
        json.dumps({"content": {}, "confidence": 0.7}), task
    )
    assert status.value == "ok" and error is None and move is not None

    ced = _council()
    final = asyncio.run(
        ced.run_registry_session("What is knowledge?", session_id="empty-socrates")
    )
    state = ced.get_session("empty-socrates")

    assert [move for move in state.moves if move.role is AgentRole.SOCRATES] == []
    question_tasks = [
        entry for entry in state.task_log
        if entry.task_kind is TaskKind.SOCRATIC_QUESTION
    ]
    assert question_tasks
    assert all(entry.move_id is None for entry in question_tasks)
    assert [move for move in state.moves if move.phase is DialogPhase.REFLECTION] == []
    assert final.synthesis is not None
    rows = ced._socratic_audit_rows[state.session_id]
    assert rows
    assert all(row["content_contract_accepted"] is False for row in rows)
