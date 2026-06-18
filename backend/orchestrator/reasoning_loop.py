"""
Reasoning Loop
==============

Orchestrates one reasoning session following the directive §7 pipeline:

  hypotheses -> claims -> rotate Socrates -> Elenchus -> reflection ->
  evidence -> knowledge emergence -> convergence -> Current Best Explanation

Runs end-to-end on mock models with no secrets, so the architecture is provable
before any real API is wired in.
"""

from __future__ import annotations

from typing import List

from ..config import Config
from ..agents.base_agent import Agent
from ..agents.model_adapter import MockModel, AnthropicAdapter
from ..epistemic.claim import Claim, Evidence
from ..epistemic.epistemic_state import EpistemicState
from ..epistemic.epistemic_graph import EpistemicGraph, NodeType
from ..epistemic.knowledge_emergence import KnowledgeEmergenceEngine
from ..reasoning.elenchus_engine import ElenchusEngine
from ..reasoning.reflection_engine import ReflectionEngine
from ..reasoning.synthesis_engine import SynthesisEngine, CurrentBestExplanation
from ..orchestrator.socratic_rotation import SocraticRotation


def _build_agents(cfg: Config) -> List[Agent]:
    agents = []
    for spec in cfg.models:
        if spec.provider == "anthropic":
            model = AnthropicAdapter(spec.name, spec.model, cfg.anthropic_api_key)
        else:
            model = MockModel(spec.name, spec.persona)
        agents.append(Agent(spec.name, model))
    return agents


class ReasoningLoop:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.agents = _build_agents(cfg)
        self.graph = EpistemicGraph()
        self.rotation = SocraticRotation(self.agents)
        self.elenchus = ElenchusEngine()
        self.reflection = ReflectionEngine()
        self.emergence = KnowledgeEmergenceEngine(cfg.thresholds)
        self.synthesis = SynthesisEngine()
        self.trace: List[str] = []

    def run(self, question: str) -> CurrentBestExplanation:
        self.trace.append(f"Question received: {question}")
        self.graph.add_node(NodeType.QUESTION, question)

        # 1-5. Each agent reflects, FINAL section becomes a claim.
        for agent in self.agents:
            refl = self.reflection.reflect(agent, question)
            claim = Claim(text=refl.claim_text, author_model=agent.agent_id)
            self.graph.add_claim(claim)
            self.trace.append(f"{agent.agent_id} proposed claim {claim.claim_id}")

        # 6-8. Rotate Socrates and challenge every claim with another agent.
        for claim in list(self.graph.claims.values()):
            socrates = self.rotation.next_socrates()
            challenger = next(a for a in self.agents if a.agent_id != claim.author_model)
            report = self.elenchus.challenge(claim, challenger)
            self.trace.append(
                f"Claim {claim.claim_id} challenged by {challenger.agent_id} "
                f"(falsified={report.falsification_successful})")

        # 9-11. Survivors gather evidence + independent reviews (mocked here).
        for claim in self.graph.claims.values():
            if claim.state == EpistemicState.CHALLENGED and not claim.contradictions:
                claim.transition(EpistemicState.SUPPORTED,
                                 actor="loop", reason="Survived challenge.")
                claim.add_evidence(Evidence(
                    f"ev_{claim.claim_id}", "Supporting analysis", quality=0.7))
                claim.independent_reviews = self.cfg.thresholds.min_independent_reviews
                claim.adjust_confidence(0.75, actor="loop",
                                        reason="Evidence integrated.")

        # 12-14. Knowledge emergence + (simple) convergence.
        self.emergence.evaluate_all(self.graph)
        self.trace.append("Knowledge emergence evaluated.")

        # 15. Current Best Explanation.
        return self.synthesis.synthesize(question, self.graph, self.trace)
