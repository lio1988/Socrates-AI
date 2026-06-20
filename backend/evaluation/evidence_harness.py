"""Evidence Layer v0.1 harness -- local, deterministic, no live calls.

Runs the sibling evidence benchmark (schema ``ced_evidence_eval_v0.1``) through
the REAL CBE pipeline plus the evidence audit + the evidence-constrained
composer, and reports per-case results.

It uses a :class:`ScriptedModel` stand-in (never calls a live model) and does
NOT change knowledge promotion or the raw CBE. Kept fully separate from the
existing v0.1 evaluation harness.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List

from socrates_ai import DialogConfig, DialogMode, DialogSpeed, SummaryMode
from backend.orchestrator.session import EnhancedDialogSession
from backend.orchestrator.live_epistemics import (
    ensure_live_epistemics,
    produce_current_best_explanation,
)
from backend.epistemic.claim import Claim
from backend.epistemic.epistemic_state import EpistemicState
from backend.epistemic.evidence_scoring import evidence_status
from backend.epistemic.evidence_fixtures import evidence_from_fixture, attach_evidence
from backend.reasoning.evidence_constrained_cbe import compose_final_epistemic_answer
from backend.evaluation.scripted_model import ScriptedModel
from backend.evaluation import evidence_metrics as EM

EVIDENCE_SCHEMA_VERSION = "ced_evidence_eval_v0.1"
EVIDENCE_HARNESS_VERSION = "ced_evidence_harness_v0.1"
_DATA = os.path.join(os.path.dirname(__file__), "data", "ced_evidence_benchmark_v0.json")

_DISCLAIMER = (
    "Evidence Layer v0.1 (scripted fixtures). Evidence statuses and the "
    "evidence-constrained final answer are deterministic regression signals "
    "over fixtures, not truth guarantees. This layer does not alter knowledge "
    "promotion or raw CBE ranking/confidence."
)


@dataclass
class EvidenceCase:
    id: str
    question: str
    claim_text: str
    evidence_fixtures: List[Dict]
    gold: Dict
    confidence: float = 0.8
    challenged: bool = True
    independent_reviews: int = 3

    @staticmethod
    def from_dict(d: Dict) -> "EvidenceCase":
        return EvidenceCase(
            id=d["id"],
            question=d["question"],
            claim_text=d["claim_text"],
            evidence_fixtures=d.get("evidence_fixtures", []),
            gold=d.get("gold", {}),
            confidence=float(d.get("confidence", 0.8)),
            challenged=bool(d.get("challenged", True)),
            independent_reviews=int(d.get("independent_reviews", 3)),
        )


def load_evidence_benchmark(path: str = _DATA) -> List[EvidenceCase]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    sv = data.get("schema_version")
    if sv != EVIDENCE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported evidence benchmark schema_version {sv!r}; "
            f"expected {EVIDENCE_SCHEMA_VERSION!r}."
        )
    return [EvidenceCase.from_dict(c) for c in data.get("cases", [])]


def _build_session(case: EvidenceCase):
    cfg = DialogConfig(
        topic=case.question,
        rounds=2,
        mode=DialogMode.SOCRATIC,
        speed=DialogSpeed.NORMAL,
        summary_mode=SummaryMode.NONE,
    )
    session = EnhancedDialogSession(
        f"evid_{case.id}", cfg, {"claude": "x", "chatgpt": "y"}
    )
    # Non-live stand-in; never called (the engine is driven directly).
    session.manager = ScriptedModel({case.question: case.claim_text})
    session.enforced_rounds = 2
    ensure_live_epistemics(session)
    return session


def run_evidence_case(case: EvidenceCase) -> "EM.EvidenceCaseResult":
    session = _build_session(case)
    graph = session.epistemic_graph

    # Build the claim DIRECTLY (not via the live recorder) so the ONLY evidence
    # on it comes from the case fixtures. The live recorder seeds a low-quality
    # self-evidence per claim (a scoring artifact of the live pipeline), which
    # would make a "no external evidence" case look WEAKLY_SUPPORTED instead of
    # MISSING. Building directly isolates external evidence as the single
    # variable under test and leaves the live pipeline untouched. A
    # directly-added claim still surfaces in the raw CBE strongest_claims.
    claim = Claim(text=case.claim_text, author_model="claude")
    graph.add_claim(claim)
    claim_id = claim.claim_id

    # Isolate evidence as the *presentation* variable: make the claim a solid,
    # active, reviewed claim so it surfaces in the raw CBE. (This is about raw
    # CBE visibility, NOT evidence-driven promotion.)
    claim.adjust_confidence(case.confidence, actor="evidence_harness", reason="fixture setup")
    claim.independent_reviews = case.independent_reviews
    if case.challenged:
        claim.transition(EpistemicState.CHALLENGED, actor="evidence_harness", reason="scripted challenge")
        claim.transition(EpistemicState.SUPPORTED, actor="evidence_harness", reason="survived")

    for i, fx in enumerate(case.evidence_fixtures):
        attach_evidence(graph, claim_id, evidence_from_fixture(fx, index=i))

    status = evidence_status(claim)
    raw_cbe = produce_current_best_explanation(session).to_dict()
    final = compose_final_epistemic_answer(raw_cbe, graph.claims)

    return EM.score_evidence_case(case, claim, status, raw_cbe, final)


@dataclass
class EvidenceRunReport:
    schema_version: str
    harness: str
    case_count: int
    cases: List[Dict]
    aggregate: Dict
    disclaimer: str

    def to_dict(self) -> Dict:
        return {
            "schema_version": self.schema_version,
            "harness": self.harness,
            "case_count": self.case_count,
            "cases": self.cases,
            "aggregate": self.aggregate,
            "disclaimer": self.disclaimer,
        }


def run_evidence_benchmark(path: str = _DATA) -> EvidenceRunReport:
    cases = load_evidence_benchmark(path)
    results = [run_evidence_case(c) for c in cases]
    return EvidenceRunReport(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        harness=EVIDENCE_HARNESS_VERSION,
        case_count=len(results),
        cases=[r.to_dict() for r in results],
        aggregate=EM.aggregate(results),
        disclaimer=_DISCLAIMER,
    )
