"""Socrates Epistemic Hybrid v1 — H2 quality/epistemic-support separation.

H1 classified the existing seven-dimension peer score as a QUALITY score
(``move_quality_score.observed``). H2 supplies the measure that name implies is
missing: an epistemic SUPPORT assessment that is computed separately, carries no
authority, and is never mixed into the quality score.

Why the separation is needed, measured rather than assumed: two live councils
were run on the same downstream question, differing only in whether the premise
handed to them was true. The premise-false arm scored ``factual_grounding`` 7.07
and the premise-true arm 6.78 — the poorly grounded answer scored HIGHER, and
every dimension separated the arms by less than 0.3 on a 0..10 scale. The
quality dimensions track fluency and structure, not epistemic support.

Design constraints inherited from the H0.5 preservation contract:

* additive and feature-gated — the assessment is opt-in and off by default;
* non-authoritative — nothing here feeds scoring, assembly, ratification,
  release, ``SessionState`` or ``FinalResponse``;
* no second authority — H2 appends to the single existing H1 ledger rather than
  opening a parallel store;
* deterministic — the assessment is a pure function of canonical artifacts and
  makes no provider or network call, so it is replayable and offline-testable;
* honest — a deterministic measure cannot know whether a claim is TRUE. It
  measures whether the council SUPPORTED its claims and whether it ever examined
  the question's own assertions. Truth adjudication is not claimed here.
"""

from __future__ import annotations

import re
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
    EpistemicMarker,
    FinalResponse,
    SessionState,
)
from .reasoning_prompts import MARKER_CONFIDENCE_BANDS

HYBRID_SUPPORT_SCHEMA_VERSION = "socrates.hybrid-support.h2/v1"

# How much epistemic support each honesty marker asserts. These are NOT quality
# weights: an "open_uncertainty" move can be excellent work and still supply
# little support for a conclusion. Ordered strictly by the strength of the
# epistemic claim the marker makes.
MARKER_SUPPORT_WEIGHTS: Dict[EpistemicMarker, float] = {
    EpistemicMarker.ESTABLISHED_FACT: 1.0,
    EpistemicMarker.LOGICAL_INFERENCE: 0.8,
    EpistemicMarker.REASONABLE_HYPOTHESIS: 0.5,
    EpistemicMarker.OPEN_UNCERTAINTY: 0.25,
    EpistemicMarker.UNSUBSTANTIATED_CLAIM: 0.0,
}

# Phases whose job is to apply pressure. Premise scrutiny is only credited here:
# an opening question restating the prompt is not scrutiny of it.
_SCRUTINY_PHASES = (DialogPhase.ELENCHUS, DialogPhase.REFLECTION)

# A move scrutinises the premise when it reuses the question's distinctive terms
# AND carries an explicit challenge token. Deterministic and deliberately
# conservative: it under-reports rather than inventing scrutiny that never
# happened.
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
    """Distinctive content words of the question, lowercased and deduplicated."""
    seen: Dict[str, None] = {}
    for raw in _WORD_RE.findall(question or ""):
        word = raw.lower()
        if word in _STOPWORDS:
            continue
        seen.setdefault(word, None)
    return tuple(seen)


def _move_text(content: Any) -> str:
    """Flatten a move's content object into searchable text."""
    if isinstance(content, str):
        return content
    if isinstance(content, Mapping):
        return " ".join(_move_text(v) for v in content.values())
    if isinstance(content, (list, tuple)):
        return " ".join(_move_text(v) for v in content)
    return str(content)


class MoveSupport(BaseModel):
    """Per-move support facts. Records what the move CLAIMED, not whether it is true."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    move_id: str
    agent_id: str
    phase: str
    marker: Optional[str] = None
    confidence: float
    marked: bool
    support_weight: Optional[float] = None
    confidence_ceiling: Optional[float] = None
    overconfident: bool = False


class EpistemicSupportAssessment(BaseModel):
    """H2 support view of one finalized session. Non-authoritative by construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = HYBRID_SUPPORT_SCHEMA_VERSION
    authority: str = SHADOW_AUTHORITY
    session_id: str

    moves_total: int = 0
    moves_marked: int = 0
    #: Share of moves that asserted with no honesty marker at all. A bare
    #: assertion supplies no support, however well written it is.
    unmarked_assertion_ratio: float = 0.0
    marker_counts: Dict[str, int] = Field(default_factory=dict)

    #: Mean support weight over MARKED moves, or None when nothing was marked.
    #: Deliberately not defaulted to 0.0 — "no marked claims" is missing data,
    #: not zero support, and CED never fabricates a missing measure.
    support_index: Optional[float] = None
    #: Share of moves carrying a marker. A high support_index over a tiny
    #: coverage_ratio is weak evidence and must be read together with it.
    coverage_ratio: float = 0.0

    #: Moves whose confidence exceeds the ceiling their own marker allows.
    overconfidence_violations: int = 0

    #: Did any pressure-phase move actually examine the question's assertions?
    premise_scrutinised: bool = False
    premise_scrutiny_moves: List[str] = Field(default_factory=list)

    #: The quality mean carried alongside for contrast ONLY. H2 never combines
    #: the two into one number; keeping them adjacent is the whole point.
    quality_mean: Optional[float] = None

    moves: List[MoveSupport] = Field(default_factory=list)


