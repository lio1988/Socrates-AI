"""
OpenClaw review — the system reports to its human curator.

This is the missing communication step of the learning loop: sessions write
traces and shadow records to disk; THIS script reads the accumulated history
back, runs the mechanical proposers over it, and writes everything a curator
needs to review in one place. Nothing is promoted, nothing mutates — the
system proposes, the human decides.

    python scripts/openclaw_review.py

Reads (env-configurable, same defaults the other scripts write to):
    CED_TRACE_DIR      traces from live/mock dialogues
                       (default runs/openclaw_traces)
    CED_SHADOW_DIR     shadow apprentice records
                       (default runs/openclaw_shadow)

Writes (never touches curated sources like MEMORY_LESSONS.md):
    CED_PROPOSALS_DIR  (default runs/openclaw_proposals)
      PROPOSED_LESSONS.md        loader-parseable lesson proposals
      PROPOSED_PROMPT_PATCHES.md prompt-patch proposals (registry lifecycle)

Free, offline, deterministic. No provider calls, no keys, no network.
"""

from __future__ import annotations

import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_memory import (                       # noqa: E402
    aggregate_failures,
    load_jsonl,
    load_traces,
    propose_lessons,
    render_proposed_lessons,
    write_proposed_lessons,
)
from backend.dialogues.openclaw_prompts import (                      # noqa: E402
    propose_prompt_patches,
)
from backend.dialogues.openclaw_identity import (                     # noqa: E402
    evidence_from_shadow_traces,
)

_W = 78


def _render_patch_proposals(patches) -> str:
    """Readable curator report for proposed prompt patches (they enter the
    Goal 7 registry lifecycle by being attached to a spec — see
    PROMPT_REGISTRY.md; this file is the human review surface)."""
    lines = [
        "# PROPOSED prompt patches - pending human review",
        "",
        "Machine-proposed from repeated failure patterns. Nothing here is",
        "active: a default render excludes proposed patches; only a NAMED",
        "candidate A/B run can exercise one, and only a human promotes it.",
        "",
    ]
    for p in patches:
        lines.extend([
            f"## {p.patch_id} - {p.name}",
            "",
            f"**Status:** {p.status}",
            f"**Targets:** {', '.join(p.target_providers)}",
            f"**Reason:** {p.reason}",
            f"**Expected effect:** {p.expected_effect}",
            f"**Risk:** {p.risk}",
            "",
            "**Patch text:**",
            "```text",
            p.text,
            "```",
            "",
        ])
    return "\n".join(lines)


def main(argv=None, env=None) -> int:
    env = os.environ if env is None else env

    trace_dir = env.get("CED_TRACE_DIR", str(_ROOT / "runs" / "openclaw_traces"))
    shadow_path = pathlib.Path(env.get(
        "CED_SHADOW_DIR", str(_ROOT / "runs" / "openclaw_shadow"))) / "shadow_records.jsonl"
    proposals_dir = pathlib.Path(env.get(
        "CED_PROPOSALS_DIR", str(_ROOT / "runs" / "openclaw_proposals")))

    traces = load_traces(trace_dir)
    shadow_records = load_jsonl(shadow_path)

    print("=" * _W)
    print("  OPENCLAW REVIEW - the system reports; the human decides")
    print("=" * _W)
    print(f"  traces         : {len(traces)} session(s) from {trace_dir}")
    print(f"  shadow records : {len(shadow_records)} from {shadow_path}")
    print("-" * _W)

    if not traces and not shadow_records:
        print("  Nothing to review yet.")
        print("  Run scripts/live_dialogue.py or scripts/shadow_dialogue.py "
              "first -")
        print("  their traces and shadow records are what this review reads.")
        print("=" * _W)
        return 0

    # 1. Failure patterns across ALL history (traces + shadow records — the
    #    shadow records are trace-shaped and carry real ratification facts).
    history = list(traces) + list(shadow_records)
    grouped = aggregate_failures(history)
    print("  FAILURE PATTERNS (repeated across sessions -> proposals):")
    if grouped:
        for key, observations in grouped.items():
            sessions = sorted({o['session_id'] for o in observations})
            print(f"    {key:<32} x{len(sessions)} session(s)")
    else:
        print("    none detected - the council is holding its contracts")
    print("-" * _W)

    # 2. Mechanical proposals (repeated-only; status=proposed; never active).
    lessons = propose_lessons(history)
    patches = propose_prompt_patches(history)
    proposals_dir.mkdir(parents=True, exist_ok=True)
    written = []
    if lessons:
        path = write_proposed_lessons(lessons, proposals_dir / "PROPOSED_LESSONS.md")
        written.append(str(path))
        print(f"  proposed lessons        : {len(lessons)} -> {path}")
    else:
        print("  proposed lessons        : none (no pattern repeated enough)")
    if patches:
        path = proposals_dir / "PROPOSED_PROMPT_PATCHES.md"
        path.write_text(_render_patch_proposals(patches), encoding="utf-8")
        written.append(str(path))
        print(f"  proposed prompt patches : {len(patches)} -> {path}")
    else:
        print("  proposed prompt patches : none (no pattern repeated enough)")
    print("-" * _W)

    # 3. Shadow apprentice standing (verified marker-filtered evidence).
    apprentice_ids = sorted({str(r.get("apprentice_id", ""))
                             for r in shadow_records
                             if r.get("apprentice_id")})
    if apprentice_ids:
        print("  SHADOW APPRENTICE EVIDENCE (marker-verified):")
        for aid in apprentice_ids:
            evidence = evidence_from_shadow_traces(aid, shadow_records)
            if evidence:
                print(f"    {aid}: blind_spots wins="
                      f"{evidence['shadow_blind_spots_wins']} over "
                      f"{evidence['shadow_sessions_analyzed']} session(s)")
        print("-" * _W)

    print("  Next:")
    print("    review the proposal files above; A/B test candidates first")
    print("    (OPERATOR_GUIDE Mode E), promote by hand (Mode F), deprecate")
    print("    what fails. The system never promotes itself.")
    print("    python scripts/openclaw_status.py   (the joined-up view)")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
