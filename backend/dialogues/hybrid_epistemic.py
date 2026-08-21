"""Socrates Epistemic Hybrid v1 — H3..H7 governing epistemic core.

One state machine, one ledger, one authority. H3 verification, H4 revision, H5
contradiction validation, H6 eligibility and H7 claim-level ratification are a
single coherent mechanism rather than five stacked layers, because the thing
they share — *what a record is allowed to do* — is exactly what must not be
duplicated.

## The law this exists to enforce

Quality is not epistemic support. The legacy canonical path promotes any session
whose mean peer score reaches 7.5 to ``WELL_SUPPORTED``; a live run measured
7.598 on an answer that opened by calling a discredited study "credible
evidence". Nothing in this module may recreate that under another name.

Permanently, none of these creates support:

* a quality score, a confidence value, agreement, corroboration count, or
  ratifier popularity;
* an ``epistemic_marker`` — the model's own label for its own claim;
* another model's opinion offered as external evidence.

## What does create support

Only an ``EvidenceRecord`` whose provenance is attributable to something other
than a model's assertion, or a ``VerificationRecord`` anchored in material the
task itself supplied. Support is categorical and always names its basis.

## Verification is claim-dependent

The blocking question is never "is there an evidence layer" but "where is the
verification anchored". A counterexample to a supplied constraint set is
checkable inside the session; a historical claim is not. ``VerificationClass``
routes each claim to the only method it may legally use, and
``EXTERNAL_EVIDENCE_REQUIRED`` is an honest terminal answer rather than a gap.

## Relationship to the existing epistemic subsystem

``backend/epistemic`` already models evidence with stance and provenance and
filters self-assertion. Its vocabulary is preserved here deliberately —
``EvidenceStance`` mirrors it exactly — and its *authority* is superseded: this
module never sums evidence to a numeric threshold. See
``docs/HYBRID_V1_H3_H7_GOVERNING_CORE.md``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from .hybrid_shadow import (
    SHADOW_AUTHORITY,
    HybridEpistemicLedger,
    HybridRecordKind,
    HybridShadowRecord,
    _digest,
)

HYBRID_EPISTEMIC_SCHEMA_VERSION = "socrates.hybrid-epistemic.h3h7/v1"


# ── verification ─────────────────────────────────────────────────────────────

class VerificationClass(str, Enum):
    """Where a claim's authoritative anchor lives. Decides the legal method."""

    #: Checkable against material the task itself supplied.
    TASK_INTERNAL = "task_internal"
    #: Checkable by deterministic execution (arithmetic, code, tests).
    TOOL_VERIFIABLE = "tool_verifiable"
    #: Needs facts from outside the task. Requires an evidence substrate.
    EXTERNAL_EVIDENCE = "external_evidence"
    #: Evaluative or normative; binary factual verification does not apply.
    NON_DEFINITIVE = "non_definitive"
    #: Nothing available. The safe default when classification is uncertain.
    NOT_CURRENTLY_VERIFIABLE = "not_currently_verifiable"


class VerificationMethod(str, Enum):
    TASK_INTERNAL_CHECK = "task_internal_check"
    TOOL_RECEIPT = "tool_receipt"
    EXTERNAL_SOURCE = "external_source"


class VerificationResult(str, Enum):
    VERIFIED = "verified"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"
    EXTERNAL_EVIDENCE_REQUIRED = "external_evidence_required"
    NOT_APPLICABLE = "not_applicable"


#: The only method each class may use. Anything else is a malformed record.
LEGAL_METHODS: Dict[VerificationClass, Tuple[VerificationMethod, ...]] = {
    VerificationClass.TASK_INTERNAL: (VerificationMethod.TASK_INTERNAL_CHECK,),
    VerificationClass.TOOL_VERIFIABLE: (VerificationMethod.TOOL_RECEIPT,),
    VerificationClass.EXTERNAL_EVIDENCE: (VerificationMethod.EXTERNAL_SOURCE,),
    VerificationClass.NON_DEFINITIVE: (),
    VerificationClass.NOT_CURRENTLY_VERIFIABLE: (),
}


