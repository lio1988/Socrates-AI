"""Maieutic machinery: the question owns nothing, and the history is immutable.

Socrates is the midwife. The other agents are the epistemic parents of candidate
knowledge, and nothing here may quietly take that from them. Two invariants sit
above everything else in this module:

    SOCRATES OWNS THE QUESTION, NOT THE ANSWER.
    THE DIALOGUE HISTORY IS IMMUTABLE. NEW UNDERSTANDING EXTENDS IT.

The design drifted once already. A previous version required the opening question
to name a complete rival ordering — a "near miss" for the council to test — and
four live runs duly opened by handing the council a six-name permutation before
any agent had spoken. That is answer injection wearing a question mark, and this
module exists partly to make it mechanically impossible to do again.

Nothing here carries epistemic authority. A commitment is a record of what an
agent said, not of what is true. An aporia is a record of where an inquiry
stalled, not a verdict. An inquiry state is a process recommendation, and CED
alone decides whether the dialogue continues.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .hybrid_epistemic import stable_id
from .model_identity import independent_model_sources
from .task_checker import all_candidate_orders, model_task

# ── the twelve operations ────────────────────────────────────────────────────


class MaieuticOperator(str, Enum):
    """What a question does. Not what it asserts — a question asserts nothing."""

    CLARIFY = "clarify"
    ELICIT_COMMITMENT = "elicit_commitment"
    EXPOSE_PREMISE = "expose_premise"
    DRAW_CONSEQUENCE = "draw_consequence"
    CONNECT_COMMITMENTS = "connect_commitments"
    TEST_COHERENCE = "test_coherence"
    DISTINGUISH = "distinguish"
    REQUEST_GROUNDS = "request_grounds"
    RESOLVE_DISAGREEMENT = "resolve_disagreement"
    INDUCE_APORIA = "induce_aporia"
    MAIEUTIC_RECONSTRUCTION = "maieutic_reconstruction"
    IDENTIFY_REMAINDER = "identify_remainder"


class InquiryState(str, Enum):
    """A process recommendation to CED. Never a truth status.

    Aporia is deliberately absent: reaching aporia is a dialectical condition,
    and very often it is precisely where the next question belongs. Conflating
    it with "stop" would end the inquiry at the moment it became productive.
    """

    CONTINUE_INQUIRY = "continue_inquiry"
    READY_FOR_RECONSTRUCTION = "ready_for_reconstruction"


# ── commitments: append-only, source-grounded ────────────────────────────────


class CommitmentStatus(str, Enum):
    ASSERTED = "asserted"
    RETAINED = "retained"
    REVISED = "revised"
    WITHDRAWN = "withdrawn"
    SUSPENDED = "suspended"


class CommitmentRecord:
    """One public thing an agent committed to, at one moment.

    Never mutated. A revision does not edit its predecessor: it is a new record
    pointing back at one. The full intellectual history of the dialogue must be
    reconstructable from the ledger alone, including the positions that were
    abandoned — those are usually the interesting ones.
    """

    __slots__ = ("commitment_id", "source_move_id", "cycle", "claim", "status",
                 "target_commitment_id", "provider_id", "model_id", "authority")

    def __init__(self, *, commitment_id: str, source_move_id: str, cycle: int,
                 claim: str, status: CommitmentStatus,
                 target_commitment_id: Optional[str] = None,
                 provider_id: Optional[str] = None,
                 model_id: Optional[str] = None,
                 authority: str = "public_move") -> None:
        self.commitment_id = commitment_id
        self.source_move_id = source_move_id
        self.cycle = cycle
        self.claim = claim
        self.status = status
        #: The commitment this one revises, withdraws, suspends or retains.
        self.target_commitment_id = target_commitment_id
        self.provider_id = provider_id
        self.model_id = model_id
        #: "public_move" for a commitment an agent declared itself.
        #: "non_authoritative_annotation" for anything inferred from prose — it
        #: is readable, it is auditable, and it resolves nothing.
        self.authority = authority

    @property
    def is_authoritative(self) -> bool:
        """Did an agent actually declare this, or did something infer it?"""
        return self.authority == "public_move"

    def to_dict(self) -> Dict[str, Any]:
        return {"commitment_id": self.commitment_id,
                "source_move_id": self.source_move_id,
                "cycle": self.cycle,
                "claim": self.claim,
                "status": self.status.value,
                "target_commitment_id": self.target_commitment_id,
                "provider_id": self.provider_id,
                "model_id": self.model_id,
                "authority": self.authority}


def _commitment_id(source_move_id: str, index: int, claim: str) -> str:
    return stable_id("cmt", source_move_id, str(index), claim)[:20]


def commitments_from_move(
    move_id: str, cycle: int, content: Any, provider_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> List[CommitmentRecord]:
    """Read the commitments an initial response declared. Declared, not inferred.

    A list of plain strings, or of objects carrying a `claim`. Anything else is
    skipped rather than interpreted: guessing what a model meant is exactly the
    step that turns a transcript into an authority.
    """
    if not isinstance(content, Mapping):
        return []
    raw = content.get("commitments")
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[CommitmentRecord] = []
    for index, item in enumerate(raw):
        claim = item.get("claim") if isinstance(item, Mapping) else item
        if not isinstance(claim, str) or not claim.strip():
            continue
        claim = claim.strip()
        out.append(CommitmentRecord(
            commitment_id=_commitment_id(move_id, index, claim),
            source_move_id=move_id, cycle=cycle, claim=claim,
            status=CommitmentStatus.ASSERTED, provider_id=provider_id,
            model_id=model_id))
    return out


#: Reflection field -> the status the resulting event carries.
_REFLECTION_EVENTS: Tuple[Tuple[str, CommitmentStatus], ...] = (
    ("commitments_retained", CommitmentStatus.RETAINED),
    ("commitments_revised", CommitmentStatus.REVISED),
    ("commitments_withdrawn", CommitmentStatus.WITHDRAWN),
    ("commitments_suspended", CommitmentStatus.SUSPENDED),
)


def commitment_events_from_reflection(
    move_id: str, cycle: int, content: Any, known: Set[str],
    provider_id: Optional[str] = None, model_id: Optional[str] = None,
) -> List[CommitmentRecord]:
    """Turn a reflection's declared changes into new, append-only events.

    Nothing in `known` is edited. A revision emits a fresh record whose
    `target_commitment_id` points back, so the ledger reads as a history rather
    than a current-belief table.
    """
    if not isinstance(content, Mapping):
        return []
    events: List[CommitmentRecord] = []
    index = 0

    for field, status in _REFLECTION_EVENTS:
        for item in content.get(field) or []:
            if isinstance(item, Mapping):
                target = item.get("commitment_id")
                claim = item.get("new_claim") or item.get("claim") or ""
            else:
                target, claim = item, ""
            if not isinstance(target, str) or target not in known:
                continue          # a reference to nothing changes nothing
            events.append(CommitmentRecord(
                commitment_id=_commitment_id(move_id, index, f"{status.value}:{target}"),
                source_move_id=move_id, cycle=cycle,
                claim=str(claim).strip(), status=status,
                target_commitment_id=target, provider_id=provider_id,
                model_id=model_id))
            index += 1

    for item in content.get("new_commitments") or []:
        claim = item.get("claim") if isinstance(item, Mapping) else item
        if not isinstance(claim, str) or not claim.strip():
            continue
        events.append(CommitmentRecord(
            commitment_id=_commitment_id(move_id, index, claim.strip()),
            source_move_id=move_id, cycle=cycle, claim=claim.strip(),
            status=CommitmentStatus.ASSERTED, provider_id=provider_id,
            model_id=model_id))
        index += 1
    return events


def live_commitments(ledger: Sequence[CommitmentRecord]) -> List[CommitmentRecord]:
    """The positions still standing, derived from the history without editing it.

    A commitment is live until a later event withdraws or suspends it. The
    superseded records stay exactly where they are.
    """
    dead: Set[str] = set()
    for record in ledger:
        if record.status in (CommitmentStatus.WITHDRAWN, CommitmentStatus.SUSPENDED,
                             CommitmentStatus.REVISED) and record.target_commitment_id:
            dead.add(record.target_commitment_id)
    return [r for r in ledger
            if r.commitment_id not in dead
            and r.status is not CommitmentStatus.WITHDRAWN
            and r.status is not CommitmentStatus.SUSPENDED]


def independent_sources(records: Iterable[CommitmentRecord]) -> Set[str]:
    """Distinct known exact-model sources behind commitment records."""
    return independent_model_sources(records, attribute="model_id")


# ── grounding: typed references to public artifacts ──────────────────────────


class GroundingRefType(str, Enum):
    COMMITMENT = "commitment"
    CRITIQUE = "critique"
    APORIA = "aporia"
    SOCRATIC_QUESTION = "socratic_question"


def parse_grounding(raw: Any) -> List[Tuple[str, str]]:
    """Read declared `grounded_in` references as (ref_type, ref_id) pairs."""
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[Tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        ref_type = str(item.get("ref_type") or "").strip().lower()
        ref_id = str(item.get("ref_id") or "").strip()
        if ref_type in {t.value for t in GroundingRefType} and ref_id:
            out.append((ref_type, ref_id))
    return out


def resolve_grounding(
    refs: Sequence[Tuple[str, str]], public_ids: Mapping[str, Set[str]],
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Split declared references into (resolved, unresolved).

    `public_ids` maps ref_type to the ids that already existed publicly when the
    Socratic task was built. A reference to something that does not exist yet —
    or does not exist at all — resolves to nothing, and a question grounded in
    nothing is grounded in nothing. It is recorded, not silently accepted.
    """
    resolved, unresolved = [], []
    for ref_type, ref_id in refs:
        (resolved if ref_id in public_ids.get(ref_type, set())
         else unresolved).append((ref_type, ref_id))
    return resolved, unresolved


