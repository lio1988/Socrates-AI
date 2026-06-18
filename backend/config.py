"""Central configuration for Socrates AI."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class ModelSpec:
    name: str
    provider: str          # "mock" | "anthropic" | "openai" | ...
    model: str = ""
    persona: str = "neutral"


@dataclass
class EmergenceThresholds:
    evidence_quality: float = 0.6
    logical_consistency: float = 0.6
    confidence: float = 0.7
    min_independent_reviews: int = 2


@dataclass
class Config:
    # Use mocks by default so the system runs with zero secrets / zero cost.
    models: List[ModelSpec] = field(default_factory=lambda: [
        ModelSpec("alpha", "mock", persona="builder"),
        ModelSpec("beta", "mock", persona="skeptic"),
        ModelSpec("gamma", "mock", persona="synthesizer"),
    ])
    thresholds: EmergenceThresholds = field(default_factory=EmergenceThresholds)
    max_rounds: int = 6
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    @property
    def num_agents(self) -> int:
        return len(self.models)


DEFAULT_CONFIG = Config()