class AnchorSpan(BaseModel):
    """A verbatim quotation from the original task, with its offset.

    The offset is what makes anchoring provable rather than asserted: validation
    re-extracts the span at that offset and compares. A record citing a
    constraint the task does not contain is malformed, not merely wrong.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    offset: int = Field(ge=0)


class VerificationRecord(BaseModel):
    """One bounded verification attempt. Never a vote."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verification_id: str
    claim_id: str
    objection_id: Optional[str] = None
    verification_class: VerificationClass
    method: Optional[VerificationMethod] = None
    #: Verbatim spans of the original task this check rests on.
    authoritative_inputs: List[AnchorSpan] = Field(default_factory=list)
    #: Evidence records relied on, for EXTERNAL_EVIDENCE only.
    evidence_ids: List[str] = Field(default_factory=list)
    condition_tested: str = ""
    result: VerificationResult
    rationale: str = ""
    scope: str = ""
    limitations: str = ""
    provenance: str = ""
    verifier_provider_id: Optional[str] = None


# ── evidence ─────────────────────────────────────────────────────────────────

class EvidenceStance(str, Enum):
    """Mirrors ``backend.epistemic.claim.EvidenceStance`` deliberately."""

    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    WEAK = "weak"


class EvidenceSourceType(str, Enum):
    """What kind of thing the evidence actually is.

    ``MODEL_ASSERTION`` exists so that a model's say-so can be *recorded* and
    then refused. It is never admissible support: that refusal is the whole
    point of naming it.
    """

    SUPPLIED_TASK_MATERIAL = "supplied_task_material"
    DETERMINISTIC_COMPUTATION = "deterministic_computation"
    TOOL_RECEIPT = "tool_receipt"
    EXTERNAL_SOURCE = "external_source"
    HUMAN_PROVIDED = "human_provided"
    MODEL_ASSERTION = "model_assertion"


#: Source types that may contribute support. A model asserting something is not
#: evidence for it, however fluently or however often.
ADMISSIBLE_EVIDENCE_SOURCES: Tuple[EvidenceSourceType, ...] = (
    EvidenceSourceType.SUPPLIED_TASK_MATERIAL,
    EvidenceSourceType.DETERMINISTIC_COMPUTATION,
    EvidenceSourceType.TOOL_RECEIPT,
    EvidenceSourceType.EXTERNAL_SOURCE,
    EvidenceSourceType.HUMAN_PROVIDED,
)


class EvidenceRecord(BaseModel):
    """Attributable material bearing on a claim."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    claim_id: str
    stance: EvidenceStance
    source_type: EvidenceSourceType
    #: Who or what this is attributable to. Never a model id for admissible
    #: evidence — that is what MODEL_ASSERTION is for.
    source_identity: str
    content: str = ""
    citation: Optional[str] = None
    known_at: Optional[str] = None
    receipt_ref: Optional[str] = None
    provenance: str = ""

    @property
    def admissible(self) -> bool:
        return self.source_type in ADMISSIBLE_EVIDENCE_SOURCES


# ── objections ───────────────────────────────────────────────────────────────

class ObjectionState(str, Enum):
    """A criticism earns destructive force; it does not arrive with it."""

    RAISED = "raised"
    PENDING_VERIFICATION = "pending_verification"
    VALIDATED = "validated"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


#: Only a validated objection may falsify. This single line is the fix for the
#: frozen failure where a false counterexample destroyed a correct answer.
DESTRUCTIVE_OBJECTION_STATES: Tuple[ObjectionState, ...] = (ObjectionState.VALIDATED,)

_OBJECTION_TRANSITIONS: Dict[ObjectionState, Tuple[ObjectionState, ...]] = {
    ObjectionState.RAISED: (ObjectionState.PENDING_VERIFICATION,
                            ObjectionState.INCONCLUSIVE),
    ObjectionState.PENDING_VERIFICATION: (ObjectionState.VALIDATED,
                                          ObjectionState.REJECTED,
                                          ObjectionState.INCONCLUSIVE),
    # Terminal. History is preserved, never rewritten.
    ObjectionState.VALIDATED: (),
    ObjectionState.REJECTED: (),
    ObjectionState.INCONCLUSIVE: (ObjectionState.PENDING_VERIFICATION,),
}


class ObjectionTransitionError(ValueError):
    """An illegal lifecycle move. Refused rather than silently normalised."""


class ObjectionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    objection_id: str
    target_claim_id: str
    text: str
    raised_by: Optional[str] = None
    state: ObjectionState = ObjectionState.RAISED
    verification_id: Optional[str] = None

    @property
    def is_destructive(self) -> bool:
        return self.state in DESTRUCTIVE_OBJECTION_STATES


# ── revision ─────────────────────────────────────────────────────────────────

class EvidenceApplicability(str, Enum):
    """How a superseded claim's evidence relates to its revision.

    Nothing is carried across automatically. The frozen failure included
    ``revised_claim_retains_semantically_stale_evidence``.
    """

    STILL_APPLICABLE = "still_applicable"
    REVALIDATED = "revalidated"
    STALE = "stale"
    CONTRADICTORY = "contradictory"
    UNRESOLVED = "unresolved"


#: Applicability values that let evidence keep bearing on the revised claim.
CARRIED_APPLICABILITY: Tuple[EvidenceApplicability, ...] = (
    EvidenceApplicability.STILL_APPLICABLE,
    EvidenceApplicability.REVALIDATED,
)


class EvidenceCarry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    applicability: EvidenceApplicability
    rationale: str = ""


class RevisionRecord(BaseModel):
    """A new claim version. Lineage preserved; support is not inherited."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_id: str
    from_claim_id: str
    to_claim_id: str
    reason: str = ""
    #: Every evidence item on the old claim must be classified explicitly.
    evidence_disposition: List[EvidenceCarry] = Field(default_factory=list)


