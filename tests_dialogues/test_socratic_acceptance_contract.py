"""Provider success is not CED acceptance for a Socratic move."""

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
from backend.dialogues.reasoning_prompts import (
    OPENING_CONTENT_DIRECTIVE,
    SOCRATIC_FOLLOWUP_MANDATE,
)
from backend.dialogues.socratic import (
    InquiryState,
    MaieuticOperator,
    validate_socratic_content,
)


ORIGINAL = (
    "If four independent and capable researchers agree on the same conclusion, "
    "under what conditions, if any, should their agreement count as knowledge "
    "rather than merely a shared error?"
)
SOLICITING_Q2 = (
    "What criteria could verify that the researchers are sufficiently independent?"
)
LIVE_Q2 = (
    "Given the critiques regarding the difficulty of establishing genuine "
    "independence among researchers, what specific criteria or methods could be "
    "employed to effectively verify their independence and minimize the risk of "
    "correlated biases in their conclusions?"
)
PUBLIC = {
    "commitment": {"cmt_live"},
    "critique": {"move_critique", "move_2fff3f6bcc4e"},
    "aporia": set(),
    "socratic_question": {"move_opening"},
}
_MISSING = object()


def _opening(**updates):
    content = {
        "question": "Which premise should the council state first?",
        "operator": MaieuticOperator.EXPOSE_PREMISE.value,
        "epistemic_marker": "open_uncertainty",
    }
    for key, value in updates.items():
        if value is _MISSING:
            content.pop(key, None)
        else:
            content[key] = value
    return content


def _followup(**updates):
    content = {
        "question": "What follows from the commitment you just made?",
        "operator": MaieuticOperator.DRAW_CONSEQUENCE.value,
        "grounded_in": [{"ref_type": "commitment", "ref_id": "cmt_live"}],
        "introduces_new_proposition": False,
        "inquiry_state": InquiryState.CONTINUE_INQUIRY.value,
        "epistemic_marker": "open_uncertainty",
    }
    for key, value in updates.items():
        if value is _MISSING:
            content.pop(key, None)
        else:
            content[key] = value
    return content


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ([], "content must be an object"),
        ({}, "question must be a string"),
        (_opening(question=_MISSING), "question must be a string"),
        (_opening(question=""), "question must be non-empty"),
        (_opening(question="   \t"), "question must be non-empty"),
        (_opening(question=17), "question must be a string"),
        (_opening(operator=_MISSING), "canonical maieutic operator"),
        (_opening(operator="invented_operator"), "canonical maieutic operator"),
        (_opening(operator="EXPOSE_PREMISE"), "canonical maieutic operator"),
        (_opening(epistemic_marker=_MISSING), "epistemic_marker is required"),
        (_opening(epistemic_marker="hypothesis"), "must be canonical"),
        (_opening(epistemic_marker="OPEN_UNCERTAINTY"), "must be canonical"),
        (_opening(epistemic_marker=3), "epistemic_marker must be a string"),
        (_opening(introduces_new_proposition="false"), "must be a boolean"),
        (_opening(introduces_new_proposition=True), "may solicit new propositions"),
    ],
)
def test_opening_contract_rejects_malformed_content(content, reason):
    result = validate_socratic_content(content, followup=False)
    assert result.accepted is False
    assert reason in result.reason


def test_exact_original_task_is_a_valid_opening_when_structure_is_valid():
    result = validate_socratic_content(
        _opening(question=ORIGINAL),
        followup=False,
    )
    assert result.accepted is True
    assert result.question == ORIGINAL
    assert result.operator is MaieuticOperator.EXPOSE_PREMISE
    assert result.epistemic_marker.value == "open_uncertainty"