def assess_session_support(state: SessionState) -> EpistemicSupportAssessment:
    """Compute the H2 support assessment from canonical artifacts only.

    Pure: no provider call, no network, no mutation of ``state``. Given the same
    session it returns the same assessment, so it is replayable offline.
    """
    question_terms = _question_terms(state.question)
    rows: List[MoveSupport] = []
    marker_counts: Dict[str, int] = {}
    weights: List[float] = []
    overconfident = 0
    scrutiny_moves: List[str] = []

    for move in state.moves:
        marker = move.epistemic_markers[0] if move.epistemic_markers else None
        marker_value = marker.value if marker is not None else None
        ceiling = MARKER_CONFIDENCE_BANDS.get(marker_value) if marker_value else None
        is_over = bool(ceiling is not None and move.confidence > ceiling + 1e-9)
        if is_over:
            overconfident += 1

        weight: Optional[float] = None
        if marker is not None:
            marker_counts[marker_value] = marker_counts.get(marker_value, 0) + 1
            weight = MARKER_SUPPORT_WEIGHTS.get(marker)
            if weight is not None:
                weights.append(weight)

        rows.append(MoveSupport(
            move_id=move.move_id,
            agent_id=move.agent_id,
            phase=move.phase.value,
            marker=marker_value,
            confidence=float(move.confidence),
            marked=marker is not None,
            support_weight=weight,
            confidence_ceiling=ceiling,
            overconfident=is_over,
        ))

        if move.phase in _SCRUTINY_PHASES and _scrutinises_premise(move.content, question_terms):
            scrutiny_moves.append(move.move_id)

    total = len(rows)
    marked = sum(1 for r in rows if r.marked)
    quality_scores = [
        ms.score_breakdown.weighted_overall() for ms in state.micro_scores
    ]

    return EpistemicSupportAssessment(
        session_id=state.session_id,
        moves_total=total,
        moves_marked=marked,
        unmarked_assertion_ratio=round((total - marked) / total, 6) if total else 0.0,
        marker_counts=marker_counts,
        support_index=round(sum(weights) / len(weights), 6) if weights else None,
        coverage_ratio=round(marked / total, 6) if total else 0.0,
        overconfidence_violations=overconfident,
        premise_scrutinised=bool(scrutiny_moves),
        premise_scrutiny_moves=scrutiny_moves,
        quality_mean=(round(sum(quality_scores) / len(quality_scores), 6)
                      if quality_scores else None),
        moves=rows,
    )


def _scrutinises_premise(content: Any, question_terms: Sequence[str]) -> bool:
    """True when a move both engages the question's terms and challenges them."""
    if not question_terms:
        return False
    text = _move_text(content).lower()
    if not any(token in text for token in _CHALLENGE_TOKENS):
        return False
    overlap = sum(1 for term in question_terms if term in text)
    return overlap >= 2


class HybridSupportObserver:
    """Appends H2 support records to the single existing H1 ledger.

    Reuses the H1 ledger deliberately: the preservation contract forbids a second
    authority, and a parallel store would be exactly that.
    """

    def __init__(self, ledger: HybridEpistemicLedger) -> None:
        self.ledger = ledger

    def capture_support(
        self, state: SessionState, final: FinalResponse,
    ) -> List[HybridShadowRecord]:
        """Observe support for a finalized session. Never mutates either model."""
        assessment = assess_session_support(state)
        records = [self.ledger.append(
            session_id=state.session_id,
            kind=HybridRecordKind.SESSION_SUPPORT_ASSESSED,
            subject_ref=f"support:{state.session_id}",
            payload={
                "schema_version": assessment.schema_version,
                "moves_total": assessment.moves_total,
                "moves_marked": assessment.moves_marked,
                "unmarked_assertion_ratio": assessment.unmarked_assertion_ratio,
                "marker_counts": assessment.marker_counts,
                "support_index": assessment.support_index,
                "coverage_ratio": assessment.coverage_ratio,
                "overconfidence_violations": assessment.overconfidence_violations,
                "premise_scrutinised": assessment.premise_scrutinised,
                "premise_scrutiny_moves": list(assessment.premise_scrutiny_moves),
                # Carried side by side, never merged.
                "quality_mean": assessment.quality_mean,
                "ratified": bool(final.ratified),
            },
        )]
        for row in assessment.moves:
            records.append(self.ledger.append(
                session_id=state.session_id,
                kind=HybridRecordKind.MOVE_SUPPORT_ASSESSED,
                subject_ref=f"support_move:{row.move_id}",
                payload=row.model_dump(mode="json"),
            ))
        return records
