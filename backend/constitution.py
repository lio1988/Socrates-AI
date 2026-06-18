"""
Constitution
============

The directive's five non-negotiable principles, expressed as code-checkable
invariants. The orchestrator runs `audit()` over a session's graph + rotation
history; any violation is surfaced (not hidden). This is what the
`GET /constitution` endpoint exposes and what Meta-Socrates leans on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .epistemic.epistemic_graph import EpistemicGraph
from .epistemic.epistemic_state import EpistemicState


PRINCIPLES = [
    ("no_permanent_authority",
     "No model may permanently act as leader, judge, or final authority. "
     "The Socratic role must rotate."),
    ("evidence_over_agreement",
     "Agreement is not truth. A weakly-evidenced majority claim must not "
     "become knowledge; a strongly-evidenced minority must stay visible."),
    ("disagreement_is_productive",
     "Disagreement must not be hidden; it should generate new questions."),
    ("every_answer_is_temporary",
     "The final output is a Current Best Explanation, never final truth."),
    ("knowledge_is_reversible",
     "A claim promoted to knowledge can later be disputed, revised or obsolete."),
]


@dataclass
class Violation:
    principle: str
    detail: str


def audit(graph: EpistemicGraph, socrates_history: List[str],
          num_agents: int) -> List[Violation]:
    violations: List[Violation] = []

    # Principle 1 — rotation actually happened if more than one round ran.
    if len(socrates_history) >= num_agents and len(set(socrates_history)) <= 1:
        violations.append(Violation(
            "no_permanent_authority",
            "One agent held the Socratic role for every round.",
        ))

    # Principle 2 — no claim reached KNOWLEDGE without surviving challenge.
    for claim in graph.claims.values():
        if claim.state == EpistemicState.KNOWLEDGE and not claim.has_been_challenged:
            violations.append(Violation(
                "evidence_over_agreement",
                f"Claim {claim.claim_id} is KNOWLEDGE but was never challenged.",
            ))

    return violations


def constitution_document() -> dict:
    return {
        "principles": [{"id": pid, "text": text} for pid, text in PRINCIPLES],
        "final_output_name": "Current Best Explanation",
    }
