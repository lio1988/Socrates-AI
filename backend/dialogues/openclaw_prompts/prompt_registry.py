"""
OpenClaw Prompt Registry — deterministic, auditable prompt lineage (Goal 7).

Two different identities are tracked:
  - composition fingerprint: base template + applied patch texts
  - rendered fingerprint: the exact final text after variables/lessons/patches

The registry is version-aware: multiple versions of one prompt_id may coexist.
An unversioned lookup becomes an error when more than one version exists, so no
caller can silently drift to an arbitrary prompt.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROMPT_STATUSES: Tuple[str, ...] = (
    "proposed", "tested", "verified", "stable", "deprecated",
)
RENDERABLE_STATUSES: frozenset = frozenset({"stable", "verified"})
_PLACEHOLDER_RE = re.compile(r"\{\{([a-z_][a-z0-9_]*)\}\}")
_LEAK_PATTERNS: Tuple[str, ...] = (
    "sk-ant-", "ANTHROPIC_API_KEY", "Bearer ",
)
ALL_PROVIDERS = "*"


@dataclass(frozen=True)
class PromptPatch:
    patch_id: str
    name: str
    status: str
    text: str
    reason: str
    expected_effect: str
    risk: str
    target_providers: Tuple[str, ...] = (ALL_PROVIDERS,)

    def __post_init__(self) -> None:
        if self.status not in PROMPT_STATUSES:
            raise ValueError(
                f"{self.patch_id}: invalid status {self.status!r} "
                f"(expected one of {PROMPT_STATUSES})")
        if not self.text.strip():
            raise ValueError(f"{self.patch_id}: empty patch text")
        if not self.target_providers:
            raise ValueError(f"{self.patch_id}: no target providers")

    def applies_to(self, provider_id: Optional[str]) -> bool:
        if ALL_PROVIDERS in self.target_providers:
            return True
        return (
            provider_id is not None
            and provider_id in self.target_providers
        )


@dataclass(frozen=True)
class PromptSpec:
    prompt_id: str
    version_label: str
    description: str
    base_text: str
    required_variables: Tuple[str, ...] = ()
    lesson_slot: str = "memory_lessons"
    patches: Tuple[PromptPatch, ...] = ()

    def __post_init__(self) -> None:
        if not self.prompt_id.strip():
            raise ValueError("prompt_id must be non-empty")
        if not self.version_label.strip():
            raise ValueError("version_label must be non-empty")
        patch_ids = [patch.patch_id for patch in self.patches]
        if len(patch_ids) != len(set(patch_ids)):
            raise ValueError(f"{self.prompt_id}: duplicate patch ids")


def applied_patches(
    spec: PromptSpec,
    provider_id: Optional[str] = None,
    *,
    candidate_patch_ids: Sequence[str] = (),
) -> List[PromptPatch]:
    """Select patches without automatic mutation."""
    by_id = {patch.patch_id: patch for patch in spec.patches}
    unknown = [
        patch_id for patch_id in candidate_patch_ids
        if patch_id not in by_id
    ]
    if unknown:
        raise ValueError(
            f"{spec.prompt_id}: unknown candidate patches {unknown!r}")

    candidate_set = set(candidate_patch_ids)
    wanted: List[PromptPatch] = []
    for patch in sorted(spec.patches, key=lambda item: item.patch_id):
        if not patch.applies_to(provider_id):
            continue
        if patch.status == "deprecated":
            continue
        if (
            patch.status in RENDERABLE_STATUSES
            or patch.patch_id in candidate_set
        ):
            wanted.append(patch)
    return wanted


def _substitute(
    template: str,
    variables: Mapping[str, str],
    *,
    context: str,
) -> str:
    found = set(_PLACEHOLDER_RE.findall(template))
    supplied = set(variables)
    missing = sorted(found - supplied)
    if missing:
        raise ValueError(f"{context}: missing variables {missing!r}")
    unknown = sorted(supplied - found)
    if unknown:
        raise ValueError(
            f"{context}: unknown variables {unknown!r} "
            "(strict rendering refuses silent extras)")
    return _PLACEHOLDER_RE.sub(
        lambda match: str(variables[match.group(1)]),
        template,
    )


def render_prompt(
    spec: PromptSpec,
    variables: Mapping[str, Any],
    *,
    provider_id: Optional[str] = None,
    candidate_patch_ids: Sequence[str] = (),
) -> str:
    """Render one prompt deterministically and refuse obvious secrets."""
    vars_norm: Dict[str, str] = {
        key: str(value) for key, value in variables.items()
    }
    missing_required = sorted(
        set(spec.required_variables) - set(vars_norm))
    if missing_required:
        raise ValueError(
            f"{spec.prompt_id}: missing required variables "
            f"{missing_required!r}")

    if spec.lesson_slot and not vars_norm.get(
            spec.lesson_slot, "").strip():
        vars_norm[spec.lesson_slot] = ""

    text = _substitute(
        spec.base_text,
        vars_norm,
        context=f"{spec.prompt_id}@{spec.version_label}",
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    for patch in applied_patches(
        spec,
        provider_id,
        candidate_patch_ids=candidate_patch_ids,
    ):
        text = f"{text}\n\n{patch.text.strip()}"

    for pattern in _LEAK_PATTERNS:
        if pattern in text:
            raise ValueError(
                f"{spec.prompt_id}: rendered prompt refused — contains "
                f"key-shaped secret pattern {pattern!r}")
    return text


def prompt_fingerprint(
    spec: PromptSpec,
    provider_id: Optional[str] = None,
    *,
    candidate_patch_ids: Sequence[str] = (),
) -> str:
    """Composition fingerprint (template + applied patch text).

    Kept under the original name for compatibility. This is not the hash of the
    rendered prompt because variables and lesson text are intentionally absent.
    """
    parts = [spec.base_text]
    parts.extend(
        patch.text for patch in applied_patches(
            spec,
            provider_id,
            candidate_patch_ids=candidate_patch_ids,
        )
    )
    canonical = "\x00".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def rendered_prompt_fingerprint(rendered_text: str) -> str:
    """Fingerprint the exact text sent to a provider."""
    return hashlib.sha256(
        rendered_text.encode("utf-8")).hexdigest()[:12]


def prompt_metadata(
    spec: PromptSpec,
    provider_id: Optional[str] = None,
    *,
    candidate_patch_ids: Sequence[str] = (),
    rendered_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Trace-ready lineage metadata.

    ``prompt_fingerprint`` remains the backwards-compatible composition hash.
    When exact rendered text is supplied, ``rendered_prompt_fingerprint`` binds
    the actual variables and memory block without storing the prompt itself.
    """
    patches = applied_patches(
        spec,
        provider_id,
        candidate_patch_ids=candidate_patch_ids,
    )
    composition = prompt_fingerprint(
        spec,
        provider_id,
        candidate_patch_ids=candidate_patch_ids,
    )
    metadata: Dict[str, Any] = {
        "prompt_id": spec.prompt_id,
        "prompt_version": spec.version_label,
        "prompt_fingerprint": composition,
        "composition_fingerprint": composition,
        "applied_patches": [patch.patch_id for patch in patches],
        "candidate_patches": sorted(candidate_patch_ids),
        "provider_scope": provider_id or ALL_PROVIDERS,
        "lesson_slot": spec.lesson_slot,
    }
    if rendered_text is not None:
        metadata["rendered_prompt_fingerprint"] = \
            rendered_prompt_fingerprint(rendered_text)
    return metadata


