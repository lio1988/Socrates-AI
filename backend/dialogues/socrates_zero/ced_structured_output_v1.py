"""Benchmark-local provider schemas for the frozen CED move contracts.

This module is an interface adapter, not another CED authority.  It renders the
existing task/role contracts as strict provider-facing JSON Schema.  Returned
JSON must still pass ``provider_registry.parse_and_validate_move`` and every
task-specific CED gate; provider schema validity never implies CED acceptance.

The module is pure and offline.  It reads no credential, opens no socket, makes
no provider call, and mutates no dialogue state.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Annotated, Any, Dict, FrozenSet, List, Literal, Tuple, Type

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, create_model

from ..models import (
    AgentRole,
    AgentTask,
    DialogPhase,
    EpistemicMarker,
    SCORE_WEIGHTS,
    SECTION_ORDER,
    ScoreBreakdown,
    SectionName,
    TaskKind,
)
from .. import semantic_floor as floor
from ..reasoning_prompts import marker_is_contracted
from ..socratic import GroundingRefType, InquiryState, MaieuticOperator
from .contracts import ContractValidationError, canonical_json


STRUCTURED_OUTPUT_SCHEMA_VERSION_V1 = "ced-benchmark-structured-output/v1"

SUPPORTED_CED_TASK_KINDS_V1: FrozenSet[TaskKind] = frozenset(
    {
        TaskKind.SOCRATIC_QUESTION,
        TaskKind.INITIAL_RESPONSE,
        TaskKind.ELENCHUS_OBJECTION,
        TaskKind.REFLECTION_REVISION,
        TaskKind.RECONSTRUCTION_PROPOSAL,
        TaskKind.SYNTHESIS_DRAFT,
        TaskKind.MOVE_SCORE,
        TaskKind.SECTION_SCORE,
        TaskKind.COUNCIL_RATIFICATION,
        TaskKind.OBJECTION_VERIFICATION,
    }
)


NonEmptyText = Annotated[str, Field(min_length=1, pattern=r"\S")]
UnitConfidence = Annotated[float, Field(ge=0.0, le=1.0)]
ScoreValue = Annotated[float, Field(ge=0.0, le=10.0)]


# -- Semantic contribution floor ----------------------------------------------
#
# The floor itself lives in ``backend.dialogues.semantic_floor`` because the CED
# acceptance authority in ``provider_registry`` is what must enforce it, and
# core code cannot depend on this benchmark-local module.  What happens here is
# only wire rendering: the same thresholds are declared as ``minLength`` so the
# provider-facing JSON Schema states the floor, and the same predicates run as
# validators so a schema-satisfying-but-empty value is rejected on parse too.
#
# These wrappers exist to raise ``ContractValidationError`` — the exception this
# module's callers already handle — rather than the core ``SemanticFloorError``.

SUBSTANTIVE_MIN_CHARS_V1 = floor.SUBSTANTIVE_MIN_CHARS
SUBSTANTIVE_MIN_WORDS_V1 = floor.SUBSTANTIVE_MIN_WORDS
SUBSTANTIVE_MIN_DISTINCT_WORDS_V1 = floor.SUBSTANTIVE_MIN_DISTINCT_WORDS
SUBSTANTIVE_MIN_CONTENT_WORDS_V1 = floor.SUBSTANTIVE_MIN_CONTENT_WORDS
SUBSTANTIVE_MIN_DISTINCT_LETTERS_V1 = floor.SUBSTANTIVE_MIN_DISTINCT_LETTERS
QUOTED_SPAN_MIN_CHARS_V1 = floor.QUOTED_SPAN_MIN_CHARS
QUOTED_SPAN_MIN_WORDS_V1 = floor.QUOTED_SPAN_MIN_WORDS
QUOTED_SPAN_MIN_DISTINCT_LETTERS_V1 = floor.QUOTED_SPAN_MIN_DISTINCT_LETTERS


def assert_substantive_text_v1(value: str) -> str:
    """Reject text that satisfies the schema without carrying a proposition."""
    try:
        return floor.assert_substantive(value)
    except floor.SemanticFloorError as exc:
        raise ContractValidationError(str(exc)) from exc


def assert_interrogative_text_v1(value: str) -> str:
    """A Socratic question must be substantive *and* actually ask something."""
    try:
        return floor.assert_interrogative(value)
    except floor.SemanticFloorError as exc:
        raise ContractValidationError(str(exc)) from exc


def assert_quoted_span_v1(value: str) -> str:
    """Reject a degenerate citation without demanding a full proposition."""
    try:
        return floor.assert_quoted_span(value)
    except floor.SemanticFloorError as exc:
        raise ContractValidationError(str(exc)) from exc


SubstantiveText = Annotated[
    str,
    Field(min_length=SUBSTANTIVE_MIN_CHARS_V1, pattern=r"\S"),
    AfterValidator(assert_substantive_text_v1),
]

QuotedSpanText = Annotated[
    str,
    Field(min_length=QUOTED_SPAN_MIN_CHARS_V1, pattern=r"\S"),
    AfterValidator(assert_quoted_span_v1),
]

InterrogativeText = Annotated[
    str,
    Field(min_length=SUBSTANTIVE_MIN_CHARS_V1, pattern=r"\S"),
    AfterValidator(assert_interrogative_text_v1),
]


class _StrictWireModel(BaseModel):
    """Every provider-owned object is closed; CED-owned fields stay outside."""

    model_config = ConfigDict(extra="forbid", strict=True)


# -- Socratic opening/follow-up ------------------------------------------------


class _SocraticOpeningContentV1(_StrictWireModel):
    question: InterrogativeText
    operator: MaieuticOperator
    epistemic_marker: EpistemicMarker


class _GroundingReferenceV1(_StrictWireModel):
    ref_type: GroundingRefType
    ref_id: NonEmptyText


class _AporiaV1(_StrictWireModel):
    previous_commitment_id: NonEmptyText
    conflicting_commitment_id: NonEmptyText
    resulting_status: Literal["withdrawn", "suspended"]
    remaining_question: InterrogativeText


class _SocraticFollowupContentV1(_StrictWireModel):
    question: InterrogativeText
    operator: MaieuticOperator
    grounded_in: List[_GroundingReferenceV1] = Field(min_length=1)
    # This is a hard CED veto, not merely a prompting preference.
    introduces_new_proposition: Literal[False]
    inquiry_state: InquiryState
    # OpenAI-style strict schemas require every property to be required.  Null
    # preserves CED's prompt contract ("optional, or null") without inventing a
    # second sentinel value.
    aporia: _AporiaV1 | None
    epistemic_marker: EpistemicMarker


# -- Initial response ----------------------------------------------------------
#
# These role payload names are the repository-native FakeProvider vocabulary
# already consumed by the canonical registry path.  The only additions are the
# explicit COMMITMENT_EMISSION_DIRECTIVE field and the canonical marker.


class _FactualClaimV1(_StrictWireModel):
    claim: SubstantiveText
    status: NonEmptyText
    notes: SubstantiveText


class _InitialCriticContentV1(_StrictWireModel):
    contradictions: List[SubstantiveText]
    weak_assumptions: List[SubstantiveText]
    logic_gaps: List[SubstantiveText]
    critique_summary: SubstantiveText
    commitments: List[SubstantiveText] = Field(min_length=1)
    epistemic_marker: EpistemicMarker


class _InitialEmpiricistContentV1(_StrictWireModel):
    factual_claims: List[_FactualClaimV1]
    evidence_quality: UnitConfidence
    documentation_gaps: List[SubstantiveText]
    commitments: List[SubstantiveText] = Field(min_length=1)
    epistemic_marker: EpistemicMarker


class _InitialSynthesizerContentV1(_StrictWireModel):
    synthesis_draft: SubstantiveText
    key_insights: List[SubstantiveText]
    unresolved_tensions: List[SubstantiveText]
    commitments: List[SubstantiveText] = Field(min_length=1)
    epistemic_marker: EpistemicMarker


# -- Elenchus ------------------------------------------------------------------
#
# The role payload remains repository-native.  ``target_section`` is the exact
# ELENCHUS_TARGET_DIRECTIVE addition used by the governing Hybrid projection.


TargetSectionV1 = Literal[
    "core_answer",
    "crucial_stress_test",
    "blind_spots",
    "nuance",
    "final_verdict",
    "none",
]


class _ElenchusCriticContentV1(_StrictWireModel):
    contradictions: List[SubstantiveText]
    weak_assumptions: List[SubstantiveText]
    logic_gaps: List[SubstantiveText]
    critique_summary: SubstantiveText
    target_section: TargetSectionV1
    epistemic_marker: EpistemicMarker


class _ElenchusEmpiricistContentV1(_StrictWireModel):
    factual_claims: List[_FactualClaimV1]
    evidence_quality: UnitConfidence
    documentation_gaps: List[SubstantiveText]
    target_section: TargetSectionV1
    epistemic_marker: EpistemicMarker


# -- Reflection and reconstruction --------------------------------------------


class _CommitmentRevisionV1(_StrictWireModel):
    commitment_id: NonEmptyText
    new_claim: SubstantiveText


class _CommitmentSuspensionV1(_StrictWireModel):
    commitment_id: NonEmptyText
    pending_on: SubstantiveText


class _ReflectionContentV1(_StrictWireModel):
    # REFLECTION_COMMITMENT_DIRECTIVE fields.
    answer_to_socratic_question: SubstantiveText
    # Retained and withdrawn lists carry commitment *ids* ("c1"), which name a
    # proposition rather than assert one.  Only authored text takes the floor.
    commitments_retained: List[NonEmptyText]
    commitments_revised: List[_CommitmentRevisionV1]
    commitments_withdrawn: List[NonEmptyText]
    commitments_suspended: List[_CommitmentSuspensionV1]
    new_commitments: List[SubstantiveText]
    remaining_uncertainty: SubstantiveText
    # BAYESIAN_UPDATE_DIRECTIVE fields and its named revised-position example.
    revised_position: SubstantiveText
    prior_confidence: UnitConfidence
    evidence_force: Literal["decisive", "strong", "weak", "none"]
    posterior_confidence: UnitConfidence
    what_changed: SubstantiveText
    epistemic_marker: EpistemicMarker


class _ReconstructionContentV1(_StrictWireModel):
    stronger_position: SubstantiveText
    integrated_critiques: List[SubstantiveText]
    remaining_weaknesses: List[SubstantiveText]
    epistemic_marker: EpistemicMarker


# -- Synthesis and peer scoring ------------------------------------------------


_synthesis_fields: Dict[str, Tuple[Any, Any]] = {
    section.value: (SubstantiveText, ...)
    for section in SECTION_ORDER
}
_synthesis_fields["epistemic_marker"] = (EpistemicMarker, ...)
_SynthesisContentV1 = create_model(
    "CedBenchmarkSynthesisContentV1",
    __base__=_StrictWireModel,
    **_synthesis_fields,
)


_score_fields: Dict[str, Tuple[Any, Any]] = {
    field_name: (ScoreValue, ...)
    for field_name in ScoreBreakdown.model_fields
}
_ScoreContentV1 = create_model(
    "CedBenchmarkScoreContentV1",
    __base__=_StrictWireModel,
    **_score_fields,
)


# -- Council ratification ------------------------------------------------------
#
# Three closed variants encode the existing conditional prompt contract without
# weakening it into a bag of nullable fields.


class _RatificationAcceptContentV1(_StrictWireModel):
    verdict: Literal["accept"]
    rationale: SubstantiveText


class _RatificationCaveatContentV1(_StrictWireModel):
    verdict: Literal["accept_with_caveat"]
    rationale: SubstantiveText
    caveat: SubstantiveText


class _RatificationBlockContentV1(_StrictWireModel):
    verdict: Literal["blocking_objection"]
    rationale: SubstantiveText
    severity: Literal["critical"]
    target_section: SectionName
    required_fix: SubstantiveText


# -- Objection verification ----------------------------------------------------
#
# The prompt has two real shapes: a task-internal check with quoted task spans,
# and a not-about-the-task classification for which citation is inapplicable.


class _TaskObjectionVerificationContentV1(_StrictWireModel):
    objection_concerns_the_task: Literal[True]
    cited_spans: List[QuotedSpanText] = Field(min_length=1)
    condition_tested: SubstantiveText
    objection_holds: bool | None
    objection_targets: Literal["conclusion", "justification"]
    rationale: SubstantiveText


class _NonTaskObjectionVerificationContentV1(_StrictWireModel):
    objection_concerns_the_task: Literal[False]
    cited_spans: List[NonEmptyText] = Field(max_length=0)
    condition_tested: SubstantiveText
    objection_holds: Literal[None]
    rationale: SubstantiveText


@dataclass(frozen=True)
class _ContractV1:
    key: str
    schema_name: str
    content_models: Tuple[Type[BaseModel], ...]
    wire_model: Type[BaseModel]


def _union_annotation(models: Tuple[Type[BaseModel], ...]) -> Any:
    annotation: Any = models[0]
    for model in models[1:]:
        annotation = annotation | model
    return annotation


def _contract(
    key: str,
    schema_name: str,
    *content_models: Type[BaseModel],
) -> _ContractV1:
    if not content_models:
        raise ValueError("a structured-output contract needs content")
    wire_model = create_model(
        "".join(part.title() for part in key.split("_")) + "MoveV1",
        __base__=_StrictWireModel,
        content=(_union_annotation(tuple(content_models)), ...),
        confidence=(UnitConfidence, ...),
    )
    return _ContractV1(
        key=key,
        schema_name=schema_name,
        content_models=tuple(content_models),
        wire_model=wire_model,
    )


_SOCRATIC_OPENING = _contract(
    "socratic_opening",
    "ced_socratic_opening_move_v1",
    _SocraticOpeningContentV1,
)
_SOCRATIC_FOLLOWUP = _contract(
    "socratic_followup",
    "ced_socratic_followup_move_v1",
    _SocraticFollowupContentV1,
)

_INITIAL_BY_ROLE = {
    AgentRole.ELENCHUS_CRITIC: _contract(
        "initial_elenchus_critic",
        "ced_initial_critic_move_v1",
        _InitialCriticContentV1,
    ),
    AgentRole.EMPIRICIST: _contract(
        "initial_empiricist",
        "ced_initial_empiricist_move_v1",
        _InitialEmpiricistContentV1,
    ),
    AgentRole.SYNTHESIZER: _contract(
        "initial_synthesizer",
        "ced_initial_synthesizer_move_v1",
        _InitialSynthesizerContentV1,
    ),
}

_ELENCHUS_BY_ROLE = {
    AgentRole.ELENCHUS_CRITIC: _contract(
        "elenchus_critic",
        "ced_elenchus_critic_move_v1",
        _ElenchusCriticContentV1,
    ),
    AgentRole.EMPIRICIST: _contract(
        "elenchus_empiricist",
        "ced_elenchus_empiricist_move_v1",
        _ElenchusEmpiricistContentV1,
    ),
}

_REFLECTION = _contract(
    "reflection",
    "ced_reflection_move_v1",
    _ReflectionContentV1,
)
_RECONSTRUCTION = _contract(
    "reconstruction",
    "ced_reconstruction_move_v1",
    _ReconstructionContentV1,
)
_SYNTHESIS = _contract(
    "synthesis",
    "ced_synthesis_move_v1",
    _SynthesisContentV1,
)
_MOVE_SCORE = _contract(
    "move_score",
    "ced_move_score_v1",
    _ScoreContentV1,
)
_SECTION_SCORE = _contract(
    "section_score",
    "ced_section_score_v1",
    _ScoreContentV1,
)
_COUNCIL_RATIFICATION = _contract(
    "council_ratification",
    "ced_council_ratification_v1",
    _RatificationAcceptContentV1,
    _RatificationCaveatContentV1,
    _RatificationBlockContentV1,
)
_OBJECTION_VERIFICATION = _contract(
    "objection_verification",
    "ced_objection_verification_v1",
    _TaskObjectionVerificationContentV1,
    _NonTaskObjectionVerificationContentV1,
)


def _require_task_shape(
    task: AgentTask,
    *,
    phase: DialogPhase,
    role: AgentRole | None = None,
) -> None:
    if task.phase is not phase:
        raise ContractValidationError(
            f"{task.task_kind.value if task.task_kind else 'unknown'} requires "
            f"phase={phase.value}, got {task.phase.value}"
        )
    if role is not None and task.role is not role:
        raise ContractValidationError(
            f"{task.task_kind.value if task.task_kind else 'unknown'} requires "
            f"role={role.value}, got {task.role.value}"
        )


def _contract_for_task_v1(task: AgentTask) -> _ContractV1:
    kind = task.task_kind
    if kind is None:
        raise ContractValidationError("task_kind is required for structured output")
    if kind not in SUPPORTED_CED_TASK_KINDS_V1:
        raise ContractValidationError(
            f"unsupported CED structured-output task kind: {kind.value}"
        )

    if kind is TaskKind.SOCRATIC_QUESTION:
        if task.phase is DialogPhase.OPENING:
            _require_task_shape(task, phase=DialogPhase.OPENING, role=AgentRole.SOCRATES)
            return _SOCRATIC_OPENING
        _require_task_shape(task, phase=DialogPhase.ELENCHUS, role=AgentRole.SOCRATES)
        return _SOCRATIC_FOLLOWUP

    if kind is TaskKind.INITIAL_RESPONSE:
        _require_task_shape(task, phase=DialogPhase.INITIAL_RESPONSE)
        contract = _INITIAL_BY_ROLE.get(task.role)
        if contract is None:
            raise ContractValidationError(
                f"initial_response has no frozen contract for role={task.role.value}"
            )
        return contract

    if kind is TaskKind.ELENCHUS_OBJECTION:
        _require_task_shape(task, phase=DialogPhase.ELENCHUS)
        contract = _ELENCHUS_BY_ROLE.get(task.role)
        if contract is None:
            raise ContractValidationError(
                f"elenchus_objection has no frozen contract for role={task.role.value}"
            )
        return contract

    if kind is TaskKind.REFLECTION_REVISION:
        _require_task_shape(task, phase=DialogPhase.REFLECTION, role=AgentRole.REFLECTOR)
        return _REFLECTION
    if kind is TaskKind.RECONSTRUCTION_PROPOSAL:
        _require_task_shape(
            task,
            phase=DialogPhase.RECONSTRUCTION,
            role=AgentRole.MAIEUTIC_RECONSTRUCTOR,
        )
        return _RECONSTRUCTION
    if kind is TaskKind.SYNTHESIS_DRAFT:
        _require_task_shape(task, phase=DialogPhase.SYNTHESIS, role=AgentRole.SYNTHESIZER)
        return _SYNTHESIS
    if kind is TaskKind.MOVE_SCORE:
        if task.phase not in {
            DialogPhase.OPENING,
            DialogPhase.INITIAL_RESPONSE,
            DialogPhase.ELENCHUS,
            DialogPhase.REFLECTION,
            DialogPhase.RECONSTRUCTION,
            DialogPhase.SYNTHESIS,
        }:
            raise ContractValidationError(
                f"move_score cannot score phase={task.phase.value}"
            )
        if task.role is not AgentRole.FINAL_EVALUATOR:
            raise ContractValidationError("move_score requires role=final_evaluator")
        return _MOVE_SCORE
    if kind is TaskKind.SECTION_SCORE:
        _require_task_shape(task, phase=DialogPhase.SYNTHESIS, role=AgentRole.FINAL_EVALUATOR)
        return _SECTION_SCORE
    if kind is TaskKind.COUNCIL_RATIFICATION:
        _require_task_shape(task, phase=DialogPhase.RATIFICATION, role=AgentRole.FINAL_EVALUATOR)
        return _COUNCIL_RATIFICATION
    if kind is TaskKind.OBJECTION_VERIFICATION:
        _require_task_shape(task, phase=DialogPhase.ELENCHUS, role=AgentRole.FINAL_EVALUATOR)
        return _OBJECTION_VERIFICATION

    # The supported-set guard above and the exhaustive cases make this dead code.
    raise ContractValidationError(f"no structured-output contract for {kind.value}")


def ced_structured_wire_model_v1(task: AgentTask) -> Type[BaseModel]:
    """Return the strict provider wire model selected by the CED-owned task."""

    return _contract_for_task_v1(task).wire_model


def ced_structured_schema_name_v1(task: AgentTask) -> str:
    """Stable provider schema name for session-authorization binding."""

    return _contract_for_task_v1(task).schema_name


def ced_structured_response_format_v1(task: AgentTask) -> Dict[str, Any]:
    """Render OpenRouter's strict ``response_format`` wrapper for one CED task."""

    contract = _contract_for_task_v1(task)
    schema = contract.wire_model.model_json_schema()

    # OpenRouter's strict-structured provider surface consistently accepts enum
    # while single-value ``const`` support varies by upstream.  Pydantic emits
    # ``const`` for Literal[T]; render the equivalent one-value enum without
    # changing the wire model or the accepted value set.
    def normalize_literals(node: Any) -> None:
        if isinstance(node, dict):
            if "const" in node:
                node["enum"] = [node.pop("const")]
            for value in node.values():
                normalize_literals(value)
        elif isinstance(node, list):
            for value in node:
                normalize_literals(value)

    normalize_literals(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": contract.schema_name,
            "strict": True,
            "schema": schema,
        },
    }


