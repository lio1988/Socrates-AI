"""
CED Integration Report v0.1 (read-only reporting layer)
=======================================================

A thin, deterministic *reporting* wrapper that shows how the existing layers
combine for a user-facing epistemic answer:

    raw_cbe  +  evidence_status/balance  +  argumentation_label  +  final_answer
    --------------------------------------------------------------------------->
    CEDIntegrationReport

It REUSES (and never mutates) the existing functions:
  * ``produce_current_best_explanation`` (raw CBE)   -- supplied by the caller
  * ``evidence_status`` / ``evidence_balance``       -- Evidence Layer
  * ``label_graph`` (grounded labeling)              -- Argumentation Framework
  * ``compose_final_epistemic_answer``               -- evidence-constrained composer

For every claim surfaced by raw CBE it answers: *how should this claim be
presented, given BOTH evidence status and argumentation status?* The combined
``final_handling`` is a presentation suggestion only -- it does not promote or
demote claims, does not change CBE ranking, and does not enforce anything in the
core. This is integration/reporting, not v0.2 enforcement.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.epistemic.epistemic_graph import EpistemicGraph
from backend.epistemic.evidence_scoring import (
    EvidenceStatus,
    evidence_balance,
    evidence_status,
)
from backend.epistemic.argumentation_framework import ArgLabel, label_graph
from backend.reasoning.evidence_constrained_cbe import compose_final_epistemic_answer

# --- final_handling vocabulary (deterministic) ------------------------------ #
PRIMARY_CANDIDATE = "primary_candidate"
WELL_SUPPORTED_BUT_DEFEATED = "well_supported_but_defeated"
WELL_SUPPORTED_BUT_UNRESOLVED = "well_supported_but_unresolved"
TENTATIVE_CANDIDATE = "tentative_candidate"
WEAK_AND_DEFEATED = "weak_and_defeated"
WEAKLY_SUPPORTED_BUT_UNRESOLVED = "weakly_supported_but_unresolved"
STRUCTURALLY_ACCEPTABLE_BUT_UNSUPPORTED = "structurally_acceptable_but_unsupported"
UNSUPPORTED_AND_DEFEATED = "unsupported_and_defeated"
UNSUPPORTED_AND_UNRESOLVED = "unsupported_and_unresolved"
CONTESTED = "contested"
REFUTED = "refuted"

NO_CLEAN_ANSWER = (
    "No fully supported and structurally undefeated answer is available from the "
    "current evidence and argumentation graph."
)

_NOTE = (
    "CED Integration Report v0.1 (read-only). Combines raw CBE, evidence audit, "
    "and grounded argumentation labels. final_handling is a presentation "
    "suggestion, not core enforcement: it does not change CBE ranking, "
    "evidence_quality, claim state, or promotion."
)

# Coarse grouping of final_handling values, for the report summary.
_BUCKET = {
    PRIMARY_CANDIDATE: "primary",
    TENTATIVE_CANDIDATE: "tentative",
    WELL_SUPPORTED_BUT_DEFEATED: "defeated",
    WEAK_AND_DEFEATED: "defeated",
    UNSUPPORTED_AND_DEFEATED: "defeated",
    WELL_SUPPORTED_BUT_UNRESOLVED: "unresolved",
    WEAKLY_SUPPORTED_BUT_UNRESOLVED: "unresolved",
    UNSUPPORTED_AND_UNRESOLVED: "unresolved",
    STRUCTURALLY_ACCEPTABLE_BUT_UNSUPPORTED: "unsupported",
    CONTESTED: "contested",
    REFUTED: "refuted",
}


def compute_final_handling(status: EvidenceStatus, label: Optional[ArgLabel]) -> str:
    """Deterministic combination of evidence status and argumentation label.

    Evidence REFUTED / CONTESTED dominate (they ignore the structural label).
    Only ``WELL_SUPPORTED + IN`` yields ``primary_candidate``; OUT, MISSING and
    REFUTED can never be a clean primary.

    ``label`` may be ``None`` (claim is not an argument); it is then treated as
    non-IN/non-OUT (i.e. unresolved), so it can never become primary.
    """
    if status == EvidenceStatus.REFUTED:
        return REFUTED
    if status == EvidenceStatus.CONTESTED:
        return CONTESTED

    is_in = label == ArgLabel.IN
    is_out = label == ArgLabel.OUT

    if status == EvidenceStatus.WELL_SUPPORTED:
        if is_in:
            return PRIMARY_CANDIDATE
        if is_out:
            return WELL_SUPPORTED_BUT_DEFEATED
        return WELL_SUPPORTED_BUT_UNRESOLVED
    if status == EvidenceStatus.WEAKLY_SUPPORTED:
        if is_in:
            return TENTATIVE_CANDIDATE
        if is_out:
            return WEAK_AND_DEFEATED
        return WEAKLY_SUPPORTED_BUT_UNRESOLVED
    if status == EvidenceStatus.MISSING:
        if is_in:
            return STRUCTURALLY_ACCEPTABLE_BUT_UNSUPPORTED
        if is_out:
            return UNSUPPORTED_AND_DEFEATED
        return UNSUPPORTED_AND_UNRESOLVED
    return UNSUPPORTED_AND_UNRESOLVED


def _final_bucket(handling: str) -> str:
    return _BUCKET.get(handling, "unresolved")


def _surfaced_claim_ranks(raw_cbe: dict) -> List[tuple]:
    """Claims surfaced by raw CBE, in rank order, as ``(claim_id, rank)``.

    Reads ``ranked_claims`` first (the full ranking), then any extra
    ``strongest_claims``. Does not modify raw_cbe.
    """
    out: List[tuple] = []
    seen = set()
    for entry in raw_cbe.get("ranked_claims", []) or []:
        cid = entry.get("claim_id") if isinstance(entry, dict) else None
        if cid and cid not in seen:
            seen.add(cid)
            out.append((cid, entry.get("rank")))
    for entry in raw_cbe.get("strongest_claims", []) or []:
        cid = entry.get("claim_id") if isinstance(entry, dict) else None
        if cid and cid not in seen:
            seen.add(cid)
            rank = (entry.get("cbe_ranking") or {}).get("rank") if isinstance(entry, dict) else None
            out.append((cid, rank))
    return out


@dataclass
class IntegratedClaimView:
    claim_id: str
    text: str
    raw_cbe_rank: Optional[int]
    evidence_status: str
    evidence_balance: Dict
    argumentation_label: str
    final_bucket: str
    final_handling: str

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "raw_cbe_rank": self.raw_cbe_rank,
            "evidence_status": self.evidence_status,
            "evidence_balance": self.evidence_balance,
            "argumentation_label": self.argumentation_label,
            "final_bucket": self.final_bucket,
            "final_handling": self.final_handling,
        }


@dataclass
class CEDIntegrationReport:
    raw_cbe: dict
    claims: List[IntegratedClaimView]
    final_epistemic_answer: dict
    summary: dict
    note: str = _NOTE

    def to_dict(self) -> dict:
        return {
            "raw_cbe": self.raw_cbe,
            "claims": [c.to_dict() for c in self.claims],
            "final_epistemic_answer": self.final_epistemic_answer,
            "summary": self.summary,
            "note": self.note,
        }


def _build_summary(
    views: List[IntegratedClaimView], primary_cid: Optional[str], graph: EpistemicGraph
) -> dict:
    has_clean = primary_cid is not None
    return {
        "has_clean_primary": has_clean,
        "primary_claim_id": primary_cid,
        "primary_text": graph.claims[primary_cid].text if has_clean else None,
        "no_clean_answer": None if has_clean else NO_CLEAN_ANSWER,
        "counts_by_handling": dict(sorted(Counter(v.final_handling for v in views).items())),
        "counts_by_evidence_status": dict(sorted(Counter(v.evidence_status for v in views).items())),
        "counts_by_argumentation_label": dict(sorted(Counter(v.argumentation_label for v in views).items())),
        "surfaced_claim_count": len(views),
    }


def build_integration_report(raw_cbe: dict, graph: EpistemicGraph) -> CEDIntegrationReport:
    """Build the read-only integration report from raw CBE + the graph.

    Pure and non-mutating: it reads the graph and raw_cbe, calls the existing
    evidence / argumentation / composer functions, and returns a new report. No
    claim state, graph, or raw_cbe content is modified.
    """
    labeling = label_graph(graph)
    final = compose_final_epistemic_answer(raw_cbe, graph.claims)

    views: List[IntegratedClaimView] = []
    primary_cid: Optional[str] = None
    for cid, rank in _surfaced_claim_ranks(raw_cbe):
        claim = graph.claims.get(cid)
        if claim is None:
            continue
        status = evidence_status(claim)
        balance = evidence_balance(claim).to_dict()
        label = labeling.labels.get(cid)
        handling = compute_final_handling(status, label)
        views.append(
            IntegratedClaimView(
                claim_id=cid,
                text=claim.text,
                raw_cbe_rank=rank,
                evidence_status=status.value,
                evidence_balance=balance,
                argumentation_label=label.value if label is not None else "UNLABELED",
                final_bucket=_final_bucket(handling),
                final_handling=handling,
            )
        )
        if handling == PRIMARY_CANDIDATE and primary_cid is None:
            primary_cid = cid

    summary = _build_summary(views, primary_cid, graph)
    return CEDIntegrationReport(
        raw_cbe=raw_cbe,
        claims=views,
        final_epistemic_answer=final.to_dict(),
        summary=summary,
        note=_NOTE,
    )