# ── contradiction ────────────────────────────────────────────────────────────

class ContradictionState(str, Enum):
    """A detector proposes; only validation makes it authoritative.

    The frozen failure included ``contradiction_edges_are_excessively_noisy``
    penalising correct claims.
    """

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    DISMISSED = "dismissed"


class ContradictionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contradiction_id: str
    claim_id_a: str
    claim_id_b: str
    state: ContradictionState = ContradictionState.CANDIDATE
    detector: str = ""
    rationale: str = ""
    verification_id: Optional[str] = None


# ── claims, eligibility, release ─────────────────────────────────────────────

class SupportState(str, Enum):
    """Categorical. There is no numeric epistemic rank anywhere in this module."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNRESOLVED = "unresolved"
    FALSIFIED = "falsified"
    EXTERNAL_EVIDENCE_REQUIRED = "external_evidence_required"


class ClaimRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str
    text: str
    author_agent_id: Optional[str] = None
    provider_id: Optional[str] = None
    section: Optional[str] = None
    verification_class: VerificationClass = VerificationClass.NOT_CURRENTLY_VERIFIABLE
    superseded_by: Optional[str] = None


class ClaimAssessment(BaseModel):
    """A claim's governing state, with the records it rests on named."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str
    support_state: SupportState
    basis_record_ids: List[str] = Field(default_factory=list)
    falsifying_record_ids: List[str] = Field(default_factory=list)
    unresolved_record_ids: List[str] = Field(default_factory=list)
    #: Recorded and powerless. Present so an auditor can see what was ignored.
    advisory_note: str = ""
    eligible_for_assembly: bool = False
    ineligibility_reason: str = ""


def stable_id(prefix: str, *parts: Any) -> str:
    """Deterministic identity. No randomness anywhere in this module."""
    return f"{prefix}_" + _digest([str(p) for p in parts])[:16]


# ── deterministic validation of a verification record ────────────────────────

class MalformedVerification(ValueError):
    """A record that cannot be trusted to mean what it says."""


