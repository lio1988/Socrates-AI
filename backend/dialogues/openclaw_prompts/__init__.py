"""
OpenClaw Prompts — versioned, auditable prompt lineage (Goal 7).

Canonical doc: docs/openclaw_memory_lessons/PROMPT_REGISTRY.md
(OPENCLAW_MEMORY_LESSONS_PROMPT_REGISTRY).

Runtime-inert by design: the CED core and reasoning_prompts.py never import
this package (test-locked). Wiring a registry-rendered prompt into live
calls is a later, explicit goal — this layer provides identity, lineage,
patch lifecycle, and trace metadata first.

No provider calls, no network, no keys.
"""

from .prompt_registry import (
    ALL_PROVIDERS,
    PROMPT_STATUSES,
    RENDERABLE_STATUSES,
    PromptPatch,
    PromptRegistry,
    PromptSpec,
    applied_patches,
    prompt_fingerprint,
    prompt_metadata,
    render_prompt,
)
from .patch_proposer import (
    PATCH_PROPOSAL_ID_START,
    attach_proposals,
    propose_patches_from_capturer,
    propose_prompt_patches,
)

__all__ = [
    "ALL_PROVIDERS",
    "PROMPT_STATUSES",
    "RENDERABLE_STATUSES",
    "PromptPatch",
    "PromptRegistry",
    "PromptSpec",
    "applied_patches",
    "prompt_fingerprint",
    "prompt_metadata",
    "render_prompt",
    "PATCH_PROPOSAL_ID_START",
    "attach_proposals",
    "propose_patches_from_capturer",
    "propose_prompt_patches",
]
