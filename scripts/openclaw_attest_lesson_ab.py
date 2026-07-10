"""Attest a single-agent Lesson A/B report into immutable Memory evidence.

This is the operator bridge between an explicit
``openclaw_agent_lesson_ab_v1`` report and the governed self-revision evidence
registry. It deliberately refuses the ordinary whole-council ``lesson_ab_v2``
report because that report cannot causally attribute an effect to one agent.

Usage::

    python scripts/openclaw_attest_lesson_ab.py local_apprentice_001 ^
        --report runs/agent_lesson_ab/report.json ^
        --action link ^
        --verified-by "Your Name"

For a harmful post-link result use ``--action unlink``. The command writes only
an immutable evidence record. It never proposes, approves, applies, confirms,
or reverts a Memory change.

Environment:
    CED_MEMORY_LESSONS_PATH             curated MEMORY_LESSONS.md override
    CED_IDENTITY_DIR                    governed identity profiles
    CED_SELF_REVISION_EVIDENCE_DIR      immutable evidence registry

No providers, network, API keys, prompt mutation, or CED authority changes.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import sys
from typing import Any, Mapping

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_identity import (                       # noqa: E402
    AGENT_LESSON_AB_REPORT_VERSION,
    IdentityRegistry,
    RevisionEvidenceRegistry,
    build_agent_lesson_ab_evidence,
)
from backend.dialogues.openclaw_memory import (                         # noqa: E402
    default_lessons_path,
    load_memory_lessons,
)

_W = 78
_MAX_REPORT_BYTES = 1_000_000
_ACTIONS = {
    "link": "link_stable_lesson",
    "link_stable_lesson": "link_stable_lesson",
    "unlink": "unlink_stable_lesson",
    "unlink_stable_lesson": "unlink_stable_lesson",
}


def _value(argv, name, default="") -> str:
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        return default
    return str(argv[index + 1]).strip()


def _load_report(path_text: str) -> tuple[pathlib.Path, Mapping[str, Any]]:
    if not path_text:
        raise ValueError("Lesson A/B attestation requires --report")
    if "://" in path_text:
        raise ValueError("Lesson A/B report must be a local file, not a URL")
    path = pathlib.Path(path_text)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Lesson A/B report {path} does not exist")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError(f"Lesson A/B report {path} cannot be inspected") from exc
    if size > _MAX_REPORT_BYTES:
        raise ValueError(
            f"Lesson A/B report exceeds {_MAX_REPORT_BYTES} bytes")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Lesson A/B report {path} is unreadable or invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("Lesson A/B report must be one JSON object")
    return path, value


def _normalize_action(value: str) -> str:
    action = _ACTIONS.get(str(value or "").strip().lower())
    if action is None:
        raise ValueError("Lesson A/B action must be link or unlink")
    return action


def _catalogue_lesson(report: Mapping[str, Any], env) -> Any:
    lesson_id = str(report.get("lesson_id", "")).strip()
    path_text = str(env.get("CED_MEMORY_LESSONS_PATH", "")).strip()
    path = pathlib.Path(path_text) if path_text else default_lessons_path()
    try:
        lessons = load_memory_lessons(path, include_deprecated=True)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"curated lesson catalogue {path} is unreadable") from exc
    matches = [lesson for lesson in lessons if lesson.lesson_id == lesson_id]
    if len(matches) != 1:
        raise ValueError(
            f"Lesson A/B report lesson {lesson_id!r} must identify exactly one "
            "curated lesson")
    return matches[0]


def _validate_report_identity(
    report: Mapping[str, Any],
    *,
    agent_id: str,
    verified_by: str,
) -> None:
    if report.get("schema_version") != AGENT_LESSON_AB_REPORT_VERSION:
        raise ValueError(
            "only openclaw_agent_lesson_ab_v1 single-agent reports can become "
            "personal Memory evidence")
    if str(report.get("target_agent_id", "")).strip() != agent_id:
        raise ValueError("Lesson A/B report targets another agent")
    report_verifier = str(report.get("verified_by", "")).strip()
    if not report_verifier:
        raise ValueError("Lesson A/B report requires a named verifier")
    if report_verifier.casefold() != verified_by.casefold():
        raise ValueError(
            "--verified-by must match the named verifier stored in the report")
    observed_on = str(report.get("observed_on", "")).strip()
    if not observed_on:
        raise ValueError("Lesson A/B report requires observed_on")
    try:
        _dt.date.fromisoformat(observed_on)
    except ValueError as exc:
        raise ValueError(
            "Lesson A/B report observed_on must use YYYY-MM-DD") from exc


def _validate_current_state(
    *,
    agent_id: str,
    lesson: Any,
    action: str,
    identity_dir: pathlib.Path,
) -> None:
    profile = IdentityRegistry(identity_dir).load_profile(agent_id)
    if profile is None:
        raise ValueError(
            f"no governed identity profile exists for {agent_id!r}")
    if action == "link_stable_lesson" and not lesson.is_stable:
        raise ValueError(
            f"{lesson.lesson_id} is {lesson.status!r}; only stable or verified "
            "lessons may be linked")
    if action == "unlink_stable_lesson" and \
            lesson.lesson_id not in profile.stable_lessons:
        raise ValueError(
            f"{lesson.lesson_id} is not currently linked to {agent_id!r}")


def main(argv=None, env=None) -> int:
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env

    agent_id = str(argv[1]).strip() if len(argv) > 1 else ""
    verified_by = _value(argv, "--verified-by")

    print("=" * _W)
    print("  OPENCLAW SINGLE-AGENT LESSON A/B ATTESTATION - evidence only")
    print("=" * _W)
    if not agent_id:
        print("  REFUSED: usage requires <agent_id>.")
        return 1
    if not verified_by:
        print("  REFUSED: attestation requires --verified-by \"Your Name\".")
        return 1
    if verified_by.casefold() == agent_id.casefold():
        print("  REFUSED: an agent can never attest its own Lesson A/B evidence.")
        return 1

    identity_dir = pathlib.Path(env.get(
        "CED_IDENTITY_DIR", str(_ROOT / "runs" / "openclaw_identity")))
    evidence_dir = pathlib.Path(env.get(
        "CED_SELF_REVISION_EVIDENCE_DIR",
        str(_ROOT / "runs" / "openclaw_self_revision_evidence"),
    ))

    try:
        report_path, report = _load_report(_value(argv, "--report"))
        action = _normalize_action(_value(argv, "--action"))
        _validate_report_identity(
            report, agent_id=agent_id, verified_by=verified_by)

        # The strict builder is the only conversion path. It rechecks the exact
        # schema, single-agent scope, sample size, verdict, finite metrics, harm
        # bounds, regressions, lesson id, verifier, and secret-shaped values.
        evidence = build_agent_lesson_ab_evidence(report, action=action)
        registry = RevisionEvidenceRegistry(evidence_dir)
        existing = registry.load(evidence.reference)
        if existing is None:
            lesson = _catalogue_lesson(report, env)
            _validate_current_state(
                agent_id=agent_id,
                lesson=lesson,
                action=action,
                identity_dir=identity_dir,
            )
        registry.register(evidence)
    except ValueError as exc:
        print(f"  REFUSED: {exc}")
        print("=" * _W)
        return 1

    print(f"  agent          : {agent_id}")
    print(f"  action         : {action}")
    print(f"  lesson         : {evidence.value}")
    print(f"  report         : {report_path}")
    print(f"  attested by    : {verified_by}")
    print(f"  observed on    : {evidence.observed_on}")
    print(f"  evidence       : {evidence.reference}")
    print(f"  registry       : {evidence_dir}")
    print("-" * _W)
    print("  Nothing was linked or unlinked. The agent may cite this immutable")
    print("  evidence in a governed Memory proposal; evaluation and non-self")
    print("  approval still follow.")
    print("  Next:")
    print(f"    python scripts/openclaw_self_review.py {agent_id}")
    print("    python scripts/openclaw_review.py")
    print("    python scripts/openclaw_status.py")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