@dataclass(frozen=True)
class SocraticContentValidation:
    """Deterministic result of the phase-aware Socratic content contract.

    This validates whether a provider-OK ``AgentMove`` may become a public
    Socratic move. It does not validate truth, quality, or prompt compliance.
    """

    accepted: bool
    reason: str
    question: str = ""
    operator: Optional[MaieuticOperator] = None
    inquiry_state: Optional[InquiryState] = None
    grounded_in: Tuple[Tuple[str, str], ...] = ()
    unresolved_grounding: Tuple[Tuple[str, str], ...] = ()


def validate_socratic_content(
    content: Any,
    *,
    followup: bool,
    public_ids: Optional[Mapping[str, Set[str]]] = None,
) -> SocraticContentValidation:
    """Apply the hard content contract for an opening or follow-up question.

    Opening questions require a real string question and one known maieutic
    operator. Follow-ups additionally require a non-empty, entirely valid set
    of typed references to already-public artifacts, a boolean declaration that
    no new proposition was introduced (which must be false), and a known
    inquiry-state recommendation.

    Invalid fields are never coerced. In particular, ``123`` does not become a
    question and malformed grounding entries are not silently dropped.
    """
    if not isinstance(content, Mapping):
        return SocraticContentValidation(False, "content must be an object")

    raw_question = content.get("question")
    if not isinstance(raw_question, str):
        return SocraticContentValidation(False, "question must be a string")
    question = raw_question.strip()
    if not question:
        return SocraticContentValidation(False, "question must be non-empty")

    operator = read_operator(content)
    if operator is None:
        return SocraticContentValidation(
            False, "operator must name one canonical maieutic operator",
            question=question,
        )

    if not followup:
        return SocraticContentValidation(
            True, "accepted opening question", question=question,
            operator=operator,
        )

    raw_grounding = content.get("grounded_in")
    if not isinstance(raw_grounding, (list, tuple)) or not raw_grounding:
        return SocraticContentValidation(
            False, "follow-up grounded_in must be a non-empty list",
            question=question, operator=operator,
        )
    grounding = tuple(parse_grounding(raw_grounding))
    if len(grounding) != len(raw_grounding):
        return SocraticContentValidation(
            False, "follow-up grounded_in contains a malformed reference",
            question=question, operator=operator, grounded_in=grounding,
        )

    resolved, unresolved = resolve_grounding(grounding, public_ids or {})
    if unresolved:
        return SocraticContentValidation(
            False, "follow-up grounded_in contains an unresolved reference",
            question=question, operator=operator,
            grounded_in=tuple(resolved),
            unresolved_grounding=tuple(unresolved),
        )
    if not resolved:
        return SocraticContentValidation(
            False, "follow-up grounded_in resolves to no public material",
            question=question, operator=operator,
        )

    introduces = content.get("introduces_new_proposition")
    if not isinstance(introduces, bool):
        return SocraticContentValidation(
            False, "introduces_new_proposition must be a boolean",
            question=question, operator=operator, grounded_in=tuple(resolved),
        )
    if introduces:
        return SocraticContentValidation(
            False, "Socrates may not introduce a new proposition",
            question=question, operator=operator, grounded_in=tuple(resolved),
        )

    inquiry_state = read_inquiry_state(content)
    if inquiry_state is None:
        return SocraticContentValidation(
            False, "inquiry_state must name one canonical inquiry state",
            question=question, operator=operator, grounded_in=tuple(resolved),
        )
    return SocraticContentValidation(
        True, "accepted grounded follow-up question",
        question=question, operator=operator, inquiry_state=inquiry_state,
        grounded_in=tuple(resolved),
    )