def render_prompt_with_metadata(
    spec: PromptSpec,
    variables: Mapping[str, Any],
    *,
    provider_id: Optional[str] = None,
    candidate_patch_ids: Sequence[str] = (),
) -> Tuple[str, Dict[str, Any]]:
    """Render once and return metadata bound to that exact text."""
    rendered = render_prompt(
        spec,
        variables,
        provider_id=provider_id,
        candidate_patch_ids=candidate_patch_ids,
    )
    metadata = prompt_metadata(
        spec,
        provider_id,
        candidate_patch_ids=candidate_patch_ids,
        rendered_text=rendered,
    )
    return rendered, metadata


class PromptRegistry:
    """Version-aware deterministic prompt catalog."""

    def __init__(self) -> None:
        self._specs: Dict[Tuple[str, str], PromptSpec] = {}

    def register(self, spec: PromptSpec) -> None:
        key = (spec.prompt_id, spec.version_label)
        if key in self._specs:
            raise ValueError(
                f"duplicate prompt version {spec.prompt_id!r} "
                f"{spec.version_label!r}")
        self._specs[key] = spec

    def get(
        self,
        prompt_id: str,
        version_label: Optional[str] = None,
    ) -> PromptSpec:
        if version_label is not None:
            key = (prompt_id, version_label)
            if key not in self._specs:
                raise KeyError(
                    f"unknown prompt version {prompt_id!r} "
                    f"{version_label!r}")
            return self._specs[key]

        matches = [
            spec for (registered_id, _), spec in self._specs.items()
            if registered_id == prompt_id
        ]
        if not matches:
            raise KeyError(f"unknown prompt {prompt_id!r}")
        if len(matches) > 1:
            versions = sorted(spec.version_label for spec in matches)
            raise ValueError(
                f"prompt {prompt_id!r} has multiple versions {versions!r}; "
                "version_label is required")
        return matches[0]

    def all_prompts(self) -> List[PromptSpec]:
        return [
            self._specs[key]
            for key in sorted(self._specs)
        ]

    def metadata_for(
        self,
        prompt_id: str,
        provider_id: Optional[str] = None,
        *,
        version_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        return prompt_metadata(
            self.get(prompt_id, version_label),
            provider_id,
        )