def validate_verification_record(
    record: VerificationRecord,
    *,
    task_text: str,
    evidence: Mapping[str, "EvidenceRecord"] = {},
) -> None:
    """Deterministic checks. Raises ``MalformedVerification`` or returns None.

    What this proves: the record is complete, its method is legal for its class,
    every cited span occurs verbatim in the original task at the offset given,
    and an inconclusive result carries a reason.

    What this does NOT prove: that the reasoning is correct. Deterministic code
    cannot read "Ben does not present last" and evaluate it in general. That
    limit is real and is stated in every record's ``limitations``.
    """
    # A record may honestly report that no method could be applied. That is what
    # EXTERNAL_EVIDENCE_REQUIRED and NOT_APPLICABLE mean, and refusing them here
    # would force a fabricated method onto an honest "I cannot check this".
    no_method_results = (VerificationResult.EXTERNAL_EVIDENCE_REQUIRED,
                         VerificationResult.NOT_APPLICABLE)
    legal = LEGAL_METHODS[record.verification_class]
    if record.result in no_method_results:
        if record.method is not None:
            raise MalformedVerification(
                f"{record.result.value} cannot also name a method")
    elif legal and record.method not in legal:
        raise MalformedVerification(
            f"method {record.method} is not legal for {record.verification_class}")
    elif not legal and record.method is not None:
        raise MalformedVerification(
            f"{record.verification_class} admits no verification method")

    if record.verification_class is VerificationClass.TASK_INTERNAL:
        if not record.authoritative_inputs:
            raise MalformedVerification(
                "a task-internal check must cite the task material it rests on")
        for span in record.authoritative_inputs:
            end = span.offset + len(span.text)
            if task_text[span.offset:end] != span.text:
                raise MalformedVerification(
                    f"cited span is not present at offset {span.offset}: {span.text!r}")
        if not record.condition_tested.strip():
            raise MalformedVerification("condition_tested is required")

    if record.verification_class is VerificationClass.EXTERNAL_EVIDENCE:
        if record.result is VerificationResult.VERIFIED:
            if not record.evidence_ids:
                raise MalformedVerification(
                    "external verification must cite evidence records")
            for eid in record.evidence_ids:
                found = evidence.get(eid)
                if found is None:
                    raise MalformedVerification(f"unknown evidence record {eid}")
                if not found.admissible:
                    raise MalformedVerification(
                        f"{eid} is {found.source_type.value}; a model's assertion "
                        "is not external evidence")

    if record.result is VerificationResult.INCONCLUSIVE and not record.rationale.strip():
        raise MalformedVerification("an inconclusive result must say why")


def verify_task_internal(
    *,
    claim_id: str,
    objection_id: Optional[str],
    task_text: str,
    cited_spans: Sequence[Tuple[str, int]],
    condition_tested: str,
    holds: Optional[bool],
    rationale: str,
    verifier_provider_id: Optional[str] = None,
) -> VerificationRecord:
    """Build a task-internal verification record.

    ``holds`` is the checker's finding: True when the condition is satisfied,
    False when it is violated, None when the check could not be completed. None
    becomes INCONCLUSIVE rather than a guess.
    """
    spans = [AnchorSpan(text=t, offset=o) for t, o in cited_spans]
    if holds is None:
        result = VerificationResult.INCONCLUSIVE
    else:
        result = VerificationResult.VERIFIED if holds else VerificationResult.FALSIFIED
    record = VerificationRecord(
        verification_id=stable_id("ver", claim_id, objection_id or "",
                                  condition_tested, result.value),
        claim_id=claim_id,
        objection_id=objection_id,
        verification_class=VerificationClass.TASK_INTERNAL,
        method=VerificationMethod.TASK_INTERNAL_CHECK,
        authoritative_inputs=spans,
        condition_tested=condition_tested,
        result=result,
        rationale=rationale,
        scope="the cited task material only",
        limitations=("Deterministic code proves the citation is present and exact; "
                     "it does not judge the reasoning that reads it."),
        provenance="task_internal",
        verifier_provider_id=verifier_provider_id,
    )
    validate_verification_record(record, task_text=task_text)
    return record


def external_evidence_required(claim_id: str, why: str) -> VerificationRecord:
    """The honest terminal answer when the task cannot settle a claim."""
    return VerificationRecord(
        verification_id=stable_id("ver", claim_id, "external_required"),
        claim_id=claim_id,
        verification_class=VerificationClass.EXTERNAL_EVIDENCE,
        method=None,
        result=VerificationResult.EXTERNAL_EVIDENCE_REQUIRED,
        rationale=why,
        scope="none — nothing in the task settles this",
        limitations="No governed external evidence substrate exists yet.",
        provenance="classification",
    )


# ── the governing state machine ──────────────────────────────────────────────