# ── aporia: a public condition, never a verdict ──────────────────────────────


class AporiaRecord:
    """Where the inquiry stalled, and what remains askable.

    Carries no truth authority of any kind. It is not a failure, not evidence,
    not a falsification and not a support state. "My reason for X conflicts with
    Y, so I can no longer justify X" is epistemic progress, and the record's only
    job is to say where the next question belongs.
    """

    __slots__ = ("previous_commitment_id", "conflicting_commitment_id",
                 "resulting_status", "remaining_question", "cycle")

    def __init__(self, *, previous_commitment_id: str,
                 conflicting_commitment_id: str, resulting_status: CommitmentStatus,
                 remaining_question: str, cycle: int) -> None:
        self.previous_commitment_id = previous_commitment_id
        self.conflicting_commitment_id = conflicting_commitment_id
        self.resulting_status = resulting_status
        self.remaining_question = remaining_question
        self.cycle = cycle

    @property
    def aporia_id(self) -> str:
        return stable_id("apo", self.previous_commitment_id,
                         self.conflicting_commitment_id, str(self.cycle))[:20]

    def to_dict(self) -> Dict[str, Any]:
        return {"aporia_id": self.aporia_id,
                "previous_commitment_id": self.previous_commitment_id,
                "conflicting_commitment_id": self.conflicting_commitment_id,
                "resulting_status": self.resulting_status.value,
                "remaining_question": self.remaining_question,
                "cycle": self.cycle}


