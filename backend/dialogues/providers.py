"""
LLM Provider Interface + FakeProvider (V1)

Architecture reserves four provider slots (fake, anthropic, openai, local).
Only FakeProvider is implemented in V1. Real providers are drop-in replacements
that implement the same interface — the CED and agents never know the difference.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .models import AgentRole


class LLMProvider(ABC):
    """
    Provider-agnostic interface.  All session state lives in the CED,
    not in any provider instance.
    """

    provider_id: str

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Dict[str, Any],
        agent_id: str = "",
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Return a structured dict whose keys match output_schema.
        Must never raise on valid inputs; return a best-effort dict on failure.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Return True iff the provider can accept requests right now."""
        ...


# ── Four provider slots (V1: only FakeProvider populated) ─────────────────────

class FakeProvider(LLMProvider):
    """
    Deterministic fake provider.  Same inputs → same outputs every time.
    No network calls, no cost.  Exists solely to let the orchestration
    machinery be built and tested before any real API is wired in.
    """

    provider_id: str = "fake"

    # ── Role-keyed response templates ────────────────────────────────────────

    _TEMPLATES: Dict[str, Dict[str, Any]] = {
        AgentRole.SOCRATES.value: {
            "question": "What underlying assumption are we taking for granted here?",
            "exposed_assumption": "That the premise is universally applicable regardless of context.",
            "epistemic_marker": "open_uncertainty",
        },
        AgentRole.ELENCHUS_CRITIC.value: {
            "contradictions": ["The scope claim is inconsistent with the evidence cited."],
            "weak_assumptions": ["Assumes correlation implies causation without justification."],
            "logic_gaps": ["The causal mechanism is asserted but not demonstrated."],
            "critique_summary": "The core claim requires stronger empirical grounding before it can be accepted.",
            "confidence": 0.72,
        },
        AgentRole.EMPIRICIST.value: {
            "factual_claims": [
                {
                    "claim": "The central assertion of the argument",
                    "status": "unverified",
                    "notes": "Requires peer-reviewed empirical support.",
                }
            ],
            "evidence_quality": 0.55,
            "documentation_gaps": [
                "No primary source cited for the main causal claim.",
                "Effect size and sample characteristics absent.",
            ],
        },
        AgentRole.MAIEUTIC_RECONSTRUCTOR.value: {
            "stronger_position": (
                "A refined version of the position that narrows scope to well-evidenced cases, "
                "explicitly qualifies the causal claim, and acknowledges known counter-evidence."
            ),
            "integrated_critiques": [
                "Scope narrowed to domains with direct empirical support.",
                "Causal language replaced with correlation-qualified language.",
            ],
            "remaining_weaknesses": [
                "Edge cases and domain-transfer applicability remain unaddressed.",
            ],
            "confidence": 0.68,
        },
        AgentRole.SYNTHESIZER.value: {
            "synthesis_draft": (
                "Based on the council's deliberation, the most defensible position is a "
                "qualified version of the original claim, limited to contexts with direct "
                "empirical support. The causal mechanism requires further investigation."
            ),
            "key_insights": [
                "Scope matters: domain-specific evidence is more reliable than general claims.",
                "Evidence quality is decisive: weak evidence does not license strong conclusions.",
            ],
            "unresolved_tensions": [
                "Cross-domain applicability remains contested among council members.",
            ],
            "confidence": 0.74,
        },
        AgentRole.REFLECTOR.value: {
            "original_position_id": "",
            "revised_position": (
                "A more cautious, evidence-constrained version of the original position "
                "that acknowledges the valid inferential gaps identified by the Elenchus Critic."
            ),
            "reason_for_revision": (
                "The Elenchus Critic identified a valid gap between the correlation evidence "
                "and the causal conclusion I drew. The revision restricts the claim accordingly."
            ),
            "confidence_change": -0.1,
        },
        AgentRole.FINAL_EVALUATOR.value: {
            "assessment": "approved",
            "blocking_objections": [],
            "epistemic_status": "uncertain",
            "evaluation_summary": (
                "The draft satisfies the epistemic discipline requirements after the "
                "reflection and reconstruction phases. Uncertainty is correctly marked."
            ),
        },
    }

    # The seven scoring dimensions (0–10 scale).
    _DIMENSIONS = [
        "epistemic_value", "logical_rigor", "factual_grounding",
        "constructive_impact", "intellectual_honesty", "clarity_precision",
        "grounded_creativity",
    ]

    # ── Deterministic variation helpers ──────────────────────────────────────

    def _seed(self, *parts: str) -> int:
        joined = "|".join(parts)
        return int(hashlib.sha256(joined.encode()).hexdigest(), 16)

    def _vary(self, base: float, seed: int, spread: float = 0.12) -> float:
        """Deterministic delta on the 0–1 scale (used for confidence etc.)."""
        delta = ((seed % 1000) / 1000.0 - 0.5) * spread * 2
        return round(max(0.0, min(1.0, base + delta)), 4)

    def _vary10(self, base: float, seed: int, spread: float = 1.5) -> float:
        """Deterministic delta on the 0–10 scale (used for score dimensions)."""
        delta = ((seed % 1000) / 1000.0 - 0.5) * spread * 2
        return round(max(0.0, min(10.0, base + delta)), 2)

    def _breakdown(self, seed: int, base: float = 7.0) -> Dict[str, float]:
        """Deterministic 7-dimension score breakdown on the 0–10 scale."""
        bd: Dict[str, float] = {}
        s = seed
        for dim in self._DIMENSIONS:
            s = self._seed(str(s), dim)
            bd[dim] = self._vary10(base, s)
        return bd

    def _score_payload(self, seed: int, base: float = 7.0) -> Dict[str, Any]:
        """A full multi-dimensional score response (move- or section-level)."""
        return {
            "score_breakdown": self._breakdown(seed, base),
            "confidence": self._vary(0.78, seed, spread=0.12),   # 0–1 scale
            "justification": (
                "Scored on epistemic value, logical rigor, factual grounding, "
                "constructive impact, honesty, clarity and grounded creativity."
            ),
            "penalty_flags": [],
            "provider_status": "ok",
        }

    def _synth_sections(self, question: str, seed: int) -> Dict[str, str]:
        """Topic-aware 5-section synthesizer draft (scripted, references the question)."""
        q = question.strip() or "the question"
        return {
            "core_answer": (
                f"On «{q}», the council's most defensible position is a qualified one: "
                f"the claim holds in contexts with direct supporting evidence, but its "
                f"scope must be narrowed rather than asserted universally."
            ),
            "crucial_stress_test": (
                f"The strongest challenge to any answer on «{q}» is the gap between "
                f"correlation and causation: the evidence cited supports association, "
                f"not the stronger causal reading the question invites."
            ),
            "blind_spots": (
                f"This treatment of «{q}» risks overlooking domain-transfer limits and "
                f"selection effects in the underlying studies, which could inflate "
                f"apparent support."
            ),
            "nuance": (
                f"The answer to «{q}» shifts with context: it is stronger for "
                f"well-studied cases and weaker where data is sparse or contested."
            ),
            "final_verdict": (
                f"Provisional verdict on «{q}»: a scope-limited 'yes, with conditions', "
                f"held with calibrated uncertainty pending stronger causal evidence."
            ),
        }

    def _ratification_vote(self, agent_id: str, hint: str) -> Dict[str, Any]:
        """Default Final Evaluator verdict: approve (no blocking objection)."""
        return {
            "voter_agent_id": agent_id,
            "decision": "approve",
            "severity": "none",
            "target_section": None,
            "reason": (
                "The assembled five-section answer meets the epistemic-discipline "
                "bar; uncertainty is marked and no section is unsupported."
            ),
            "epistemic_status": hint or "uncertain",
        }

    # ── Public interface ──────────────────────────────────────────────────────

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Dict[str, Any],
        agent_id: str = "",
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        role_key = output_schema.get("_role", "")
        question = output_schema.get("_question", "")
        target = str(output_schema.get("_target", ""))
        section = str(output_schema.get("_section", ""))

        # ── Move-level shadow scoring ────────────────────────────────────────
        if role_key == "__move_score__":
            seed = self._seed(agent_id, role_key, target)
            return self._score_payload(seed)

        # ── Section-level draft scoring (varies per draft × section) ─────────
        if role_key == "__section_score__":
            seed = self._seed(agent_id, role_key, target, section)
            return self._score_payload(seed)

        seed = self._seed(agent_id, role_key, user_prompt[:80])

        # ── Synthesis phase: full 5-section draft ────────────────────────────
        if role_key == AgentRole.SYNTHESIZER.value and output_schema.get("_sections"):
            sections = self._synth_sections(question, seed)
            sections["confidence"] = self._vary(0.78, seed, spread=0.10)
            return sections

        # ── Final Evaluator: structured ratification vote ────────────────────
        if role_key == AgentRole.FINAL_EVALUATOR.value:
            return self._ratification_vote(agent_id, output_schema.get("_epistemic_hint", ""))

        # ── Role-keyed response path (Socrates, critics, reflector, etc.) ────
        template = self._TEMPLATES.get(role_key)
        if template is None:
            return {"content": f"[FakeProvider|{agent_id}] no template for role={role_key!r}"}

        result: Dict[str, Any] = json.loads(json.dumps(template))

        # Apply deterministic variation to numeric fields (0–1 scale)
        for field in ("confidence", "evidence_quality", "confidence_change"):
            if field in result and isinstance(result[field], (int, float)):
                result[field] = self._vary(float(result[field]), seed, spread=0.10)

        return result

    def health_check(self) -> bool:
        return True


