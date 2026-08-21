"""Socrates Epistemic Hybrid v1 — H2 quality/epistemic-support separation.

H1 classified the existing seven-dimension peer score as a QUALITY score
(``move_quality_score.observed``). H2 separates the two planes that were being
read as one, and does nothing else.

Why the separation is needed, measured rather than assumed. Two live councils
were run on the same downstream question, differing only in whether the premise
handed to them was true. The premise-false arm scored ``factual_grounding`` 7.07
and 6.93 across runs; the premise-true arm scored 6.78 and 6.41. The poorly
grounded answer scored HIGHER, and no dimension separated the arms by more than
0.52 on a 0..10 scale. Worse, the canonical ``_epistemic_hint`` promotes any
session whose mean quality score reaches 7.5 to ``WELL_SUPPORTED``, and the
premise-false arm measured 7.609. A discredited premise, fluently argued, was
over that line.

## The two planes

**Quality plane.** How well the council argued: peer scores, the leaderboard,
the legacy threshold status. Fully visible here, and authoritative over nothing.

**Epistemic-support plane.** Whether a conclusion is actually supported.
Categorical, and derived ONLY from authoritative support records.

## Why there is no number

An earlier revision of this module computed a ``support_index`` by averaging
epistemic markers. That was wrong, and the wrongness is worth stating plainly: a
marker is the MODEL'S OWN LABEL for its OWN claim, so a council that stamped
``established_fact`` on every move would have scored a perfect "support" figure.
Self-description had been promoted to evidence.

No numeric epistemic ranker replaces it. Not from markers, not from confidence,
not from quality, not from agreement, corroboration counts or ratifier
popularity. A single number invites exactly the collapse the measurements above
document. Support is categorical, and every status names the records it rests on.

## What that yields today

No authoritative support record exists anywhere in the system yet: verification,
evidence promotion and objection validation are H3+ and are not implemented. So
``basis_record_ids`` is empty and the status is honestly ``UNSUPPORTED`` or
``UNRESOLVED``. That is the correct answer, not a gap to paper over.

## Authority boundary

* additive and off by default — injected by a caller, no orchestrator wiring;
* non-authoritative — feeds nothing in scoring, assembly, ratification, release,
  ``SessionState`` or ``FinalResponse``;
* no second authority — records append to the single existing H1 ledger;
* deterministic — a pure function of canonical artifacts, no provider call;
* the legacy canonical status is carried through unchanged for comparison and is
  never an input to the Hybrid status.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from .hybrid_shadow import (
    SHADOW_AUTHORITY,
    HybridEpistemicLedger,
    HybridRecordKind,
    HybridShadowRecord,
)
from .models import (
    DialogPhase,
    FinalResponse,
    SessionState,
)
from .reasoning_prompts import MARKER_CONFIDENCE_BANDS

HYBRID_SUPPORT_SCHEMA_VERSION = "socrates.hybrid-support.h2/v2"


class SupportInputClass(str, Enum):
    """How each canonical input may be used by the epistemic-support plane."""

    AUTHORITATIVE_SUPPORT = "authoritative_support"
    AUTHORITATIVE_CONTRADICTION = "authoritative_contradiction"
    UNRESOLVED = "unresolved"
    ADVISORY_METADATA = "advisory_metadata"
    QUALITY_SIGNAL = "quality_signal"


class HybridSupportStatus(str, Enum):
    """Categorical support state. Never numeric, never ranked.

    Only the two honest states are defined. A SUPPORTED value would require
    authoritative support records, which verification (H3+) has not yet made it
    possible to produce. Defining it now would invite something to fill it.
    """

    UNSUPPORTED = "unsupported"
    UNRESOLVED = "unresolved"


#: Every input the support plane could see, and the only way it may be used.
#: Nothing is classified AUTHORITATIVE_SUPPORT: no such record exists before H3.
SUPPORT_INPUT_CLASSIFICATION: Dict[str, SupportInputClass] = {
    # Model self-description. Never evidence.
    "epistemic_marker": SupportInputClass.ADVISORY_METADATA,
    "move_confidence": SupportInputClass.ADVISORY_METADATA,
    # How well it was argued, not whether it is so.
    "peer_quality_score": SupportInputClass.QUALITY_SIGNAL,
    "section_quality_score": SupportInputClass.QUALITY_SIGNAL,
    "epistemic_leaderboard": SupportInputClass.QUALITY_SIGNAL,
    # Popularity among ratifiers is agreement, not corroboration.
    "ratification_verdict": SupportInputClass.QUALITY_SIGNAL,
    "council_agreement": SupportInputClass.QUALITY_SIGNAL,
    # A score threshold wearing an epistemic name.
    "legacy_epistemic_status": SupportInputClass.QUALITY_SIGNAL,
    # Raised, and never verified by anything.
    "elenchus_objection": SupportInputClass.UNRESOLVED,
    "ratification_objection": SupportInputClass.UNRESOLVED,
}

#: Inputs that may establish support. Empty until H3+ implements verification.
AUTHORITATIVE_SUPPORT_INPUTS: Tuple[str, ...] = tuple(
    name for name, kind in SUPPORT_INPUT_CLASSIFICATION.items()
    if kind is SupportInputClass.AUTHORITATIVE_SUPPORT
)

_SCRUTINY_PHASES = (DialogPhase.ELENCHUS, DialogPhase.REFLECTION)

_CHALLENGE_TOKENS = (
    "assumption", "premise", "presuppos", "unfounded", "unsupported",
    "not supported", "contest", "disput", "criticis", "criticiz", "critique",
    "flawed", "discredit", "debunk", "overstate", "questionable", "misleading",
    "fails to", "does not follow", "no evidence", "lacks evidence",
)

_STOPWORDS = frozenset("""
about above after again against because been before being below between both
during each further having however into itself more most other over same some
such than that their them then there these they this those through under until
very were what when where which while whose with would your
""".split())

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']{4,}")


def _question_terms(question: str) -> Tuple[str, ...]:
    seen: Dict[str, None] = {}
    for raw in _WORD_RE.findall(question or ""):
        word = raw.lower()
        if word not in _STOPWORDS:
            seen.setdefault(word, None)
    return tuple(seen)


def _move_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, Mapping):
        return " ".join(_move_text(v) for v in content.values())
    if isinstance(content, (list, tuple)):
        return " ".join(_move_text(v) for v in content)
    return str(content)


def _scrutinises_premise(content: Any, question_terms: Sequence[str]) -> bool:
    if not question_terms:
        return False
    text = _move_text(content).lower()
    if not any(token in text for token in _CHALLENGE_TOKENS):
        return False
    return sum(1 for term in question_terms if term in text) >= 2


class MoveMarkerObservation(BaseModel):
    """One move's self-description. Advisory metadata, authoritative over nothing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    move_id: str
    agent_id: str
    phase: str
    marker: Optional[str] = None
    confidence: float
    marked: bool
    confidence_ceiling: Optional[float] = None
    overconfident: bool = False