def ced_structured_schema_sha256_v1(task: AgentTask) -> str:
    """Digest the exact rendered wrapper, including its stable schema name."""

    return hashlib.sha256(
        canonical_json(ced_structured_response_format_v1(task)).encode("utf-8")
    ).hexdigest()


def validate_ced_structured_output_v1(task: AgentTask, raw_text: str) -> BaseModel:
    """Validate provider-schema compliance only; this does not accept a CED move."""

    return ced_structured_wire_model_v1(task).model_validate_json(
        raw_text,
        strict=True,
    )


def _representative_tasks_v1() -> Tuple[AgentTask, ...]:
    def task(kind: TaskKind, phase: DialogPhase, role: AgentRole) -> AgentTask:
        return AgentTask(
            task_id=f"offline_{kind.value}_{role.value}",
            session_id="offline_schema_parity",
            agent_id=f"offline_{role.value}",
            role=role,
            phase=phase,
            question="Offline schema parity question",
            task_kind=kind,
        )

    return (
        task(TaskKind.SOCRATIC_QUESTION, DialogPhase.OPENING, AgentRole.SOCRATES),
        task(TaskKind.SOCRATIC_QUESTION, DialogPhase.ELENCHUS, AgentRole.SOCRATES),
        task(TaskKind.INITIAL_RESPONSE, DialogPhase.INITIAL_RESPONSE,
             AgentRole.ELENCHUS_CRITIC),
        task(TaskKind.INITIAL_RESPONSE, DialogPhase.INITIAL_RESPONSE,
             AgentRole.EMPIRICIST),
        task(TaskKind.INITIAL_RESPONSE, DialogPhase.INITIAL_RESPONSE,
             AgentRole.SYNTHESIZER),
        task(TaskKind.ELENCHUS_OBJECTION, DialogPhase.ELENCHUS,
             AgentRole.ELENCHUS_CRITIC),
        task(TaskKind.ELENCHUS_OBJECTION, DialogPhase.ELENCHUS,
             AgentRole.EMPIRICIST),
        task(TaskKind.REFLECTION_REVISION, DialogPhase.REFLECTION,
             AgentRole.REFLECTOR),
        task(TaskKind.RECONSTRUCTION_PROPOSAL, DialogPhase.RECONSTRUCTION,
             AgentRole.MAIEUTIC_RECONSTRUCTOR),
        task(TaskKind.SYNTHESIS_DRAFT, DialogPhase.SYNTHESIS,
             AgentRole.SYNTHESIZER),
        task(TaskKind.MOVE_SCORE, DialogPhase.OPENING,
             AgentRole.FINAL_EVALUATOR),
        task(TaskKind.SECTION_SCORE, DialogPhase.SYNTHESIS,
             AgentRole.FINAL_EVALUATOR),
        task(TaskKind.COUNCIL_RATIFICATION, DialogPhase.RATIFICATION,
             AgentRole.FINAL_EVALUATOR),
        task(TaskKind.OBJECTION_VERIFICATION, DialogPhase.ELENCHUS,
             AgentRole.FINAL_EVALUATOR),
    )


