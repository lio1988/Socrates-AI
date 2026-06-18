"""Convergence / consensus-stability check (Rule 11). Extracted from main.py."""

from __future__ import annotations

from typing import List, Tuple

from backend.storage.models import ConsensusMemoryData, ElenchusResult


def compute_convergence(
    consensus: ConsensusMemoryData,
    elenchus_history: List[ElenchusResult],
    prev_conclusion_count: int,
) -> Tuple[float, bool]:
    """
    Rule 11: Consensus stability check.
    Returns (convergence_score 0.0–1.0, is_stable).
    Stable when: no new conclusions added AND no Elenchus falsification in last 2 rounds.
    """
    conclusion_count = len(consensus.verified_conclusions)
    open_count       = len(consensus.open_questions)
    disagreement_count = len(consensus.remaining_disagreements)

    # No new conclusions added
    stable_conclusions = (conclusion_count == prev_conclusion_count and conclusion_count > 0)

    # Recent Elenchus results: none falsified in last 2
    recent_elenchus = elenchus_history[-2:] if len(elenchus_history) >= 2 else elenchus_history
    recent_falsifications = sum(1 for e in recent_elenchus if e.falsification_successful)
    stable_elenchus = (recent_falsifications == 0)

    # Open questions shrinking
    open_ratio = 1.0 - (open_count / max(conclusion_count + open_count, 1))

    score = (
        (0.40 * float(stable_conclusions)) +
        (0.40 * float(stable_elenchus)) +
        (0.20 * open_ratio)
    )

    # Stable when score > 0.8 AND at least 1 verified conclusion
    is_stable = (score >= 0.8 and conclusion_count >= 1 and disagreement_count == 0)

    return round(score, 3), is_stable
