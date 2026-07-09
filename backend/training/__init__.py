"""
Phase 22 — The Teacher Loop (self-distillation flywheel).

The insight of the mechanical-engineer-philosopher: we do not need to invent a
learning algorithm. The CED council is ALREADY a data generator with quality
labels — ratified dialogues, peer-scored moves, mechanically selected section
winners and runner-ups. That is exactly the corpus a student LLM needs:

    council teaches  → harvest SFT + preference data (from REAL scores)
                     → LoRA fine-tune a small open model locally (NVIDIA GPU)
                     → the student re-enters as a council seat
                     → measured by the external-truth instruments (R1/R3a)
                     → the flywheel turns, cheaper and better each cycle.

Everything here is OFFLINE and dependency-guarded: the harvester is pure Python;
the trainer only *describes* and *prepares* runs, lazy-imports torch/peft, and
NEVER trains automatically. Real training is an explicit, GPU-gated step the
operator runs — no keys, no network, no `.env`.
"""

from .corpus import (
    SFTExample,
    PreferencePair,
    TrainingCorpus,
    harvest_session,
    harvest_tree_preferences,
)
from .local_trainer import (
    LoRAConfig,
    TrainingPlan,
    TrainingUnavailable,
    gpu_report,
    check_training_deps,
    build_training_plan,
    write_training_script,
    reentry_instructions,
)
from .arena import (
    ARENA_SCHEMA_VERSION,
    DEFAULT_MIN_DECIDED,
    DEFAULT_PROMOTION_GATE,
    PromotionArena,
)

__all__ = [
    "SFTExample", "PreferencePair", "TrainingCorpus", "harvest_session",
    "harvest_tree_preferences",
    "LoRAConfig", "TrainingPlan", "TrainingUnavailable",
    "gpu_report", "check_training_deps", "build_training_plan",
    "write_training_script", "reentry_instructions",
    "ARENA_SCHEMA_VERSION", "DEFAULT_MIN_DECIDED", "DEFAULT_PROMOTION_GATE",
    "PromotionArena",
]
