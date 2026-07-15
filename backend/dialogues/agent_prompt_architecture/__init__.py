"""Foundations for Socrates AI Agent Prompt Architecture v2.

The package is intentionally runtime-inert until the controlled integration target.
"""

from .capabilities import (
    CAPABILITY_MANIFEST_SCHEMA_VERSION,
    KNOWN_CAPABILITIES,
    CapabilityGrant,
    CapabilityManifest,
    build_capability_manifest_block,
)
from .composer import (
    FOUNDATION_PROMPT_ID,
    FOUNDATION_PROMPT_VERSION,
    build_agent_foundation_prompt,
    foundation_prompt_metadata,
)
from .constitution import (
    CED_CORE_EPISTEMIC_CONSTITUTION_V2,
    CONSTITUTION_ID,
    CONSTITUTION_VERSION,
    constitution_digest,
    render_constitution,
)
from .identity import (
    IDENTITY_VIEW_SCHEMA_VERSION,
    AgentIdentityPromptView,
    AgentPromptArchitectureError,
    IdentityGuidanceItem,
    build_agent_identity_block,
    identity_prompt_digest,
)

__all__ = [
    "CAPABILITY_MANIFEST_SCHEMA_VERSION",
    "KNOWN_CAPABILITIES",
    "CapabilityGrant",
    "CapabilityManifest",
    "build_capability_manifest_block",
    "FOUNDATION_PROMPT_ID",
    "FOUNDATION_PROMPT_VERSION",
    "build_agent_foundation_prompt",
    "foundation_prompt_metadata",
    "CED_CORE_EPISTEMIC_CONSTITUTION_V2",
    "CONSTITUTION_ID",
    "CONSTITUTION_VERSION",
    "constitution_digest",
    "render_constitution",
    "IDENTITY_VIEW_SCHEMA_VERSION",
    "AgentIdentityPromptView",
    "AgentPromptArchitectureError",
    "IdentityGuidanceItem",
    "build_agent_identity_block",
    "identity_prompt_digest",
]