class HybridEpistemicState:
    """The single authoritative epistemic state for one session.

    Every governing question — is this claim supported, may it be assembled, may
    the answer be released — is answered here from records alone. No quality
    score, confidence value, marker, agreement count or ratifier tally is an
    input to any of it.
    """

    def __init__(self, session_id: str, task_text: str) -> None:
        self.session_id = session_id
        #: The original task. The anchor for every task-internal check.
        self.task_text = task_text
        self.claims: Dict[str, ClaimRecord] = {}
        self.objections: Dict[str, ObjectionRecord] = {}
        self.evidence: Dict[str, EvidenceRecord] = {}
        self.verifications: Dict[str, VerificationRecord] = {}
        self.revisions: Dict[str, RevisionRecord] = {}
        self.contradictions: Dict[str, ContradictionRecord] = {}
        #: Append-only history of lifecycle moves, for replay and audit.
        self.transitions: List[Dict[str, Any]] = []

    # -- ingestion ------------------------------------------------------------

    def add_claim(self, claim: ClaimRecord) -> ClaimRecord:
        self.claims[claim.claim_id] = claim
        return claim

    def add_evidence(self, record: EvidenceRecord) -> EvidenceRecord:
        self.evidence[record.evidence_id] = record
        return record

    def add_objection(self, objection: ObjectionRecord) -> ObjectionRecord:
        self.objections[objection.objection_id] = objection
        self.transitions.append({"kind": "objection", "id": objection.objection_id,
                                 "to": objection.state.value})
        return objection

    def add_verification(self, record: VerificationRecord) -> VerificationRecord:
        """Store a verification, validating it deterministically first."""
        validate_verification_record(record, task_text=self.task_text,
                                     evidence=self.evidence)
        self.verifications[record.verification_id] = record
        return record

    def add_contradiction(self, record: ContradictionRecord) -> ContradictionRecord:
        self.contradictions[record.contradiction_id] = record
        self.transitions.append({"kind": "contradiction", "id": record.contradiction_id,
                                 "to": record.state.value})
        return record

    # -- objection lifecycle --------------------------------------------------

    def transition_objection(
        self, objection_id: str, to: ObjectionState, *,
        verification_id: Optional[str] = None,
    ) -> ObjectionRecord:
        """Move an objection along a legal edge, or refuse.

        VALIDATED and REJECTED both require a verification record: an objection
        may not acquire — or lose — destructive force by assertion.
        """
        current = self.objections[objection_id]
        allowed = _OBJECTION_TRANSITIONS[current.state]
        if to not in allowed:
            raise ObjectionTransitionError(
                f"{current.state.value} -> {to.value} is not a legal transition")
        if to in (ObjectionState.VALIDATED, ObjectionState.REJECTED):
            if verification_id is None:
                raise ObjectionTransitionError(
                    f"{to.value} requires a verification record")
            record = self.verifications.get(verification_id)
            if record is None:
                raise ObjectionTransitionError(f"unknown verification {verification_id}")
            expected = (VerificationResult.VERIFIED if to is ObjectionState.VALIDATED
                        else VerificationResult.FALSIFIED)
            if record.result is not expected:
                raise ObjectionTransitionError(
                    f"{to.value} requires a {expected.value} verification, "
                    f"got {record.result.value}")
        updated = current.model_copy(update={"state": to,
                                             "verification_id": verification_id})
        self.objections[objection_id] = updated
        self.transitions.append({"kind": "objection", "id": objection_id,
                                 "from": current.state.value, "to": to.value,
                                 "verification_id": verification_id})
        return updated

    def validate_contradiction(
        self, contradiction_id: str, *, verification_id: str,
    ) -> ContradictionRecord:
        """Promote a detected candidate to authoritative, on a record."""
        current = self.contradictions[contradiction_id]
        record = self.verifications.get(verification_id)
        if record is None or record.result is not VerificationResult.VERIFIED:
            raise ObjectionTransitionError(
                "a contradiction is validated only by a VERIFIED record")
        updated = current.model_copy(update={"state": ContradictionState.VALIDATED,
                                             "verification_id": verification_id})
        self.contradictions[contradiction_id] = updated
        self.transitions.append({"kind": "contradiction", "id": contradiction_id,
                                 "from": current.state.value, "to": "validated"})
        return updated

    def dismiss_contradiction(self, contradiction_id: str, why: str) -> ContradictionRecord:
        current = self.contradictions[contradiction_id]
        updated = current.model_copy(update={"state": ContradictionState.DISMISSED,
                                             "rationale": why})
        self.contradictions[contradiction_id] = updated
        self.transitions.append({"kind": "contradiction", "id": contradiction_id,
                                 "from": current.state.value, "to": "dismissed"})
        return updated

    # -- revision -------------------------------------------------------------

    def revise(self, revision: RevisionRecord) -> RevisionRecord:
        """Record a revision. Support is never inherited across it.

        Every evidence item on the superseded claim must be classified. Anything
        left unclassified stays on the old claim rather than moving, which is the
        fix for the frozen ``revised_claim_retains_semantically_stale_evidence``.
        """
        classified = {c.evidence_id for c in revision.evidence_disposition}
        carried = {c.evidence_id for c in revision.evidence_disposition
                   if c.applicability in CARRIED_APPLICABILITY}
        for record in list(self.evidence.values()):
            if record.claim_id != revision.from_claim_id:
                continue
            if record.evidence_id in carried:
                moved = record.model_copy(update={"claim_id": revision.to_claim_id})
                self.evidence[record.evidence_id] = moved
            elif record.evidence_id not in classified:
                self.transitions.append({"kind": "evidence_unclassified",
                                         "id": record.evidence_id,
                                         "revision": revision.revision_id})
        old = self.claims.get(revision.from_claim_id)
        if old is not None:
            self.claims[old.claim_id] = old.model_copy(
                update={"superseded_by": revision.to_claim_id})
        self.revisions[revision.revision_id] = revision
        self.transitions.append({"kind": "revision", "id": revision.revision_id,
                                 "from": revision.from_claim_id,
                                 "to": revision.to_claim_id})
        return revision

    # -- assessment: the governing computation --------------------------------

    def assess_claim(self, claim_id: str) -> ClaimAssessment:
        """Compute a claim's governing state from records only.

        Order matters and is deliberate. A validated objection falsifies before
        anything else is considered, because a refutation anchored in the task
        outranks any amount of accumulated support. Everything below it is about
        what the records do *not* settle.
        """
        claim = self.claims[claim_id]
        basis: List[str] = []
        falsifying: List[str] = []
        unresolved: List[str] = []

        # A validated objection is the one thing that can destroy a claim, and
        # it reached VALIDATED only through a verification record.
        for objection in self.objections.values():
            if objection.target_claim_id != claim_id:
                continue
            if objection.is_destructive:
                falsifying.append(objection.objection_id)
            elif objection.state in (ObjectionState.RAISED,
                                     ObjectionState.PENDING_VERIFICATION,
                                     ObjectionState.INCONCLUSIVE):
                unresolved.append(objection.objection_id)
            # REJECTED objections stay in provenance and weigh nothing.

        # A validated contradiction leaves the pair unresolved; candidates do not.
        for contradiction in self.contradictions.values():
            if claim_id not in (contradiction.claim_id_a, contradiction.claim_id_b):
                continue
            if contradiction.state is ContradictionState.VALIDATED:
                unresolved.append(contradiction.contradiction_id)

        # Support comes only from admissible evidence and verified checks.
        for record in self.evidence.values():
            if record.claim_id != claim_id:
                continue
            if not record.admissible:
                continue                      # a model's assertion is not evidence
            if record.stance is EvidenceStance.SUPPORTING:
                basis.append(record.evidence_id)
            elif record.stance is EvidenceStance.CONTRADICTING:
                unresolved.append(record.evidence_id)
            # WEAK is relevant and insufficient; it never becomes a basis.

        external_required = False
        for record in self.verifications.values():
            if record.claim_id != claim_id or record.objection_id is not None:
                continue
            if record.result is VerificationResult.VERIFIED:
                basis.append(record.verification_id)
            elif record.result is VerificationResult.FALSIFIED:
                falsifying.append(record.verification_id)
            elif record.result is VerificationResult.EXTERNAL_EVIDENCE_REQUIRED:
                external_required = True
                unresolved.append(record.verification_id)
            elif record.result is VerificationResult.INCONCLUSIVE:
                unresolved.append(record.verification_id)

        if falsifying:
            state = SupportState.FALSIFIED
        elif external_required and not basis:
            state = SupportState.EXTERNAL_EVIDENCE_REQUIRED
        elif unresolved:
            state = SupportState.UNRESOLVED
        elif basis:
            state = SupportState.SUPPORTED
        else:
            state = SupportState.UNSUPPORTED

        eligible, reason = self._eligibility(claim, state)
        return ClaimAssessment(
            claim_id=claim_id,
            support_state=state,
            basis_record_ids=sorted(set(basis)),
            falsifying_record_ids=sorted(set(falsifying)),
            unresolved_record_ids=sorted(set(unresolved)),
            advisory_note=("quality, confidence, markers, agreement and ratifier "
                           "counts were not inputs to this state"),
            eligible_for_assembly=eligible,
            ineligibility_reason=reason,
        )

    def _eligibility(
        self, claim: ClaimRecord, state: SupportState,
    ) -> Tuple[bool, str]:
        """Assembly eligibility, derived from governing state alone.

        Never from a quality rank, an agreement count, a marker, a confidence
        value or a CBE-style numeric score.
        """
        if claim.superseded_by is not None:
            return False, f"superseded by {claim.superseded_by}"
        if state is SupportState.FALSIFIED:
            return False, "a validated objection or falsifying check stands"
        return True, ""

    def assess_all(self) -> Dict[str, ClaimAssessment]:
        return {cid: self.assess_claim(cid) for cid in self.claims}

    # -- compatibility (H5) ---------------------------------------------------

    def incompatible_pairs(self, claim_ids: Sequence[str]) -> List[Tuple[str, str]]:
        """Validated contradictions among a candidate set.

        Only VALIDATED contradictions block assembly. A noisy detector may
        propose as many CANDIDATE edges as it likes and penalise nothing, which
        is the fix for ``contradiction_edges_are_excessively_noisy``.
        """
        chosen = set(claim_ids)
        pairs: List[Tuple[str, str]] = []
        for contradiction in self.contradictions.values():
            if contradiction.state is not ContradictionState.VALIDATED:
                continue
            a, b = contradiction.claim_id_a, contradiction.claim_id_b
            if a in chosen and b in chosen:
                pairs.append(tuple(sorted((a, b))))
        return sorted(set(pairs))

    def eligible_claim_ids(self) -> List[str]:
        return sorted(cid for cid, a in self.assess_all().items()
                      if a.eligible_for_assembly)


