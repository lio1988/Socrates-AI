"""Strict capability-manifest foundation for Agent Prompt Architecture v2.

A manifest declares what a caller has authorized for one task. It never executes
anything. Runtime wiring remains CED-owned and is intentionally outside this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence, Tuple

from .identity import AgentPromptArchitectureError

CAPABILITY_MANIFEST_SCHEMA_VERSION = "ced_capability_manifest_v1"

KNOWN_CAPABILITIES = frozenset({
    "micro_socratic_check",
    "external_consultation",
    "web_retrieval",
    "calculator",
    "time_date",
    "calendar_read",
    "document_read",
    "code_test",
    "source_check",
    "user_clarification",
    "deliberation_tree_revision",
    "memory_lessons",
    "identity_guidance",
})

_MICRO_MODES = frozenset({"light", "standard", "high_risk"})
_CONSULT_MODES = frozenset({"critic", "independent_solver", "judge"})
_CONTEXT_ONLY = frozenset({"memory_lessons", "identity_guidance"})
_TOOL_CAPABILITIES = frozenset({
    "web_retrieval",
    "calculator",
    "time_date",
    "calendar_read",
    "document_read",
    "code_test",
    "source_check",
    "user_clarification",
})


@dataclass(frozen=True)
class CapabilityGrant:
    capability_id: str
    max_calls: int = 0
    mode: str = ""

    def __post_init__(self) -> None:
        if self.capability_id not in KNOWN_CAPABILITIES:
            raise AgentPromptArchitectureError(
                f"unknown capability {self.capability_id!r}"
            )
        if type(self.max_calls) is not int or self.max_calls < 0 or self.max_calls > 8:
            raise AgentPromptArchitectureError(
                "max_calls must be an integer within [0, 8]"
            )
        if not isinstance(self.mode, str):
            raise AgentPromptArchitectureError("mode must be a string")
        mode = self.mode.strip()
        object.__setattr__(self, "mode", mode)

        if self.capability_id == "micro_socratic_check":
            if self.max_calls != 1 or mode not in _MICRO_MODES:
                raise AgentPromptArchitectureError(
                    "micro_socratic_check requires max_calls=1 and a valid risk mode"
                )
        elif self.capability_id == "external_consultation":
            if self.max_calls != 1 or mode not in _CONSULT_MODES:
                raise AgentPromptArchitectureError(
                    "external_consultation requires max_calls=1 and a valid mode"
                )
        elif self.capability_id in _CONTEXT_ONLY:
            if self.max_calls != 0 or mode:
                raise AgentPromptArchitectureError(
                    f"{self.capability_id} is context-only and requires max_calls=0"
                )
        elif self.capability_id in _TOOL_CAPABILITIES:
            if self.max_calls < 1 or mode:
                raise AgentPromptArchitectureError(
                    f"{self.capability_id} requires max_calls>=1 and no mode"
                )
        elif self.capability_id == "deliberation_tree_revision":
            if self.max_calls < 1 or mode:
                raise AgentPromptArchitectureError(
                    "deliberation_tree_revision requires max_calls>=1 and no mode"
                )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CapabilityGrant":
        if not isinstance(value, Mapping):
            raise AgentPromptArchitectureError("capability grant must be a mapping")
        allowed = {"capability_id", "max_calls", "mode"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise AgentPromptArchitectureError(
                f"capability grant has unknown fields {unknown!r}"
            )
        if "capability_id" not in value:
            raise AgentPromptArchitectureError(
                "capability grant is missing capability_id"
            )
        return cls(
            capability_id=value["capability_id"],
            max_calls=value.get("max_calls", 0),
            mode=value.get("mode", ""),
        )

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "max_calls": self.max_calls,
            "mode": self.mode,
        }


@dataclass(frozen=True)
class CapabilityManifest:
    grants: Tuple[CapabilityGrant, ...] = field(default_factory=tuple)
    schema_version: str = CAPABILITY_MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CAPABILITY_MANIFEST_SCHEMA_VERSION:
            raise AgentPromptArchitectureError(
                f"schema_version must be {CAPABILITY_MANIFEST_SCHEMA_VERSION!r}"
            )
        grants = tuple(
            item if isinstance(item, CapabilityGrant)
            else CapabilityGrant.from_mapping(item)
            for item in self.grants
        )
        ids = [grant.capability_id for grant in grants]
        if len(ids) != len(set(ids)):
            raise AgentPromptArchitectureError(
                "capability manifest contains duplicate capability IDs"
            )
        object.__setattr__(
            self,
            "grants",
            tuple(sorted(grants, key=lambda grant: grant.capability_id)),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CapabilityManifest":
        if not isinstance(value, Mapping):
            raise AgentPromptArchitectureError("capability manifest must be a mapping")
        allowed = {"schema_version", "grants"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise AgentPromptArchitectureError(
                f"capability manifest has unknown fields {unknown!r}"
            )
        grants = value.get("grants", ())
        if isinstance(grants, (str, bytes)) or not isinstance(grants, Sequence):
            raise AgentPromptArchitectureError("grants must be a sequence")
        return cls(
            schema_version=value.get(
                "schema_version", CAPABILITY_MANIFEST_SCHEMA_VERSION
            ),
            grants=tuple(grants),
        )

    def is_enabled(self, capability_id: str) -> bool:
        return any(grant.capability_id == capability_id for grant in self.grants)

    def canonical_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "grants": [grant.to_dict() for grant in self.grants],
        }


def build_capability_manifest_block(manifest: CapabilityManifest) -> str:
    if not isinstance(manifest, CapabilityManifest):
        raise AgentPromptArchitectureError(
            "build_capability_manifest_block requires CapabilityManifest"
        )
    payload = json.dumps(
        manifest.canonical_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return "\n".join((
        "<capability_manifest>",
        "Only the listed capabilities are authorized for this task.",
        payload,
        "A listed capability is permission for the governed caller to route it;",
        "it is not evidence that the agent already executed it.",
        "</capability_manifest>",
    ))


__all__ = [
    "CAPABILITY_MANIFEST_SCHEMA_VERSION",
    "KNOWN_CAPABILITIES",
    "CapabilityGrant",
    "CapabilityManifest",
    "build_capability_manifest_block",
]
