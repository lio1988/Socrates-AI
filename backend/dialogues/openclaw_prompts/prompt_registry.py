"""
OpenClaw Prompt Registry — deterministic, auditable prompt lineage (Goal 7).

The missing control layer this closes: prompts had no version identity. A
prompt that drifts silently cannot be A/B tested, cannot be traced, and
cannot be trusted. This registry gives every prompt:

  - a declarative spec (base template + variables + lesson slot)
  - small, append-only, provider-scoped patches with the SAME lifecycle as
    memory lessons (proposed -> tested -> verified -> stable -> deprecated)
  - a human version label AND a content-addressed fingerprint, so the trace
    metadata is tamper-evident: if the rendered text changed, the version
    string changes
  - trace-ready metadata (no secrets, no scores)

Mechanical safety (never aspirational):

  - NO automatic prompt mutation: a render applies ONLY stable/verified
    patches unless the caller names specific candidate patch ids explicitly
    (that is how a proposed patch gets its A/B run — the Lesson A/B harness
    pattern is the shared "tested" instrument). Deprecated patches never
    render, even as candidates.
  - Append-only patches: v0 has no replace/delete operations — every patch
    is reversible by construction (PROMPT_PATCH_POLICY).
  - Strict variables: a missing required variable or an unknown supplied
    variable raises — never a silent empty slot. Placeholders use
    ``{{name}}`` (double braces) because prompt bodies legitimately contain
    JSON examples with single braces.
  - The lesson slot collapses cleanly when no lessons are supplied — no
    dangling "Relevant memory lessons:" header.
  - Leak guard: rendered text is refused if it carries key-shaped secrets.
  - Runtime-inert: nothing in the CED core imports this package
    (test-locked, same isolation as the identity layer). Wiring a rendered
    prompt into live calls is a LATER, explicit goal.

Pure stdlib, deterministic, offline. No provider calls, no keys.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

#: Same lifecycle as memory lessons (MEMORY_LESSONS.md / lesson_loader).
PROMPT_STATUSES: Tuple[str, ...] = (
    "proposed", "tested", "verified", "stable", "deprecated",
)

#: Patch statuses a DEFAULT render may apply (mirror of STABLE_OR_VERIFIED).
RENDERABLE_STATUSES: frozenset = frozenset({"stable", "verified"})

#: ``{{variable_name}}`` — double braces so JSON examples in prompt bodies
#: (single braces) never collide with substitution.
_PLACEHOLDER_RE = re.compile(r"\{\{([a-z_][a-z0-9_]*)\}\}")

#: Render-time refusal patterns (same family as the trace-capture guard).
_LEAK_PATTERNS: Tuple[str, ...] = ("sk-ant-", "ANTHROPIC_API_KEY", "Bearer ")

#: Applies-to-every-provider marker for patches.
ALL_PROVIDERS = "*"


@dataclass(frozen=True)
class PromptPatch:
    """A small, append-only, provider-scoped prompt addition.

    Carries the PROMPT_PATCH_POLICY audit fields (reason, expected effect,
    risk) and the lesson lifecycle. A patch is a BLOCK APPENDED to the
    rendered prompt — v0 deliberately has no replace/delete operations, so
    every patch is reversible by construction.
    """
    patch_id: str                       # e.g. "PATCH-0001"
    name: str
    status: str
    text: str                           # the appended block
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
        return provider_id is not None and provider_id in self.target_providers


@dataclass(frozen=True)
class PromptSpec:
    """Declarative identity of one prompt: template + variables + patches."""
    prompt_id: str                      # e.g. "openclaw_synthesis"
    version_label: str                  # human lineage label, e.g. "v0.1"
    description: str
    base_text: str                      # template with {{variables}}
    required_variables: Tuple[str, ...] = ()
    lesson_slot: str = "memory_lessons" # optional variable: collapses if empty
    patches: Tuple[PromptPatch, ...] = ()

    def __post_init__(self) -> None:
        if not self.prompt_id.strip():
            raise ValueError("prompt_id must be non-empty")
        ids = [p.patch_id for p in self.patches]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.prompt_id}: duplicate patch ids")


# ── Patch selection (the never-auto-mutate rule, mechanically) ───────────────

def applied_patches(
    spec: PromptSpec,
    provider_id: Optional[str] = None,
    *,
    candidate_patch_ids: Sequence[str] = (),
) -> List[PromptPatch]:
    """Ordered patches a render will append.

    Default: ONLY stable/verified patches that target this provider.
    ``candidate_patch_ids`` names specific proposed/tested patches to include
    for an explicit A/B experiment — blanket inclusion does not exist.
    Deprecated patches never apply, even when named. Naming an unknown patch
    id raises (an experiment must know exactly what it is testing).
    """
    by_id = {p.patch_id: p for p in spec.patches}
    unknown = [pid for pid in candidate_patch_ids if pid not in by_id]
    if unknown:
        raise ValueError(f"{spec.prompt_id}: unknown candidate patches {unknown!r}")
    wanted: List[PromptPatch] = []
    for patch in sorted(spec.patches, key=lambda p: p.patch_id):
        if not patch.applies_to(provider_id):
            continue
        if patch.status == "deprecated":
            continue                    # never renders, candidate or not
        if patch.status in RENDERABLE_STATUSES or patch.patch_id in set(candidate_patch_ids):
            wanted.append(patch)
    return wanted


# ── Rendering (strict, deterministic) ─────────────────────────────────────────

def _substitute(template: str, variables: Mapping[str, str],
                *, context: str) -> str:
    found = set(_PLACEHOLDER_RE.findall(template))
    supplied = set(variables)
    missing = sorted(found - supplied)
    if missing:
        raise ValueError(f"{context}: missing variables {missing!r}")
    unknown = sorted(supplied - found)
    if unknown:
        raise ValueError(f"{context}: unknown variables {unknown!r} "
                         "(strict rendering refuses silent extras)")
    return _PLACEHOLDER_RE.sub(lambda m: str(variables[m.group(1)]), template)


def render_prompt(
    spec: PromptSpec,
    variables: Mapping[str, Any],
    *,
    provider_id: Optional[str] = None,
    candidate_patch_ids: Sequence[str] = (),
) -> str:
    """Render one prompt deterministically.

    - every required variable must be supplied; extras are refused
    - the lesson slot vanishes cleanly when its value is empty/absent
    - applicable patches (see :func:`applied_patches`) are appended in
      patch_id order, separated by blank lines
    - the result is refused if it carries key-shaped secrets
    """
    vars_norm: Dict[str, str] = {k: str(v) for k, v in variables.items()}
    missing_required = sorted(set(spec.required_variables) - set(vars_norm))
    if missing_required:
        raise ValueError(f"{spec.prompt_id}: missing required variables "
                         f"{missing_required!r}")

    # Lesson slot: optional by design — empty means the slot line disappears.
    if spec.lesson_slot:
        if not vars_norm.get(spec.lesson_slot, "").strip():
            vars_norm[spec.lesson_slot] = ""

    text = _substitute(spec.base_text, vars_norm, context=spec.prompt_id)
    # Collapse the hole an empty lesson slot leaves behind.
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    for patch in applied_patches(spec, provider_id,
                                 candidate_patch_ids=candidate_patch_ids):
        text = f"{text}\n\n{patch.text.strip()}"

    for pattern in _LEAK_PATTERNS:
        if pattern in text:
            raise ValueError(
                f"{spec.prompt_id}: rendered prompt refused — contains "
                f"key-shaped secret pattern {pattern!r}")
    return text


# ── Version identity (label + content-addressed fingerprint) ─────────────────

def prompt_fingerprint(
    spec: PromptSpec,
    provider_id: Optional[str] = None,
    *,
    candidate_patch_ids: Sequence[str] = (),
) -> str:
    """Deterministic sha256[:12] of the composition (base + applied patch
    texts, in order). Tamper-evident lineage: any change to the base text or
    to the applied patch set changes the fingerprint."""
    parts = [spec.base_text]
    parts.extend(p.text for p in applied_patches(
        spec, provider_id, candidate_patch_ids=candidate_patch_ids))
    canon = "\x00".join(parts)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


def prompt_metadata(
    spec: PromptSpec,
    provider_id: Optional[str] = None,
    *,
    candidate_patch_ids: Sequence[str] = (),
) -> Dict[str, Any]:
    """Trace-ready audit metadata (matches TraceCapturer's metadata= slot).
    Carries lineage only — no prompt text, no scores, no secrets."""
    patches = applied_patches(spec, provider_id,
                              candidate_patch_ids=candidate_patch_ids)
    return {
        "prompt_id": spec.prompt_id,
        "prompt_version": spec.version_label,
        "prompt_fingerprint": prompt_fingerprint(
            spec, provider_id, candidate_patch_ids=candidate_patch_ids),
        "applied_patches": [p.patch_id for p in patches],
        "candidate_patches": sorted(candidate_patch_ids),
        "provider_scope": provider_id or ALL_PROVIDERS,
        "lesson_slot": spec.lesson_slot,
    }


# ── The registry ──────────────────────────────────────────────────────────────

class PromptRegistry:
    """Deterministic catalog of prompt specs, keyed by prompt_id."""

    def __init__(self) -> None:
        self._specs: Dict[str, PromptSpec] = {}

    def register(self, spec: PromptSpec) -> None:
        if spec.prompt_id in self._specs:
            raise ValueError(f"duplicate prompt_id {spec.prompt_id!r} "
                             "(evolve via a new version_label, not overwrite)")
        self._specs[spec.prompt_id] = spec

    def get(self, prompt_id: str) -> PromptSpec:
        if prompt_id not in self._specs:
            raise KeyError(f"unknown prompt {prompt_id!r}")
        return self._specs[prompt_id]

    def all_prompts(self) -> List[PromptSpec]:
        return [self._specs[k] for k in sorted(self._specs)]

    def metadata_for(self, prompt_id: str,
                     provider_id: Optional[str] = None) -> Dict[str, Any]:
        return prompt_metadata(self.get(prompt_id), provider_id)