# ── H7: claim-level ratification and frozen release ──────────────────────────

class RatificationDisposition(str, Enum):
    """What a ratifier said about one identified claim."""

    ACCEPT = "accept"
    ACCEPT_WITH_CAVEAT = "accept_with_caveat"
    OBJECT = "object"


class ClaimBallot(BaseModel):
    """One ratifier's disposition toward one claim, with what it checked.

    The frozen failure recorded three ratifiers accepting an objectively wrong
    answer under well-worded criteria. The criteria were not the defect: the
    ballot carried a verdict and some prose and nothing that said what had been
    checked. ``checked_verification_ids`` is that missing field.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ballot_id: str
    claim_id: str
    ratifier_provider_id: str
    disposition: RatificationDisposition
    rationale: str = ""
    #: Verification records this ratifier relied on. A ballot with none is
    #: recorded as unanchored and cannot move epistemic state.
    checked_verification_ids: List[str] = Field(default_factory=list)
    caveat: Optional[str] = None

    @property
    def anchored(self) -> bool:
        return bool(self.checked_verification_ids)


class ReleaseDecision(str, Enum):
    """What the system is willing to say about the answer it is emitting."""

    #: Every assembled claim is supported by records.
    RELEASE_SUPPORTED = "release_supported"
    #: Emitted honestly, with its epistemic state stated as unresolved.
    RELEASE_UNRESOLVED = "release_unresolved"
    #: Something falsified or incompatible is in the way.
    BLOCKED = "blocked"


class FrozenRelease(BaseModel):
    """The released answer and the exact record set that governed it.

    Freezing is what makes the release reproducible: replaying these records
    must produce this decision, and a later change to the session cannot quietly
    rewrite what was already published.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = HYBRID_EPISTEMIC_SCHEMA_VERSION
    session_id: str
    release_decision: ReleaseDecision
    #: Claims actually assembled into the answer.
    released_claim_ids: List[str] = Field(default_factory=list)
    #: Their governing states, frozen alongside.
    claim_states: Dict[str, str] = Field(default_factory=dict)
    basis_record_ids: List[str] = Field(default_factory=list)
    unresolved_record_ids: List[str] = Field(default_factory=list)
    blocked_reason: str = ""
    #: Ratification, reported and never converted into support.
    anchored_ballots: int = 0
    unanchored_ballots: int = 0
    inconsistent_ballots: List[str] = Field(default_factory=list)
    #: Quality and the legacy status travel alongside, governing nothing.
    quality_mean: Optional[float] = None
    legacy_epistemic_status: Optional[str] = None
    #: Digest over the governing records. Changes if the basis changes.
    frozen_digest: str = ""


