"""Routing: domain classification, synthesis-model selection (Rule 12) and
adaptive complexity assessment (Rule 10). Extracted from main.py."""

from __future__ import annotations

from typing import Dict, List, Tuple

from backend.storage.models import Domain, ComplexityLevel, ComplexityAssessment


_DOMAIN_KEYWORDS: Dict[Domain, List[str]] = {
    Domain.SOFTWARE:    ["code", "algorithm", "software", "programming", "api", "database", "system", "architecture"],
    Domain.MATHEMATICS: ["math", "proof", "theorem", "equation", "calculus", "probability", "statistics", "number"],
    Domain.CREATIVE:    ["story", "poem", "narrative", "art", "design", "creative", "imagination", "metaphor"],
    Domain.SCIENCE:     ["quantum", "physics", "chemistry", "biology", "experiment", "hypothesis", "empirical"],
    Domain.PHILOSOPHY:  ["consciousness", "existence", "reality", "truth", "knowledge", "ethics", "ontology", "epistemology", "free will", "soul"],
    Domain.LAW:         ["law", "legal", "rights", "justice", "constitution", "court", "regulation", "contract"],
    Domain.ETHICS:      ["moral", "ethical", "good", "evil", "virtue", "duty", "harm", "obligation", "AI ethics"],
}

# Rule 12: Best model per domain
_DOMAIN_MODEL_MAP: Dict[Domain, str] = {
    Domain.SOFTWARE:    "claude",
    Domain.MATHEMATICS: "chatgpt",
    Domain.CREATIVE:    "gemini",
    Domain.SCIENCE:     "gemini",
    Domain.PHILOSOPHY:  "claude",
    Domain.LAW:         "chatgpt",
    Domain.ETHICS:      "claude",
    Domain.GENERAL:     "",  # selected dynamically from highest-scoring model
}


def classify_domain(topic: str) -> Tuple[Domain, str]:
    """
    Rule 12: Classify topic domain to determine synthesis model.
    Returns (Domain, reasoning).
    """
    topic_lower = topic.lower()
    scores: Dict[Domain, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in topic_lower)

    best_domain = max(scores, key=scores.get)  # type: ignore
    best_score = scores[best_domain]

    if best_score == 0:
        return Domain.GENERAL, "No domain-specific keywords detected; general analysis selected."

    return best_domain, (
        f"Domain '{best_domain.value}' detected ({best_score} keyword matches). "
        f"Synthesis assigned to '{_DOMAIN_MODEL_MAP.get(best_domain, 'dynamic')}'."
    )


def select_synthesis_model(domain: Domain, available_models: List[str]) -> str:
    """
    Rule 12: Automatically select best model for synthesis.
    Falls back to first available if preferred model not connected.
    """
    preferred = _DOMAIN_MODEL_MAP.get(domain, "")
    if preferred and preferred in available_models:
        return preferred
    # Dynamic fallback for GENERAL domain
    return available_models[0] if available_models else "claude"


# ============================================================================
# SECTION 5: COMPLEXITY ASSESSOR (Rule 10)
# ============================================================================

_COMPLEXITY_SIGNALS = {
    "very_complex": [
        "consciousness", "quantum", "paradox", "turing", "gödel", "free will",
        "hard problem", "metaphysics", "ontology", "epistemology", "p vs np",
        "philosophy of mind",
    ],
    "complex": [
        "ethics", "justice", "moral", "artificial intelligence", "democracy",
        "religion", "god", "soul", "meaning", "truth", "reality", "infinity",
    ],
    "moderate": [
        "history", "economics", "psychology", "education", "society",
        "technology", "environment", "politics",
    ],
}


def assess_complexity(topic: str) -> ComplexityAssessment:
    """
    Rule 10: Determine reasoning depth from topic complexity.
    Simple → short reasoning. Very complex → full Socratic pipeline.
    """
    topic_lower = topic.lower()

    if any(kw in topic_lower for kw in _COMPLEXITY_SIGNALS["very_complex"]):
        level, score = ComplexityLevel.VERY_COMPLEX, 0.9
        min_rounds, refl_interval, cycles = 10, 2, 4
    elif any(kw in topic_lower for kw in _COMPLEXITY_SIGNALS["complex"]):
        level, score = ComplexityLevel.COMPLEX, 0.7
        min_rounds, refl_interval, cycles = 6, 3, 3
    elif any(kw in topic_lower for kw in _COMPLEXITY_SIGNALS["moderate"]):
        level, score = ComplexityLevel.MODERATE, 0.5
        min_rounds, refl_interval, cycles = 4, 4, 2
    else:
        level, score = ComplexityLevel.SIMPLE, 0.25
        min_rounds, refl_interval, cycles = 2, 0, 1

    domain, _ = classify_domain(topic)

    return ComplexityAssessment(
        level=level,
        score=score,
        recommended_rounds=min_rounds,
        recommended_reflection_interval=refl_interval,
        requires_fact_verification=(score >= 0.5),
        requires_elenchus=True,  # Rule 3: ALWAYS required
        estimated_socratic_cycles=cycles,
        domain=domain,
        reasoning=(
            f"Topic complexity assessed as '{level.value}' (score={score}). "
            f"Minimum {min_rounds} rounds recommended with Elenchus every round "
            f"and Reflection every {refl_interval} rounds."
        ),
    )