def test_q2_style_solicitation_and_entirely_public_grounding_are_valid():
    result = validate_socratic_content(
        _followup(
            question=SOLICITING_Q2,
            operator=MaieuticOperator.REQUEST_GROUNDS.value,
            grounded_in=[
                {"ref_type": "commitment", "ref_id": "cmt_live"},
                {"ref_type": "critique", "ref_id": "move_critique"},
            ],
        ),
        followup=True,
        public_ids=PUBLIC,
    )
    assert result.accepted is True
    assert result.grounded_in == (
        ("commitment", "cmt_live"),
        ("critique", "move_critique"),
    )
    assert result.introduces_new_proposition is False


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (_followup(grounded_in=_MISSING), "non-empty list"),
        (_followup(grounded_in=[]), "non-empty list"),
        (_followup(grounded_in=["not-a-reference"]), "malformed reference"),
        (_followup(grounded_in=[{"ref_type": "unknown", "ref_id": "x"}]),
         "malformed reference"),
        (_followup(grounded_in=[{"ref_type": "commitment", "ref_id": 1}]),
         "malformed reference"),
        (_followup(grounded_in=[{"ref_type": "commitment", "ref_id": " "}]),
         "malformed reference"),
        (_followup(grounded_in=[{"ref_type": "commitment", "ref_id": "missing"}]),
         "unresolved reference"),
        (_followup(grounded_in=[
            {"ref_type": "commitment", "ref_id": "cmt_live"},
            {"ref_type": "critique", "ref_id": "missing"},
        ]), "unresolved reference"),
        (_followup(introduces_new_proposition=_MISSING), "must be a boolean"),
        (_followup(introduces_new_proposition="false"), "must be a boolean"),
        (_followup(introduces_new_proposition=0), "must be a boolean"),
        (_followup(introduces_new_proposition=1), "must be a boolean"),
        (_followup(introduces_new_proposition=None), "must be a boolean"),
        (_followup(introduces_new_proposition=True), "may solicit new propositions"),
        (_followup(inquiry_state=_MISSING), "canonical inquiry state"),
        (_followup(inquiry_state="unknown"), "canonical inquiry state"),
        (_followup(inquiry_state="CONTINUE_INQUIRY"), "canonical inquiry state"),
    ],
)
def test_followup_contract_rejects_malformed_or_unsafe_content(content, reason):
    result = validate_socratic_content(
        content,
        followup=True,
        public_ids=PUBLIC,
    )
    assert result.accepted is False
    assert reason in result.reason


def test_malformed_grounding_prefix_is_not_misreported_as_resolved():
    result = validate_socratic_content(
        _followup(grounded_in=[
            {"ref_type": "commitment", "ref_id": "missing"},
            "not-a-reference",
        ]),
        followup=True,
        public_ids=PUBLIC,
    )
    assert result.accepted is False
    assert result.grounded_in == ()
    assert result.unresolved_grounding == ()


def test_archived_q2_true_is_rejected_for_its_declaration_not_its_question_text():
    valid = validate_socratic_content(
        _followup(
            question=LIVE_Q2,
            operator=MaieuticOperator.REQUEST_GROUNDS.value,
            grounded_in=[{"ref_type": "critique",
                          "ref_id": "move_2fff3f6bcc4e"}],
            introduces_new_proposition=False,
        ),
        followup=True,
        public_ids=PUBLIC,
    )
    mislabeled = validate_socratic_content(
        _followup(
            question=LIVE_Q2,
            operator=MaieuticOperator.REQUEST_GROUNDS.value,
            grounded_in=[{"ref_type": "critique",
                          "ref_id": "move_2fff3f6bcc4e"}],
            introduces_new_proposition=True,
        ),
        followup=True,
        public_ids=PUBLIC,
    )
    assert valid.accepted is True
    assert mislabeled.accepted is False
    assert "may solicit new propositions" in mislabeled.reason
    assert mislabeled.grounded_in == (("critique", "move_2fff3f6bcc4e"),)