def ballot_is_inconsistent(
    ballot: ClaimBallot, verifications: Mapping[str, VerificationRecord],
) -> bool:
    """True when a ballot's verdict contradicts its own cited checks.

    A ratifier that cites a FALSIFIED check and then votes ACCEPT is internally
    inconsistent. That is detectable without judging the reasoning, and it is
    the one thing a ballot can get mechanically wrong.
    """
    if ballot.disposition is RatificationDisposition.OBJECT:
        return False
    for vid in ballot.checked_verification_ids:
        record = verifications.get(vid)
        if record is not None and record.result is VerificationResult.FALSIFIED:
            return True
    return False


def freeze_release(
    state: HybridEpistemicState,
    *,
    assembled_claim_ids: Sequence[str],
    ballots: Sequence[ClaimBallot] = (),
    quality_mean: Optional[float] = None,
    legacy_epistemic_status: Optional[str] = None,
) -> FrozenRelease:
    """Decide and freeze a release from the governing records.

    Ratification is reported, never summed into support. A unanimous council
    cannot raise an unsupported answer, and a lone anchored refutation is not
    outvoted.
    """
    assessments = {cid: state.assess_claim(cid) for cid in assembled_claim_ids}

    blocked: List[str] = []
    for cid, assessment in assessments.items():
        if assessment.support_state is SupportState.FALSIFIED:
            blocked.append(f"{cid} is falsified")
        elif not assessment.eligible_for_assembly:
            blocked.append(f"{cid}: {assessment.ineligibility_reason}")

    incompatible = state.incompatible_pairs(list(assembled_claim_ids))
    for a, b in incompatible:
        blocked.append(f"{a} and {b} are a validated contradiction")

    basis: List[str] = []
    unresolved: List[str] = []
    for assessment in assessments.values():
        basis.extend(assessment.basis_record_ids)
        unresolved.extend(assessment.unresolved_record_ids)

    anchored = sum(1 for b in ballots if b.anchored)
    unanchored = sum(1 for b in ballots if not b.anchored)
    inconsistent = sorted(b.ballot_id for b in ballots
                          if ballot_is_inconsistent(b, state.verifications))

    if blocked:
        decision = ReleaseDecision.BLOCKED
    elif unresolved or not basis:
        # Honest emission: the answer goes out, its epistemic state goes with it.
        decision = ReleaseDecision.RELEASE_UNRESOLVED
    else:
        decision = ReleaseDecision.RELEASE_SUPPORTED

    frozen = {
        "session": state.session_id,
        "claims": sorted(assembled_claim_ids),
        "states": {cid: a.support_state.value for cid, a in sorted(assessments.items())},
        "basis": sorted(set(basis)),
        "unresolved": sorted(set(unresolved)),
        "decision": decision.value,
    }
    return FrozenRelease(
        session_id=state.session_id,
        release_decision=decision,
        released_claim_ids=sorted(assembled_claim_ids),
        claim_states={cid: a.support_state.value for cid, a in assessments.items()},
        basis_record_ids=sorted(set(basis)),
        unresolved_record_ids=sorted(set(unresolved)),
        blocked_reason="; ".join(blocked),
        anchored_ballots=anchored,
        unanchored_ballots=unanchored,
        inconsistent_ballots=inconsistent,
        quality_mean=quality_mean,
        legacy_epistemic_status=legacy_epistemic_status,
        frozen_digest=_digest(frozen),
    )