# ── Three reserved-but-unimplemented providers ───────────────────────────────

class _UnimplementedProvider(LLMProvider):
    """Placeholder. Raises NotImplementedError on use."""

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

    def complete(self, system_prompt, user_prompt, output_schema,
                 agent_id="", temperature=0.7) -> Dict[str, Any]:
        raise NotImplementedError(
            f"Provider '{self.provider_id}' is not implemented in V1. "
            "Only FakeProvider is available."
        )

    def health_check(self) -> bool:
        return False


class AnthropicProvider(_UnimplementedProvider):
    provider_id: str = "anthropic"

    def __init__(self) -> None:
        super().__init__("anthropic")


class OpenAIProvider(_UnimplementedProvider):
    provider_id: str = "openai"

    def __init__(self) -> None:
        super().__init__("openai")


class LocalProvider(_UnimplementedProvider):
    provider_id: str = "local"

    def __init__(self) -> None:
        super().__init__("local")


# ── Provider registry ─────────────────────────────────────────────────────────

class ProviderRegistry:
    """
    Holds the four provider slots.
    V1: only 'fake' is wired.  The other three are reserved stubs.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, LLMProvider] = {
            "fake":      FakeProvider(),
            "anthropic": AnthropicProvider(),
            "openai":    OpenAIProvider(),
            "local":     LocalProvider(),
        }

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> Optional[LLMProvider]:
        return self._providers.get(provider_id)

    def get_or_raise(self, provider_id: str) -> LLMProvider:
        p = self.get(provider_id)
        if p is None:
            raise KeyError(
                f"Provider '{provider_id}' not registered. "
                f"Available: {list(self._providers)}"
            )
        return p