def test_prompt_distinguishes_soliciting_from_supplying_a_proposition():
    prompt = " ".join(SOCRATIC_FOLLOWUP_MANDATE.split())
    assert "QUESTION ITSELF" in prompt
    assert "criteria, methods, alternatives, consequences, distinctions, or explanations" in prompt
    assert "declaration, not proof" in prompt


def test_local_socratic_base_contract_names_every_opening_field():
    for field in ("question", "operator", "epistemic_marker"):
        assert f'"{field}"' in OPENING_CONTENT_DIRECTIVE


def test_active_generic_parser_marker_contract_is_preserved():
    ordinary = AgentTask(
        session_id="s",
        agent_id="a",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.INITIAL_RESPONSE,
        question="q",
        task_kind=TaskKind.INITIAL_RESPONSE,
    )
    for content in (
        {"thesis": "x"},
        {"thesis": "x", "epistemic_marker": "not_canonical"},
        {"thesis": "x", "epistemic_marker": 3},
    ):
        move, status, error = parse_and_validate_move(
            json.dumps({"content": content, "confidence": 0.7}),
            ordinary,
            meta={},
        )
        assert move is None
        assert status.value == "schema_error"
        assert error is not None and "epistemic_marker" in error

    move, status, error = parse_and_validate_move(
        json.dumps({"content": {
            "thesis": "x",
            "epistemic_marker": "reasonable_hypothesis",
        }, "confidence": 0.7}),
        ordinary,
        meta={},
    )
    assert status.value == "ok" and error is None and move is not None


class InvalidOpeningMarkerSocrates(ScriptedMockProvider):
    def __init__(self, provider_id, marker):
        super().__init__(provider_id)
        self._marker = marker

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if (task.task_kind is TaskKind.SOCRATIC_QUESTION
                and task.phase is DialogPhase.OPENING):
            content = _opening(question=task.question)
            if self._marker is _MISSING:
                content.pop("epistemic_marker")
            else:
                content["epistemic_marker"] = self._marker
            return json.dumps({"content": content, "confidence": 0.5})
        return await super()._produce_raw_text(task, agent_state)


@pytest.mark.parametrize(
    "marker",
    [_MISSING, "hypothesis", "unknown_marker", "OPEN_UNCERTAINTY", 3],
    ids=["missing", "invalid", "unknown", "noncanonical", "non-string"],
)
def test_invalid_socratic_markers_receive_no_public_move_identity(marker):
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(4):
        registry.register(InvalidOpeningMarkerSocrates(f"seat{index}", marker))
    ced = CEDOrchestrator(
        [SocraticAgent(f"a{index}", provider) for index in range(4)],
        provider,
        registry=registry,
    )
    state = ced.create_session(ORIGINAL, session_id=f"marker-{id(marker)}")

    asyncio.run(ced._run_registry_phase(state, DialogPhase.OPENING, 5.0))

    assert [move for move in state.moves if move.role is AgentRole.SOCRATES] == []
    question_tasks = [
        entry for entry in state.task_log
        if entry.task_kind is TaskKind.SOCRATIC_QUESTION
    ]
    assert len(question_tasks) == 1
    assert question_tasks[0].move_id is None
    assert question_tasks[0].provider_status.value == "schema_error"
    assert state.session_id not in ced._socratic_audit_rows

    content = _opening()
    if marker is _MISSING:
        content.pop("epistemic_marker")
    else:
        content["epistemic_marker"] = marker
    local = validate_socratic_content(content, followup=False)
    assert local.accepted is False


class SelfDeclaringSecondCycleSocrates(ScriptedMockProvider):
    """The exact Q2 is valid with false, then self-declared invalid with true."""

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is not TaskKind.SOCRATIC_QUESTION:
            return await super()._produce_raw_text(task, agent_state)
        if task.phase is DialogPhase.OPENING:
            return json.dumps({"content": _opening(question=task.question),
                               "confidence": 0.5})
        critiques = task.context.get("elenchus_critiques") or []
        return json.dumps({"content": _followup(
            question=LIVE_Q2,
            operator=MaieuticOperator.REQUEST_GROUNDS.value,
            grounded_in=[{"ref_type": "critique",
                          "ref_id": critiques[0]["critique_id"]}],
            introduces_new_proposition=task.round_number > 0,
            inquiry_state=InquiryState.CONTINUE_INQUIRY.value,
        ), "confidence": 0.5})


