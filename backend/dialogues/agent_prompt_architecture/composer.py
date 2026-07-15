"""Deterministic composition of the common Agent Prompt Architecture v2 layers.

This composer stops before temporary role, phase/task, and output-schema overlays.
It is therefore safe to test as a foundation but is not canonical runtime wiring.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from .capabilities import CapabilityManifest, build_capability_manifest_block
from .constitution import (
    CONSTITUTION_ID,
    CONSTITUTION_VERSION,
    constitution_digest,
    render_constitution,
)
from .identity import (
    AgentIdentityPromptView,
    AgentPromptArchitectureError,
    build_agent_identity_block,
    identity_prompt_digest,
)

FOUNDATION_PROMPT_ID = "ced_agent_prompt_v2_foundation"
FOUNDATION_PROMPT_VERSION = "v2.0-foundation"


def build_agent_foundation_prompt(
    identity_view: AgentIdentityPromptView,
    capability_manifest: Optional[CapabilityManifest] = None,
) -> str:
    """Compose Constitution → Identity → Capability Manifest, in that order."""
    if not isinstance(identity_view, AgentIdentityPromptView):
        raise AgentPromptArchitectureError(
            "build_agent_foundation_prompt requires AgentIdentityPromptView"
        )
    if capability_manifest is None:
        capability_manifest = CapabilityManifest()
    if not isinstance(capability_manifest, CapabilityManifest):
        raise AgentPromptArchitectureError(
            "capability_manifest must be CapabilityManifest or None"
        )
    return "\n\n".join((
        render_constitution(),
        build_agent_identity_block(identity_view),
        build_capability_manifest_block(capability_manifest),
    ))


def foundation_prompt_metadata(
    identity_view: AgentIdentityPromptView,
    capability_manifest: Optional[CapabilityManifest] = None,
) -> Dict[str, Any]:
    """Trace-ready lineage only; no prompt text, scores, secrets, or hidden state."""
    if capability_manifest is None:
        capability_manifest = CapabilityManifest()
    prompt = build_agent_foundation_prompt(identity_view, capability_manifest)
    return {
        "prompt_id": FOUNDATION_PROMPT_ID,
        "prompt_version": FOUNDATION_PROMPT_VERSION,
        "prompt_digest": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "constitution_id": CONSTITUTION_ID,
        "constitution_version": CONSTITUTION_VERSION,
        "constitution_digest": constitution_digest(),
        "identity_schema_version": identity_view.schema_version,
        "identity_digest": identity_prompt_digest(identity_view),
        "capability_schema_version": capability_manifest.schema_version,
        "enabled_capabilities": [
            grant.capability_id for grant in capability_manifest.grants
        ],
    }


__all__ = [
    "FOUNDATION_PROMPT_ID",
    "FOUNDATION_PROMPT_VERSION",
    "build_agent_foundation_prompt",
    "foundation_prompt_metadata",
]