def _assert_every_object_is_closed(node: Any) -> None:
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            if node.get("additionalProperties") is not False:
                raise ContractValidationError(
                    "provider schema contains an open object"
                )
            if set(node.get("required") or ()) != set(properties):
                raise ContractValidationError(
                    "provider schema object does not require every property"
                )
        for value in node.values():
            _assert_every_object_is_closed(value)
    elif isinstance(node, list):
        for value in node:
            _assert_every_object_is_closed(value)


def assert_ced_structured_schema_parity_v1() -> None:
    """Fail closed if the provider factory drifts from frozen CED structures."""

    expected_kinds = {
        TaskKind.SOCRATIC_QUESTION,
        TaskKind.INITIAL_RESPONSE,
        TaskKind.ELENCHUS_OBJECTION,
        TaskKind.REFLECTION_REVISION,
        TaskKind.RECONSTRUCTION_PROPOSAL,
        TaskKind.SYNTHESIS_DRAFT,
        TaskKind.MOVE_SCORE,
        TaskKind.SECTION_SCORE,
        TaskKind.COUNCIL_RATIFICATION,
        TaskKind.OBJECTION_VERIFICATION,
    }
    if set(SUPPORTED_CED_TASK_KINDS_V1) != expected_kinds:
        raise ContractValidationError("structured-output task coverage drifted")

    represented = set()
    schema_names = set()
    for task in _representative_tasks_v1():
        represented.add(task.task_kind)
        wrapper = ced_structured_response_format_v1(task)
        if set(wrapper) != {"type", "json_schema"}:
            raise ContractValidationError("response_format wrapper fields drifted")
        if wrapper["type"] != "json_schema":
            raise ContractValidationError("response_format is not JSON Schema")
        config = wrapper["json_schema"]
        if set(config) != {"name", "strict", "schema"}:
            raise ContractValidationError("json_schema wrapper fields drifted")
        if config["strict"] is not True:
            raise ContractValidationError("provider schema is not strict")
        schema_names.add(config["name"])
        schema = config["schema"]
        if set(schema.get("properties") or {}) != {"content", "confidence"}:
            raise ContractValidationError("CED wire envelope fields drifted")
        if "epistemic_marker" in (schema.get("properties") or {}):
            raise ContractValidationError("epistemic_marker escaped content")
        if '"const"' in canonical_json(schema):
            raise ContractValidationError("provider schema contains unnormalized const")
        _assert_every_object_is_closed(schema)

        contract = _contract_for_task_v1(task)
        requires_marker = marker_is_contracted(task.task_kind)
        for content_model in contract.content_models:
            has_marker = "epistemic_marker" in content_model.model_fields
            if has_marker is not requires_marker:
                raise ContractValidationError(
                    f"marker contract drifted for {contract.key}"
                )

    if represented != expected_kinds:
        raise ContractValidationError("not every supported task kind is represented")

    opening_fields = set(_SocraticOpeningContentV1.model_fields)
    if opening_fields != {"question", "operator", "epistemic_marker"}:
        raise ContractValidationError("Socratic opening fields drifted")
    followup_fields = set(_SocraticFollowupContentV1.model_fields)
    if followup_fields != {
        "question",
        "operator",
        "grounded_in",
        "introduces_new_proposition",
        "inquiry_state",
        "aporia",
        "epistemic_marker",
    }:
        raise ContractValidationError("Socratic follow-up fields drifted")

    section_fields = {section.value for section in SECTION_ORDER}
    if set(_SynthesisContentV1.model_fields) != section_fields | {
        "epistemic_marker"
    }:
        raise ContractValidationError("synthesis fields differ from SECTION_ORDER")
    if set(_ScoreContentV1.model_fields) != set(ScoreBreakdown.model_fields):
        raise ContractValidationError("score fields differ from ScoreBreakdown")
    if set(_ScoreContentV1.model_fields) != set(SCORE_WEIGHTS):
        raise ContractValidationError("score fields differ from SCORE_WEIGHTS")

    if len(schema_names) != len({_contract_for_task_v1(t).key
                                 for t in _representative_tasks_v1()}):
        raise ContractValidationError("distinct CED contracts share a schema name")


__all__ = [
    "STRUCTURED_OUTPUT_SCHEMA_VERSION_V1",
    "SUPPORTED_CED_TASK_KINDS_V1",
    "assert_ced_structured_schema_parity_v1",
    "ced_structured_response_format_v1",
    "ced_structured_schema_name_v1",
    "ced_structured_schema_sha256_v1",
    "ced_structured_wire_model_v1",
    "validate_ced_structured_output_v1",
]
