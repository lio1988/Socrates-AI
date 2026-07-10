"""Attest a single-agent Lesson A/B result into trusted Memory evidence.

This is a named-human bridge, not an automatic promotion path. It accepts one
versioned, offline instrument report and converts it through the existing strict
``build_agent_lesson_ab_evidence`` builder into immutable evidence.

Usage:
    python scripts/openclaw_attest_lesson_ab.py local_apprentice_001 \
        --report runs/agent_lesson_ab/report.json \
        --action link \
        --verified-by "Your Name" \
        --verification-reference "review/lesson-ab-001"

For ``link`` the lesson must already be curated as stable/verified. For
``unlink`` the lesson must already be linked in the target agent's identity.
Nothing is proposed, approved, applied, promoted, or injected here.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import sys
from typing import Any, Mapping

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_identity import (                      # noqa: E402
    AGENT_LESSON_AB_REPORT_VERSION,
    IdentityRegistry,
    RevisionEvidenceRegistry,
    build_agent_lesson_ab_evidence,
)
from backend.dialogues.openclaw_memory import load_stable_lessons      # noqa: E402

RAW_REPORT_VERSION = "openclaw_single_agent_lesson_ab_result_v1"
_W = 78
_RAW_FIELDS = {
    "schema_version",
    "target_agent_id",
    "lesson_id",
    "treatment_scope",
    "tested",
    "min_tested",
    "verdict",
    "helped",
    "mean_score_delta",
    "harm_rate",
    "max_harm_rate",
    "ratification_regressions",
    "unresolved_regressions",
    "catastrophic_regressions",
    "configuration_mismatches",
    "source",
    "observed_on",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Attest single-agent Lesson A/B evidence for Memory revision.")
    parser.add_argument("agent_id")
    parser.add_argument("--report", required=True)
    parser.add_argument("--action", required=True, choices=("link", "unlink"))
    parser.add_argument("--verified-by", required=True)
    parser.add_argument("--verification-reference", required=True)
    return parser


def _read_report(path: pathlib.Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Lesson A/B report {path} is unreadable or corrupt") from exc
    if not isinstance(value, Mapping):
        raise ValueError("Lesson A/B report must be a JSON object")
    actual = set(value)
    if actual != _RAW_FIELDS:
        raise ValueError(
            "Lesson A/B report contains missing or unknown fields: "
            f"{sorted(actual ^ _RAW_FIELDS)}")
    if value.get("schema_version") != RAW_REPORT_VERSION:
        raise ValueError(
            f"Lesson A/B report must use schema_version {RAW_REPORT_VERSION!r}")
    if value.get("treatment_scope") != "single_agent":
        raise ValueError("Lesson A/B report must use treatment_scope='single_agent'")
    return dict(value)


def _reference(report: Mapping[str, Any], action: str) -> str:
    semantic = {
        key: report[key]
        for key in sorted(report)
        if key not in {"observed_on"}
    }
    digest = hashlib.sha256(json.dumps(
        semantic,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()[:16]
    return (
        f"agent-ab/{report['target_agent_id']}/{report['lesson_id']}/"
        f"{action}/{digest}"
    )


def _stable_lesson_ids(path: str | None) -> set[str]:
    return {
        lesson.lesson_id
        for lesson in load_stable_lessons(path or None)
    }


def _validate_state(
    *,
    action: str,
    lesson_id: str,
    agent_id: str,
    lessons_path: str | None,
    identity_dir: str,
) -> None:
    if action == "link":
        if lesson_id not in _stable_lesson_ids(lessons_path):
            raise ValueError(
                "Memory link evidence requires an already stable/verified lesson")
        return

    profile = IdentityRegistry(identity_dir).load_profile(agent_id)
    if profile is None:
        raise ValueError("Memory unlink evidence requires an existing identity profile")
    if lesson_id not in profile.stable_lessons:
        raise ValueError(
            "Memory unlink evidence requires the lesson to be currently linked")


def _strict_report(
    raw: Mapping[str, Any],
    *,
    action: str,
    verified_by: str,
    verification_reference: str,
    observed_on: str,
) -> dict[str, Any]:
    return {
        "schema_version": AGENT_LESSON_AB_REPORT_VERSION,
        "reference": _reference(raw, action),
        "target_agent_id": raw["target_agent_id"],
        "lesson_id": raw["lesson_id"],
        "treatment_scope": raw["treatment_scope"],
        "tested": raw["tested"],
        "min_tested": raw["min_tested"],
        "verdict": raw["verdict"],
        "helped": raw["helped"],
        "mean_score_delta": raw["mean_score_delta"],
        "harm_rate": raw["harm_rate"],
        "max_harm_rate": raw["max_harm_rate"],
        "ratification_regressions": raw["ratification_regressions"],
        "unresolved_regressions": raw["unresolved_regressions"],
        "catastrophic_regressions": raw["catastrophic_regressions"],
        "configuration_mismatches": raw["configuration_mismatches"],
        "source": raw["source"],
        "verified_by": verified_by,
        "verification_reference": verification_reference,
        "observed_on": observed_on,
    }


def main(argv=None, env=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv[1:])
    env = os.environ if env is None else env
    try:
        args = _parser().parse_args(argv)
        agent_id = str(args.agent_id).strip()
        verified_by = str(args.verified_by).strip()
        verification_reference = str(args.verification_reference).strip()
        if not agent_id:
            raise ValueError("agent_id must be non-empty")
        if not verified_by:
            raise ValueError("attestation requires a named verifier")
        if verified_by.casefold() == agent_id.casefold():
            raise ValueError("an agent cannot attest its own Lesson A/B evidence")
        if not verification_reference:
            raise ValueError("verification reference must be non-empty")

        raw = _read_report(pathlib.Path(args.report))
        if str(raw.get("target_agent_id", "")).strip() != agent_id:
            raise ValueError("Lesson A/B report belongs to another agent")
        lesson_id = str(raw.get("lesson_id", "")).strip()
        identity_dir = env.get(
            "CED_IDENTITY_DIR", str(_ROOT / "runs" / "openclaw_identity"))
        lessons_path = env.get("CED_MEMORY_LESSONS_PATH", "").strip() or None
        _validate_state(
            action=args.action,
            lesson_id=lesson_id,
            agent_id=agent_id,
            lessons_path=lessons_path,
            identity_dir=identity_dir,
        )

        observed_on = str(raw.get("observed_on", "")).strip() or str(
            env.get("CED_ATTEST_DATE", "")).strip() or _dt.date.today().isoformat()
        strict = _strict_report(
            raw,
            action=args.action,
            verified_by=verified_by,
            verification_reference=verification_reference,
            observed_on=observed_on,
        )
        builder_action = (
            "link_stable_lesson" if args.action == "link"
            else "unlink_stable_lesson"
        )
        evidence = build_agent_lesson_ab_evidence(
            strict, action=builder_action)
        evidence_dir = env.get(
            "CED_SELF_REVISION_EVIDENCE_DIR",
            str(_ROOT / "runs" / "openclaw_self_revision_evidence"),
        )
        RevisionEvidenceRegistry(evidence_dir).register(evidence)
    except (SystemExit, ValueError) as exc:
        if isinstance(exc, SystemExit):
            return int(exc.code or 1)
        print(f"REFUSED: {exc}")
        return 1

    print("=" * _W)
    print("  OPENCLAW SINGLE-AGENT LESSON A/B ATTESTATION")
    print("=" * _W)
    print(f"  agent       : {agent_id}")
    print(f"  lesson      : {lesson_id}")
    print(f"  action      : {builder_action}")
    print(f"  verified by : {verified_by}")
    print(f"  evidence    : {evidence.reference}")
    print("-" * _W)
    print("  Nothing was linked or unlinked. This immutable record is only")
    print("  evidence for a future governed Memory self-revision proposal.")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
