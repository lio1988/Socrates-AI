"""
OpenClaw Prompts — versioned, auditable prompt lineage (Goal 7).

Canonical doc: docs/openclaw_memory_lessons/PROMPT_REGISTRY.md
(OPENCLAW_MEMORY_LESSONS_PROMPT_REGISTRY).

Runtime-inert by design: the CED core and reasoning_prompts.py never import
this package. Wiring a registry-rendered prompt into live calls remains an
explicit later step.
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
    rendered_prompt_fingerprint,
    render_prompt_with_metadata,
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
    "rendered_prompt_fingerprint",
    "render_prompt_with_metadata",
    "PATCH_PROPOSAL_ID_START",
    "attach_proposals",
    "propose_patches_from_capturer",
    "propose_prompt_patches",
]
