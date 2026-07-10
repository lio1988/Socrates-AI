"""
OpenClaw Prompts — prompt patch generator (Goal 8).

Converts REPEATED failures observed in session traces (Goal 5) into PROPOSED
prompt patches for the Goal 7 registry lifecycle. The mirror image of the
lesson proposer (Goal 6): same detectors, same repeated-only gating, same
never-auto-promote constitution — but the output is a small append-only
prompt instruction instead of a memory lesson.

It does NOT rewrite prompts from scratch. Every proposal is a small block
with the PROMPT_PATCH_POLICY audit fields (reason with observed session ids,
expected effect, risk).

Safety, mechanically guaranteed (not aspirational):

  - Every proposal has ``status="proposed"``. The Goal 7 registry's default
    render applies ONLY stable/verified patches (test-locked), so a proposal
    can NEVER reach a rendered prompt without an explicit, named A/B
    candidate run and a human promotion afterwards.
  - A pattern must repeat (``min_occurrences``, default 2) before it becomes
    a proposal — one-off noise is not a patch.
  - Proposal ids live in a reserved provisional range (PATCH-9001+) and are
    deterministic (sorted pattern order). The curator re-numbers on
    promotion.
  - The A/B instrument for a proposed patch is the same matched-pair harness
    pattern as lessons (Goal 6.1): control render vs candidate render, same
    question — the patch earns ``tested``, a human moves it further.

No provider calls, no network, no keys.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, Iterable, List, Sequence

from backend.dialogues.openclaw_memory.lesson_proposer import (
    DEFAULT_MIN_OCCURRENCES,
    aggregate_failures,
)

from .prompt_registry import ALL_PROVIDERS, PromptPatch, PromptSpec

#: Reserved provisional id range for machine-proposed patches (mirrors the
#: lesson proposer's LESSON-9001+ range).
PATCH_PROPOSAL_ID_START = 9001


def _template_for(pattern_key: str) -> Dict[str, str]:
    if pattern_key == "ratification_failed":
        return {
            "name": "Ground the stress test in the strongest raised objection",
            "text": "**Ratification discipline**: your synthesis must engage "
                    "the strongest objection actually raised in this dialogue "
                    "inside crucial_stress_test, and final_verdict must answer "
                    "it directly. A synthesis that ignores the elenchus "
                    "invites a ratification block.",
            "expected_effect": "Fewer ratification failures: the ratifier "
                               "finds the standing objection already engaged.",
            "risk": "Over-fitting the synthesis to please the ratifier can "
                    "suppress honest disagreement.",
        }
    if pattern_key == "assembly_missing":
        return {
            "name": "Always produce a complete, schema-valid five-section draft",
            "text": "**Assembly discipline**: every synthesis response must "
                    "contain ALL five required fields (core_answer, "
                    "crucial_stress_test, blind_spots, nuance, final_verdict) "
                    "as a schema-valid JSON object, so assembly always has a "
                    "real candidate.",
            "expected_effect": "Sessions stop ending without an assembled "
                               "answer.",
            "risk": "A rushed complete draft can be weaker than a partial "
                    "honest one; the fix is contract compliance, not haste.",
        }
    if pattern_key.startswith("unresolved_section:"):
        section = pattern_key.split(":", 1)[1]
        return {
            "name": f"Give substantive standalone content to '{section}'",
            "text": f"**Section discipline**: '{section}' must receive "
                    "substantive standalone content in every draft — a thin "
                    "or empty section leaves the final answer incomplete even "
                    "when other sections win.",
            "expected_effect": f"'{section}' stops shipping unresolved.",
            "risk": "Padding with filler to avoid 'unresolved' is worse than "
                    "honest thinness; the fix is substance.",
        }
    if pattern_key.startswith("phase_missing:"):
        phase = pattern_key.split(":", 1)[1]
        return {
            "name": f"Match the exact output contract in phase '{phase}'",
            "text": "**Output contract**: respond with EXACTLY the required "
                    "JSON contract for this phase — one JSON object, the "
                    "exact field names, nothing else. A schema-invalid "
                    "response starves every downstream phase.",
            "expected_effect": f"Phase '{phase}' stops producing zero valid "
                               "moves.",
            "risk": "This pattern can also stem from provider outages rather "
                    "than prompt behavior; verify the task log before "
                    "treating it as a prompt fix.",
        }
    return {
        "name": f"Address repeated failure pattern: {pattern_key}",
        "text": f"**Review needed**: the failure pattern '{pattern_key}' "
                "repeated across sessions; a human should decide whether a "
                "prompt instruction can address it.",
        "expected_effect": "Unknown until reviewed.",
        "risk": "Auto-detected pattern without a curated template; review "
                "carefully before any A/B run.",
    }


def propose_prompt_patches(
    traces: Sequence[Dict[str, Any]],
    *,
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
    target_providers: Iterable[str] = (ALL_PROVIDERS,),
) -> List[PromptPatch]:
    """Convert repeated failure patterns across traces into PROPOSED patches.

    Deterministic: patterns sorted by key; ids assigned from
    ``PATCH_PROPOSAL_ID_START`` in that order. Every proposal has
    ``status="proposed"`` and therefore can never render into a default
    prompt without explicit candidate naming + human promotion.
    """
    if min_occurrences < 1:
        raise ValueError(f"min_occurrences must be >= 1, got {min_occurrences!r}")
    grouped = aggregate_failures(traces)
    total = len(traces)
    proposals: List[PromptPatch] = []
    next_id = PATCH_PROPOSAL_ID_START
    for pattern_key, observations in grouped.items():
        sessions = sorted({o["session_id"] for o in observations})
        if len(sessions) < min_occurrences:
            continue
        t = _template_for(pattern_key)
        reason = (f"observed failure pattern '{pattern_key}' in "
                  f"{len(sessions)}/{total} analyzed sessions "
                  f"({', '.join(sessions)}): {observations[0]['detail']}")
        proposals.append(PromptPatch(
            patch_id=f"PATCH-{next_id}",
            name=t["name"],
            status="proposed",
            text=t["text"],
            reason=reason,
            expected_effect=t["expected_effect"],
            risk=t["risk"],
            target_providers=tuple(target_providers),
        ))
        next_id += 1
    return proposals


def propose_patches_from_capturer(
    capturer: Any,
    *,
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
) -> List[PromptPatch]:
    """Convenience: propose patches from a TraceCapturer's collected traces."""
    return propose_prompt_patches(list(getattr(capturer, "traces", [])),
                                  min_occurrences=min_occurrences)


def attach_proposals(spec: PromptSpec,
                     proposals: Sequence[PromptPatch]) -> PromptSpec:
    """Return a NEW spec carrying the proposals (input spec untouched).

    The registry's own guarantees then apply: a default render still excludes
    them; only a named candidate run can exercise one. Duplicate patch ids
    are refused by the spec's own validation."""
    return dataclasses.replace(spec, patches=spec.patches + tuple(proposals))
