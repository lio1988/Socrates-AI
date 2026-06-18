"""Runtime enforcement of the Engineering Constitution v0.1 (15 rules).

Extracted from main.py. Each forbidden action raises ConstitutionViolationError.
This is the operational guard; backend/constitution.py holds the higher-level
CED principle invariants.
"""

from __future__ import annotations

from typing import Optional, List, Dict

from backend.storage.models import (
    Claim, KnowledgeConcept, SynthesisResult, ComplexityAssessment,
    ElenchusResult, ReflectionStep, DialogTurnResponse,
)


class ConstitutionViolationError(Exception):
    """Raised when an Engineering Constitution rule is violated"""
    def __init__(self, rule: int, description: str):
        self.rule = rule
        self.description = description
        super().__init__(f"[Constitution Rule {rule}] {description}")


class ConstitutionGuard:
    """
    Enforces the Engineering Constitution v0.1.
    Every forbidden action raises ConstitutionViolationError.
    """

    @staticmethod
    def assert_socratic_rotation(
        model_id: str,
        previous_socrates: Optional[str],
        rounds_as_socrates: Dict[str, int],
        total_rounds: int,
    ) -> None:
        """Rule 1: No agent permanently acts as Socrates"""
        if previous_socrates and model_id == previous_socrates:
            # Check if this agent has been Socrates > 60% of rounds
            count = rounds_as_socrates.get(model_id, 0)
            if count > total_rounds * 0.6:
                raise ConstitutionViolationError(
                    1,
                    f"{model_id} has been Socrates in {count}/{total_rounds} rounds "
                    f"(>{60}%). Authority must rotate."
                )

    @staticmethod
    def assert_socratic_phase_present(history: List[DialogTurnResponse]) -> None:
        """Rule 2: Every discussion must contain a Socratic phase"""
        has_socratic = any(t.is_socratic for t in history)
        if history and not has_socratic:
            raise ConstitutionViolationError(
                2,
                "No Socratic phase found in dialogue history. "
                "Every discussion MUST contain a Socratic phase."
            )

    @staticmethod
    def assert_elenchus_after_claim(
        elenchus_history: List[ElenchusResult],
        rounds_completed: int,
    ) -> None:
        """Rule 3: Every answer must be challenged via Elenchus"""
        if rounds_completed > 0 and not elenchus_history:
            raise ConstitutionViolationError(
                3,
                f"No Elenchus performed after {rounds_completed} rounds. "
                "Every proposed answer MUST be challenged."
            )

    @staticmethod
    def assert_reflection_performed(
        reflection_history: List[ReflectionStep],
        model_id: str,
        round_num: int,
    ) -> None:
        """Rule 5: Every agent must reflect before final submission"""
        performed = any(
            r.model_id == model_id and r.round == round_num
            for r in reflection_history
        )
        if not performed:
            raise ConstitutionViolationError(
                5,
                f"{model_id} submitted in round {round_num} without a Reflection step. "
                "Every agent MUST review its own reasoning before submission."
            )

    @staticmethod
    def assert_claim_has_provenance(claim: Claim) -> None:
        """Rule 6: Every factual claim must carry Evidence + Confidence + Source + Status"""
        if not claim.source:
            raise ConstitutionViolationError(6, "Claim missing 'source'.")
        if claim.confidence == 0.5 and not claim.evidence:
            raise ConstitutionViolationError(
                6, f"Claim '{claim.text[:60]}...' has no evidence and default confidence."
            )

    @staticmethod
    def assert_knowledge_graph_validated_only(concept: KnowledgeConcept) -> None:
        """Rule 8: Only validated knowledge enters long-term memory"""
        if not concept.validated:
            raise ConstitutionViolationError(
                8,
                f"Concept '{concept.label}' is not validated. "
                "The Knowledge Graph MUST NOT store unvalidated concepts."
            )
        if concept.is_opinion:
            raise ConstitutionViolationError(
                8, f"Concept '{concept.label}' is an opinion. Opinions MUST NOT enter the Knowledge Graph."
            )
        if concept.is_hallucination_risk:
            raise ConstitutionViolationError(
                8, f"Concept '{concept.label}' is flagged as hallucination risk."
            )

    @staticmethod
    def assert_consensus_not_single_model(
        models_agreed: List[str],
        available_models: List[str],
    ) -> None:
        """Rule 3+9: Consensus cannot be decided by a single model"""
        if len(models_agreed) == 1 and len(available_models) > 1:
            raise ConstitutionViolationError(
                3,
                f"Consensus declared by single model '{models_agreed[0]}'. "
                "Consensus MUST NOT replace structured Elenchus."
            )

    @staticmethod
    def assert_synthesis_no_new_facts(
        synthesis_text: str,
        claim_texts: List[str],
    ) -> List[str]:
        """
        Rule 6+: Synthesis must not add new facts.
        Returns list of suspected new facts (heuristic — LLM should enforce strictly).
        """
        warnings: List[str] = []
        # Heuristic: flag sentences with factual patterns not in claims
        import re
        sentences = re.split(r'[.!?]', synthesis_text)
        factual_patterns = [r'\d{4}', r'\b\d+%', r'\baccording to\b', r'\bproved\b', r'\bshowed that\b']
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            for pattern in factual_patterns:
                if re.search(pattern, sent, re.IGNORECASE):
                    matched = any(
                        sent.lower()[:40] in c.lower() for c in claim_texts
                    )
                    if not matched:
                        warnings.append(sent[:100])
                        break
        return warnings

    @staticmethod
    def assert_disagreements_exposed(synthesis: SynthesisResult) -> None:
        """Rule 13: Never hide disagreement"""
        if synthesis.hidden_disagreements:
            raise ConstitutionViolationError(
                13,
                f"Synthesis attempted to hide {len(synthesis.hidden_disagreements)} disagreement(s). "
                "Disagreements MUST always be exposed."
            )

    @staticmethod
    def assert_minimum_rounds(
        requested_rounds: int,
        complexity: ComplexityAssessment,
    ) -> int:
        """
        Rule 10: Complexity drives minimum rounds.
        Returns the enforced round count (may be higher than requested).
        """
        if requested_rounds < complexity.recommended_rounds:
            return complexity.recommended_rounds
        return requested_rounds