# ── ledger projection ────────────────────────────────────────────────────────

class HybridEpistemicObserver:
    """Projects the governing state into the single existing ledger."""

    def __init__(self, ledger: HybridEpistemicLedger) -> None:
        self.ledger = ledger

    def capture(
        self, state: HybridEpistemicState, release: FrozenRelease,
    ) -> List[HybridShadowRecord]:
        records: List[HybridShadowRecord] = []
        for cid, assessment in sorted(state.assess_all().items()):
            records.append(self.ledger.append(
                session_id=state.session_id,
                kind=HybridRecordKind.CLAIM_ASSESSED,
                subject_ref=f"claim:{cid}",
                payload=assessment.model_dump(mode="json"),
            ))
        for oid, objection in sorted(state.objections.items()):
            records.append(self.ledger.append(
                session_id=state.session_id,
                kind=HybridRecordKind.OBJECTION_LIFECYCLE,
                subject_ref=f"objection:{oid}",
                payload=objection.model_dump(mode="json"),
            ))
        for vid, verification in sorted(state.verifications.items()):
            records.append(self.ledger.append(
                session_id=state.session_id,
                kind=HybridRecordKind.VERIFICATION_RECORDED,
                subject_ref=f"verification:{vid}",
                payload=verification.model_dump(mode="json"),
            ))
        records.append(self.ledger.append(
            session_id=state.session_id,
            kind=HybridRecordKind.RELEASE_FROZEN,
            subject_ref=f"release:{state.session_id}",
            payload=release.model_dump(mode="json"),
        ))
        return records
