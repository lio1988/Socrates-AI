r"""
OpenClaw review — the system reports to its human curator.

Reads accumulated dialogue/shadow history plus governed self-revision evidence
and lifecycle records. It writes human-review surfaces only: nothing is
promoted, approved, applied, or mutated.

    python scripts/openclaw_review.py

Reads:
    CED_TRACE_DIR                         dialogue traces
    CED_SHADOW_DIR                        shadow apprentice records
    CED_SELF_REVISION_EVIDENCE_DIR        immutable attested evidence
    CED_SELF_REVISION_DIR                 proposal lifecycle records

Writes under CED_PROPOSALS_DIR (default runs/openclaw_proposals):
    PROPOSED_LESSONS.md
    PROPOSED_PROMPT_PATCHES.md
    SELF_REVISION_PIPELINE.md

Free, offline, deterministic. No provider calls, keys, network, or authority.
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
    write_proposed_lessons,
)
from backend.dialogues.openclaw_prompts import (                      # noqa: E402
    propose_prompt_patches,
)
from backend.dialogues.openclaw_identity import (                     # noqa: E402
    RevisionEvidenceRegistry,
    SelfRevisionRegistry,
    evidence_from_shadow_traces,
)

_W = 78


def _render_patch_proposals(patches) -> str:
    """Readable curator report for proposed prompt patches."""
    lines = [
        "# PROPOSED prompt patches - pending human review",
        "",
        "Machine-proposed from repeated failure patterns. Nothing here is",
        "active: a default render excludes proposed patches; only a NAMED",
        "candidate A/B run can exercise one, and only a human promotes it.",
        "",
    ]
    for patch in patches:
        lines.extend([
            f"## {patch.patch_id} - {patch.name}",
            "",
            f"**Status:** {patch.status}",
            f"**Targets:** {', '.join(patch.target_providers)}",
            f"**Reason:** {patch.reason}",
            f"**Expected effect:** {patch.expected_effect}",
            f"**Risk:** {patch.risk}",
            "",
            "**Patch text:**",
            "```text",
            patch.text,
            "```",
            "",
        ])
    return "\n".join(lines)


def _pipeline_by_agent(evidence_records, lifecycle_records):
    grouped = {}
    for evidence in evidence_records:
        grouped.setdefault(evidence.agent_id, {
            "evidence": [], "lifecycles": []
        })["evidence"].append(evidence)
    for lifecycle in lifecycle_records:
        agent_id = str(lifecycle.get("agent_id", "")).strip() or "<unknown>"
        grouped.setdefault(agent_id, {
            "evidence": [], "lifecycles": []
        })["lifecycles"].append(lifecycle)
    return grouped


def _next_pipeline_action(agent_id, evidence, lifecycles):
    statuses = [str(row.get("status", "")) for row in lifecycles]
    if any(status == "probationary" for status in statuses):
        return "collect independent post-change evidence; confirm or roll back"
    if any(status in {
        "submitted", "evaluated_passed", "evaluated_failed", "approved"
    } for status in statuses):
        return "complete independent evaluation/decision/application review"
    if evidence and not lifecycles:
        return f"run scripts/openclaw_self_review.py {agent_id}"
    if evidence:
        return "review whether new evidence warrants another bounded self-review"
    return (
        f"run scripts/openclaw_attest_evidence.py {agent_id} "
        "--verified-by \"Your Name\""
    )


def _render_self_revision_pipeline(evidence_records, lifecycle_records):
    grouped = _pipeline_by_agent(evidence_records, lifecycle_records)
    lines = [
        "# SELF-REVISION PIPELINE - human review surface",
        "",
        "This report is read-only. Evidence is not a proposal; a proposal is not",
        "an approval; an approval is not an application. Memory, Identity, and",
        "Soul remain descriptive and grant no CED authority.",
        "",
    ]
    if not grouped:
        lines.extend([
            "No self-revision evidence or lifecycle records exist yet.",
            "",
        ])
        return "\n".join(lines)

    for agent_id in sorted(grouped):
        evidence = sorted(
            grouped[agent_id]["evidence"], key=lambda row: row.reference)
        lifecycles = sorted(
            grouped[agent_id]["lifecycles"],
            key=lambda row: str(row.get("proposal_id", "")),
        )
        lines.extend([
            f"## {agent_id}",
            "",
            f"Verified evidence records: **{len(evidence)}**",
        ])
        if evidence:
            for record in evidence:
                supports = ", ".join(record.supports)
                lines.append(
                    f"- `{record.reference}` — `{supports}` — "
                    f"{record.value} — verified by **{record.verified_by}**"
                )
        else:
            lines.append("- none")

        lines.extend([
            "",
            f"Proposal lifecycle records: **{len(lifecycles)}**",
        ])
        if lifecycles:
            for record in lifecycles:
                proposal = record.get("proposal") or {}
                target = str(proposal.get("target", "?"))
                action = str(proposal.get("action", "?"))
                lines.append(
                    f"- `{record.get('proposal_id', '?')}` — "
                    f"**{record.get('status', 'unknown')}** — "
                    f"`{target}:{action}`"
                )
        else:
            lines.append("- none")

        lines.extend([
            "",
            "Next governed action:",
            f"- {_next_pipeline_action(agent_id, evidence, lifecycles)}",
            "",
        ])
    return "\n".join(lines)


def main(argv=None, env=None) -> int:
    env = os.environ if env is None else env

    trace_dir = env.get(
        "CED_TRACE_DIR", str(_ROOT / "runs" / "openclaw_traces"))
    shadow_path = pathlib.Path(env.get(
        "CED_SHADOW_DIR", str(_ROOT / "runs" / "openclaw_shadow"))) / \
        "shadow_records.jsonl"
    proposals_dir = pathlib.Path(env.get(
        "CED_PROPOSALS_DIR", str(_ROOT / "runs" / "openclaw_proposals")))
    evidence_dir = env.get(
        "CED_SELF_REVISION_EVIDENCE_DIR",
        str(_ROOT / "runs" / "openclaw_self_revision_evidence"),
    )
    revision_dir = env.get(
        "CED_SELF_REVISION_DIR",
        str(_ROOT / "runs" / "openclaw_self_revisions"),
    )

    traces = load_traces(trace_dir)
    shadow_records = load_jsonl(shadow_path)
    evidence_records = RevisionEvidenceRegistry(evidence_dir).all_records()
    lifecycle_records = SelfRevisionRegistry(revision_dir).all_records()

    print("=" * _W)
    print("  OPENCLAW REVIEW - the system reports; the human decides")
    print("=" * _W)
    print(f"  traces         : {len(traces)} session(s) from {trace_dir}")
    print(f"  shadow records : {len(shadow_records)} from {shadow_path}")
    print(f"  revision evidence : {len(evidence_records)}")
    print(f"  revision lifecycles: {len(lifecycle_records)}")
    print("-" * _W)

    if not any((traces, shadow_records, evidence_records, lifecycle_records)):
        print("  Nothing to review yet.")
        print("  Run shadow/live dialogue first, or attest existing instrument evidence.")
        print("=" * _W)
        return 0

    written = []
    history = list(traces) + list(shadow_records)

    if history:
        grouped = aggregate_failures(history)
        print("  FAILURE PATTERNS (repeated across sessions -> proposals):")
        if grouped:
            for key, observations in grouped.items():
                sessions = sorted({row["session_id"] for row in observations})
                print(f"    {key:<32} x{len(sessions)} session(s)")
        else:
            print("    none detected - the council is holding its contracts")
        print("-" * _W)

        lessons = propose_lessons(history)
        patches = propose_prompt_patches(history)
        proposals_dir.mkdir(parents=True, exist_ok=True)
        if lessons:
            path = write_proposed_lessons(
                lessons, proposals_dir / "PROPOSED_LESSONS.md")
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

    apprentice_ids = sorted({
        str(record.get("apprentice_id", ""))
        for record in shadow_records if record.get("apprentice_id")
    })
    if apprentice_ids:
        print("  SHADOW APPRENTICE EVIDENCE (marker-verified):")
        for agent_id in apprentice_ids:
            evidence = evidence_from_shadow_traces(agent_id, shadow_records)
            if evidence:
                print(f"    {agent_id}: blind_spots wins="
                      f"{evidence['shadow_blind_spots_wins']} over "
                      f"{evidence['shadow_sessions_analyzed']} session(s)")
        print("-" * _W)

    if evidence_records or lifecycle_records:
        proposals_dir.mkdir(parents=True, exist_ok=True)
        pipeline_path = proposals_dir / "SELF_REVISION_PIPELINE.md"
        pipeline_path.write_text(
            _render_self_revision_pipeline(
                evidence_records, lifecycle_records),
            encoding="utf-8",
        )
        written.append(str(pipeline_path))
        print("  SELF-REVISION PIPELINE:")
        for agent_id, values in sorted(
                _pipeline_by_agent(evidence_records, lifecycle_records).items()):
            statuses = {}
            for row in values["lifecycles"]:
                status = str(row.get("status", "unknown"))
                statuses[status] = statuses.get(status, 0) + 1
            status_text = ", ".join(
                f"{name}={count}" for name, count in sorted(statuses.items())
            ) or "no proposals"
            print(f"    {agent_id}: evidence={len(values['evidence'])}; "
                  f"{status_text}")
        print(f"    curator report -> {pipeline_path}")
        print("-" * _W)

    print("  Next:")
    if written:
        print("    review the files written above; nothing is active by existence")
    print("    A/B test candidates, require named non-self decisions, and use")
    print("    the recoverable transaction path for approved self-revisions.")
    print("    python scripts/openclaw_status.py   (the joined-up view)")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