class EpistemicSupportAssessment(BaseModel):
    """H2 view of one finalized session, in two strictly separated planes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = HYBRID_SUPPORT_SCHEMA_VERSION
    authority: str = SHADOW_AUTHORITY
    session_id: str

    # ── epistemic-support plane (categorical, record-based) ──────────────────
    hybrid_h2_epistemic_status: HybridSupportStatus = HybridSupportStatus.UNSUPPORTED
    #: Authoritative records this status rests on. Empty until H3+ produces any.
    basis_record_ids: List[str] = Field(default_factory=list)
    #: Challenges raised in the dialogue that nothing has verified either way.
    unresolved_record_ids: List[str] = Field(default_factory=list)
    advisory_metadata_count: int = 0
    quality_signal_count: int = 0

    # ── quality plane (visible, authoritative over nothing) ──────────────────
    quality_mean: Optional[float] = None
    #: The canonical status, carried through unchanged for comparison. It is a
    #: quality-score threshold (mean >= 7.5 -> well_supported) and is NEVER an
    #: input to hybrid_h2_epistemic_status.
    legacy_epistemic_status: Optional[str] = None

    # ── advisory metadata (visible, authoritative over nothing) ──────────────
    moves_total: int = 0
    moves_marked: int = 0
    unmarked_assertion_ratio: float = 0.0
    coverage_ratio: float = 0.0
    marker_counts: Dict[str, int] = Field(default_factory=dict)
    overconfidence_violations: int = 0
    premise_scrutinised: bool = False
    premise_scrutiny_moves: List[str] = Field(default_factory=list)
    moves: List[MoveMarkerObservation] = Field(default_factory=list)


def assess_session_support(
    state: SessionState, final: Optional[FinalResponse] = None,
) -> EpistemicSupportAssessment:
    """Compute the H2 assessment from canonical artifacts only.

    Pure: no provider call, no network, no mutation of ``state`` or ``final``.

    ``final`` is read only to carry the legacy canonical status through for
    comparison. The threshold that produces it is not reimplemented here — one
    authority for that rule, and it stays in CED.
    """
    question_terms = _question_terms(state.question)
    rows: List[MoveMarkerObservation] = []
    marker_counts: Dict[str, int] = {}
    overconfident = 0
    scrutiny_moves: List[str] = []
    unresolved: List[str] = []

    for move in state.moves:
        marker = move.epistemic_markers[0] if move.epistemic_markers else None
        marker_value = marker.value if marker is not None else None
        ceiling = MARKER_CONFIDENCE_BANDS.get(marker_value) if marker_value else None
        is_over = bool(ceiling is not None and move.confidence > ceiling + 1e-9)
        if is_over:
            overconfident += 1
        if marker_value is not None:
            marker_counts[marker_value] = marker_counts.get(marker_value, 0) + 1

        rows.append(MoveMarkerObservation(
            move_id=move.move_id,
            agent_id=move.agent_id,
            phase=move.phase.value,
            marker=marker_value,
            confidence=float(move.confidence),
            marked=marker is not None,
            confidence_ceiling=ceiling,
            overconfident=is_over,
        ))

        # An objection raised in the dialogue is a challenge nothing has yet
        # resolved. It cannot support a conclusion, and it cannot refute one
        # either — validation is H3. It is recorded as open.
        if move.phase is DialogPhase.ELENCHUS:
            unresolved.append(move.move_id)
        if move.phase in _SCRUTINY_PHASES and _scrutinises_premise(
                move.content, question_terms):
            scrutiny_moves.append(move.move_id)

    total = len(rows)
    marked = sum(1 for r in rows if r.marked)
    quality_scores = [ms.score_breakdown.weighted_overall()
                      for ms in state.micro_scores]

    # Advisory metadata: one marker observation and one confidence reading per
    # move. Quality signals: every peer score. Neither may reach the status.
    advisory = marked + total
    quality_signals = len(quality_scores)

    # The status names what it rests on. With no authoritative support record in
    # existence, the only honest answers are "open challenges stand" or "nothing
    # establishes this".
    status = (HybridSupportStatus.UNRESOLVED if unresolved
              else HybridSupportStatus.UNSUPPORTED)

    legacy = None
    if final is not None and getattr(final, "epistemic_status", None) is not None:
        legacy = final.epistemic_status.value

    return EpistemicSupportAssessment(
        session_id=state.session_id,
        hybrid_h2_epistemic_status=status,
        basis_record_ids=[],          # nothing authoritative exists before H3+
        unresolved_record_ids=unresolved,
        advisory_metadata_count=advisory,
        quality_signal_count=quality_signals,
        quality_mean=(round(sum(quality_scores) / len(quality_scores), 6)
                      if quality_scores else None),
        legacy_epistemic_status=legacy,
        moves_total=total,
        moves_marked=marked,
        unmarked_assertion_ratio=round((total - marked) / total, 6) if total else 0.0,
        coverage_ratio=round(marked / total, 6) if total else 0.0,
        marker_counts=marker_counts,
        overconfidence_violations=overconfident,
        premise_scrutinised=bool(scrutiny_moves),
        premise_scrutiny_moves=scrutiny_moves,
        moves=rows,
    )


class HybridSupportObserver:
    """Appends H2 records to the single existing H1 ledger.

    Reuses that ledger deliberately: the preservation contract forbids a second
    authority, and a parallel store would be one.
    """

    def __init__(self, ledger: HybridEpistemicLedger) -> None:
        self.ledger = ledger

    def capture_support(
        self, state: SessionState, final: FinalResponse,
    ) -> List[HybridShadowRecord]:
        """Observe a finalized session. Never mutates either model."""
        a = assess_session_support(state, final)
        records = [self.ledger.append(
            session_id=state.session_id,
            kind=HybridRecordKind.SESSION_SUPPORT_ASSESSED,
            subject_ref=f"support:{state.session_id}",
            payload={
                "schema_version": a.schema_version,
                # support plane
                "hybrid_h2_epistemic_status": a.hybrid_h2_epistemic_status.value,
                "basis_record_ids": list(a.basis_record_ids),
                "unresolved_record_ids": list(a.unresolved_record_ids),
                "advisory_metadata_count": a.advisory_metadata_count,
                "quality_signal_count": a.quality_signal_count,
                # quality plane, side by side and never merged
                "quality_mean": a.quality_mean,
                "legacy_epistemic_status": a.legacy_epistemic_status,
                # advisory metadata
                "moves_total": a.moves_total,
                "moves_marked": a.moves_marked,
                "coverage_ratio": a.coverage_ratio,
                "unmarked_assertion_ratio": a.unmarked_assertion_ratio,
                "marker_counts": a.marker_counts,
                "overconfidence_violations": a.overconfidence_violations,
                "premise_scrutinised": a.premise_scrutinised,
                "premise_scrutiny_moves": list(a.premise_scrutiny_moves),
                "ratified": bool(final.ratified),
            },
        )]
        for row in a.moves:
            records.append(self.ledger.append(
                session_id=state.session_id,
                kind=HybridRecordKind.MOVE_SUPPORT_ASSESSED,
                subject_ref=f"support_move:{row.move_id}",
                payload=row.model_dump(mode="json"),
            ))
        return records
