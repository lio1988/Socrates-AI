"""
Lightweight, deterministic topic classifier (V1).

Used by the FakeProvider to produce domain-relevant scripted output. This is a
keyword heuristic only — no model, no network. It is intentionally simple and
fully deterministic so the rest of the pipeline stays reproducible.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Tuple


class Topic(str, Enum):
    COSMOLOGY              = "cosmology"
    EPISTEMOLOGY           = "epistemology"
    MATHEMATICS_PHILOSOPHY = "mathematics_philosophy"
    LAW                    = "law"
    MEDICINE               = "medicine"
    TECHNOLOGY             = "technology"
    BUSINESS               = "business"
    GENERAL                = "general"


# Keyword tables (lower-cased substring match). Multi-word phrases are weighted
# more heavily than single common words so specific topics win over generic hits.
_KEYWORDS: Dict[Topic, List[str]] = {
    Topic.EPISTEMOLOGY: [
        "justified true belief", "gettier", "jtb", "epistemology", "epistemic",
        "defeater", "reliabilism", "reliabilist", "virtue epistemology",
        "internalism", "externalism", "skepticism", "scepticism",
        "knowledge", "justification", "justified", "belief", "truth",
        "anti-luck", "no false lemmas",
    ],
    Topic.MATHEMATICS_PHILOSOPHY: [
        "mathematics discovered", "discovered or invented", "platonism",
        "formalism", "intuitionism", "mathematical objects", "mathematical truth",
        "philosophy of mathematics", "is mathematics",
    ],
    Topic.COSMOLOGY: [
        "universe", "cosmos", "big bang", "multiverse", "cosmological",
        "fine-tuning", "origin of the universe", "spacetime",
    ],
    Topic.LAW: [
        "law", "legal", "court", "statute", "constitutional", "liability",
        "contract", "jurisdiction", "precedent",
    ],
    Topic.MEDICINE: [
        "patient", "diagnosis", "treatment", "clinical", "disease", "symptom",
        "therapy", "medical", "drug",
    ],
    Topic.TECHNOLOGY: [
        "software", "algorithm", "machine learning", "artificial intelligence",
        "computer", "neural network", "encryption", "data structure",
    ],
    Topic.BUSINESS: [
        "market", "revenue", "profit", "customer", "startup", "strategy",
        "pricing", "competitor", "business model",
    ],
}

# Phrases of two or more words count more than single broad words.
def _weight(keyword: str) -> int:
    return 2 if " " in keyword or "-" in keyword else 1

# Priority order used only to break exact score ties (more specific first).
_PRIORITY: List[Topic] = [
    Topic.EPISTEMOLOGY,
    Topic.MATHEMATICS_PHILOSOPHY,
    Topic.COSMOLOGY,
    Topic.MEDICINE,
    Topic.LAW,
    Topic.TECHNOLOGY,
    Topic.BUSINESS,
]


def classify_topic(question: str) -> Topic:
    """Return the best-matching Topic for a question (GENERAL if no keywords hit)."""
    text = (question or "").lower()

    scores: Dict[Topic, int] = {}
    for topic, keywords in _KEYWORDS.items():
        score = sum(_weight(k) for k in keywords if k in text)
        if score:
            scores[topic] = score

    if not scores:
        return Topic.GENERAL

    best = max(scores.values())
    # Tie-break by priority order.
    for topic in _PRIORITY:
        if scores.get(topic, 0) == best:
            return topic
    # Fallback (shouldn't happen): first by score.
    return max(scores, key=scores.get)