def aporia_from_content(content: Any, cycle: int, known: Set[str]) -> Optional[AporiaRecord]:
    """Read a declared aporia, or None. Both commitments must already exist."""
    if not isinstance(content, Mapping):
        return None
    raw = content.get("aporia")
    if not isinstance(raw, Mapping):
        return None
    previous = str(raw.get("previous_commitment_id") or "")
    conflicting = str(raw.get("conflicting_commitment_id") or "")
    if previous not in known or conflicting not in known:
        return None
    try:
        status = CommitmentStatus(str(raw.get("resulting_status") or "suspended"))
    except ValueError:
        status = CommitmentStatus.SUSPENDED
    if status not in (CommitmentStatus.WITHDRAWN, CommitmentStatus.SUSPENDED):
        status = CommitmentStatus.SUSPENDED
    return AporiaRecord(previous_commitment_id=previous,
                        conflicting_commitment_id=conflicting,
                        resulting_status=status,
                        remaining_question=str(raw.get("remaining_question") or ""),
                        cycle=cycle)


# ── the injection firewall ───────────────────────────────────────────────────


class InjectionCheck(str, Enum):
    PASS = "pass"
    ANSWER_INJECTION_DETECTED = "answer_injection_detected"
    #: No mechanical detector exists for this domain. We do not pretend one does,
    #: and we do not ask a model to certify that no leak occurred — that would be
    #: a model's opinion standing in for a guarantee.
    NOT_APPLICABLE = "not_applicable"


def check_answer_injection(
    question_text: str, task_text: str, prior_public_texts: Sequence[str],
) -> Tuple[InjectionCheck, str]:
    """Did this question hand the council an answer nobody had produced?

    Mechanical for finite ordering and honest about everything else. "Already
    public" includes the user's own task: if the operator supplied a candidate
    ordering, Socrates may of course refer to it.

    Merely naming every entity is not injection — an ordering is only recognised
    behind an explicit frame ("the order is", "could the sequence be"), so a
    question that mentions all six analysts in prose passes.
    """
    model, _reason = model_task(task_text)
    if model is None:
        return (InjectionCheck.NOT_APPLICABLE,
                "no mechanical ordering detector applies to this task")

    proposed = all_candidate_orders(question_text, model.entities)
    if not proposed:
        return InjectionCheck.PASS, "the question names no complete ordering"

    already_public: Set[Tuple[str, ...]] = set()
    for text in (task_text, *prior_public_texts):
        already_public |= all_candidate_orders(text, model.entities)

    injected = proposed - already_public
    if injected:
        named = "; ".join(", ".join(order) for order in sorted(injected))
        return (InjectionCheck.ANSWER_INJECTION_DETECTED,
                f"introduces an ordering no prior public artifact contains: {named}")
    return InjectionCheck.PASS, "every ordering named was already public"


# ── reading a Socratic move ──────────────────────────────────────────────────


def read_inquiry_state(content: Any) -> Optional[InquiryState]:
    """The advisory recommendation, or None when absent or unreadable."""
    if not isinstance(content, Mapping):
        return None
    try:
        return InquiryState(str(content.get("inquiry_state") or "").strip().lower())
    except ValueError:
        return None


def read_operator(content: Any) -> Optional[MaieuticOperator]:
    if not isinstance(content, Mapping):
        return None
    try:
        return MaieuticOperator(str(content.get("operator") or "").strip().lower())
    except ValueError:
        return None
