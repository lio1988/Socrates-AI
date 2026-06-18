"""Proves: every claim gets challenged; weak-evidence majority is NOT promoted;
strong-evidence claim IS promoted."""

from backend.agents.base_agent import Agent
from backend.agents.model_adapter import MockModel
from backend.epistemic.claim import Claim, Evidence
from backend.epistemic.epistemic_state import EpistemicState
from backend.epistemic.knowledge_emergence import KnowledgeEmergenceEngine
from backend.reasoning.elenchus_engine import ElenchusEngine
from backend.config import EmergenceThresholds


def test_elenchus_marks_claim_challenged():
    c = Claim(text="Caffeine improves reaction time.", author_model="alpha")
    challenger = Agent("beta", MockModel("mB"))
    engine = ElenchusEngine()
    engine.challenge(c, challenger)
    assert c.has_been_challenged is True
    assert c.state == EpistemicState.CHALLENGED


def test_weak_evidence_majority_not_promoted():
    c = Claim(text="Popular but unsupported claim.", author_model="alpha")
    c.transition(EpistemicState.CHALLENGED, actor="e", reason="c")
    c.transition(EpistemicState.SUPPORTED, actor="e", reason="agree")
    # Everyone "agrees" but evidence is weak and reviews are zero.
    engine = KnowledgeEmergenceEngine(EmergenceThresholds())
    decision = engine.evaluate(c)
    assert decision.promoted is False
    assert c.state != EpistemicState.KNOWLEDGE


def test_strong_evidence_claim_promoted():
    c = Claim(text="Well-supported claim.", author_model="alpha", confidence=0.9)
    c.transition(EpistemicState.CHALLENGED, actor="e", reason="c")
    c.transition(EpistemicState.SUPPORTED, actor="e", reason="survived")
    c.add_evidence(Evidence("e1", "Peer-reviewed meta-analysis", quality=0.9))
    c.add_evidence(Evidence("e2", "Independent replication", quality=0.85))
    c.independent_reviews = 3
    engine = KnowledgeEmergenceEngine(EmergenceThresholds())
    decision = engine.evaluate(c)
    assert decision.promoted is True
    assert c.state == EpistemicState.KNOWLEDGE


def test_minority_strong_claim_stays_visible():
    # A lone claim with strong evidence remains active even without consensus.
    c = Claim(text="Minority but well-evidenced.", author_model="gamma", confidence=0.8)
    c.transition(EpistemicState.CHALLENGED, actor="e", reason="c")
    c.transition(EpistemicState.SUPPORTED, actor="e", reason="held")
    c.add_evidence(Evidence("e1", "Strong data", quality=0.8))
    c.independent_reviews = 2
    engine = KnowledgeEmergenceEngine(EmergenceThresholds())
    engine.evaluate(c)
    assert c.is_active is True