def _invalid_second_cycle_council() -> CEDOrchestrator:
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(4):
        registry.register(SelfDeclaringSecondCycleSocrates(f"seat{index}"))
    return CEDOrchestrator(
        [SocraticAgent(f"a{index}", provider) for index in range(4)],
        provider,
        registry=registry,
        phase_retry=True,
        max_socratic_followups=2,
        shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
    )


def test_contract_rejection_uses_bounded_retry_and_never_reuses_stale_question():
    ced = _invalid_second_cycle_council()
    final = asyncio.run(ced.run_registry_session(
        ORIGINAL,
        session_id="contract-retry-no-stale-reflection",
    ))
    state = ced.get_session("contract-retry-no-stale-reflection")

    accepted_questions = [
        move.content["question"]
        for move in state.moves
        if move.role is AgentRole.SOCRATES
    ]
    assert accepted_questions[:2] == [ORIGINAL, LIVE_Q2]

    rejected = [
        entry for entry in state.task_log
        if (entry.task_kind is TaskKind.SOCRATIC_QUESTION
            and entry.phase is DialogPhase.ELENCHUS
            and entry.round_index == 1)
    ]
    assert {entry.attempt_index for entry in rejected} == {0, 1}
    assert all(entry.move_id is None for entry in rejected)
    assert all(entry.provider_status.value == "ok" for entry in rejected)
    assert not [
        move for move in state.moves
        if (move.role is AgentRole.SOCRATES
            and move.phase is DialogPhase.ELENCHUS
            and move.attempt_index == 1)
    ]
    assert not [
        entry for entry in state.task_log
        if entry.phase is DialogPhase.REFLECTION and entry.round_index == 1
    ]
    retries = [
        row for row in ced._phase_retries.get(state.session_id, [])
        if row["phase"] == DialogPhase.ELENCHUS.value
    ]
    assert retries[-1]["retried_slots"] == retries[-1]["failed_slots"]
    assert retries[-1]["rescued"] is False
    rejected_rows = [
        row for row in ced._socratic_audit_rows[state.session_id]
        if row["phase"] == DialogPhase.ELENCHUS.value and row["cycle"] == 1
    ]
    assert {row["self_declared_new_proposition"] for row in rejected_rows} == {True}
    assert all(row["content_contract_accepted"] is False for row in rejected_rows)
    assert all("may solicit new propositions" in row["content_contract_reason"]
               for row in rejected_rows)
    assert all(row["is_grounded"] is True for row in rejected_rows)
    assert all(row["grounded_in_resolved"] for row in rejected_rows)
    assert final.synthesis is not None


class EmptySocrates(ScriptedMockProvider):
    """Provider-valid envelope whose Socratic question fails the CED contract."""

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is TaskKind.SOCRATIC_QUESTION:
            return json.dumps({"content": {
                "question": "",
                "operator": MaieuticOperator.CLARIFY.value,
                "epistemic_marker": "open_uncertainty",
            }, "confidence": 0.7})
        return await super()._produce_raw_text(task, agent_state)


def _empty_question_council() -> CEDOrchestrator:
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(4):
        registry.register(EmptySocrates(f"empty-seat{index}"))
    return CEDOrchestrator(
        [SocraticAgent(f"empty-a{index}", provider) for index in range(4)],
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
        json.dumps({"content": {
            "question": "",
            "operator": MaieuticOperator.CLARIFY.value,
            "epistemic_marker": "open_uncertainty",
        }, "confidence": 0.7}),
        task,
    )
    assert status.value == "ok" and error is None and move is not None

    ced = _empty_question_council()
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
