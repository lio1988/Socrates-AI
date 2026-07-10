"""Attest a single-agent Lesson A/B result into immutable Memory evidence.

The command accepts only a strict attestation envelope containing:

- an ``openclaw_agent_lesson_ab_v1`` instrument report;
- the SHA-256 fingerprint of the exact curated lesson tested;
- the governed Identity fingerprint of the exact target agent tested;
- a SHA-256 experiment fingerprint covering the matched execution setup.

It deliberately refuses the ordinary whole-council ``lesson_ab_v2`` report and
unbound personal reports. The output is only an immutable evidence record; the
command never proposes, approves, applies, confirms, or reverts Memory.

Usage::

    python scripts/openclaw_attest_lesson_ab.py local_apprentice_001 ^
        --report runs/agent_lesson_ab/attestation.json ^
        --action link ^
        --verified-by "Your Name"

For a harmful post-link result use ``--action unlink``.

Environment:
    CED_MEMORY_LESSONS_PATH             curated MEMORY_LESSONS.md override
    CED_IDENTITY_DIR                    governed identity profiles
    CED_SELF_REVISION_EVIDENCE_DIR      immutable evidence registry

No providers, network, API keys, prompt mutation, or CED authority changes.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import re
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
    governed_profile_fingerprint,
)
from backend.dialogues.openclaw_memory import (                         # noqa: E402
    default_lessons_path,
    load_memory_lessons,
    memory_lesson_fingerprint,
)

ATTESTATION_SCHEMA_VERSION = "openclaw_agent_lesson_ab_attestation_v1"
_W = 78
_MAX_REPORT_BYTES = 1_000_000
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_ENVELOPE_FIELDS = {
    "schema_version",
    "lesson_fingerprint",
    "target_identity_fingerprint",
    "experiment_fingerprint",
    "instrument_report",
}
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


def _load_envelope(path_text: str) -> tuple[pathlib.Path, Mapping[str, Any]]:
    if not path_text:
        raise ValueError("Lesson A/B attestation requires --report")
    if "://" in path_text:
        raise ValueError("Lesson A/B attestation must be a local file, not a URL")
    path = pathlib.Path(path_text)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Lesson A/B attestation {path} does not exist")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError(
            f"Lesson A/B attestation {path} cannot be inspected") from exc
    if size > _MAX_REPORT_BYTES:
        raise ValueError(
            f"Lesson A/B attestation exceeds {_MAX_REPORT_BYTES} bytes")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Lesson A/B attestation {path} is unreadable or invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("Lesson A/B attestation must be one JSON object")
    return path, value


def _hex_digest(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not _HEX64_RE.fullmatch(text):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return text


def _unpack_envelope(
    envelope: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, str]]:
    if set(envelope) != _ENVELOPE_FIELDS:
        raise ValueError(
            "Lesson A/B attestation contains missing or unknown fields: "
            f"{sorted(set(envelope) ^ _ENVELOPE_FIELDS)}")
    if envelope.get("schema_version") != ATTESTATION_SCHEMA_VERSION:
        raise ValueError(
            f"Lesson A/B attestation must use schema_version "
            f"{ATTESTATION_SCHEMA_VERSION!r}")
    report = envelope.get("instrument_report")
    if not isinstance(report, Mapping):
        raise ValueError("instrument_report must be one JSON object")
    bindings = {
        "lesson_fingerprint": _hex_digest(
            envelope.get("lesson_fingerprint"), field="lesson_fingerprint"),
        "target_identity_fingerprint": _hex_digest(
            envelope.get("target_identity_fingerprint"),
            field="target_identity_fingerprint",
        ),
        "experiment_fingerprint": _hex_digest(
            envelope.get("experiment_fingerprint"),
            field="experiment_fingerprint",
        ),
    }
    return report, bindings


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
        observed_date = _dt.date.fromisoformat(observed_on)
    except ValueError as exc:
        raise ValueError(
            "Lesson A/B report observed_on must use YYYY-MM-DD") from exc
    if observed_date > _dt.date.today():
        raise ValueError("Lesson A/B report observed_on cannot be in the future")


def _bind_report(
    report: Mapping[str, Any],
    bindings: Mapping[str, str],
) -> dict[str, Any]:
    """Commit all three external bindings into the builder's report digest."""
    source = str(report.get("source", "")).strip()
    binding_digest = hashlib.sha256(json.dumps(
        dict(bindings),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    suffix = f"#bindings-{binding_digest[:16]}"
    if len(source) + len(suffix) > 512:
        raise ValueError(
            "Lesson A/B report source is too long to bind provenance safely")
    bound = dict(report)
    bound["source"] = source + suffix
    return bound


def _validate_current_state(
    *,
    agent_id: str,
    lesson: Any,
    action: str,
    identity_dir: pathlib.Path,
    bindings: Mapping[str, str],
) -> None:
    profile = IdentityRegistry(identity_dir).load_profile(agent_id)
    if profile is None:
        raise ValueError(
            f"no governed identity profile exists for {agent_id!r}")
    actual_lesson = memory_lesson_fingerprint(lesson)
    if actual_lesson != bindings["lesson_fingerprint"]:
        raise ValueError(
            "Lesson A/B attestation lesson_fingerprint does not match the "
            "current curated lesson")
    actual_identity = governed_profile_fingerprint(profile)
    if actual_identity != bindings["target_identity_fingerprint"]:
        raise ValueError(
            "Lesson A/B attestation target_identity_fingerprint does not match "
            "the current governed agent state")
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
        report_path, envelope = _load_envelope(_value(argv, "--report"))
        report, bindings = _unpack_envelope(envelope)
        action = _normalize_action(_value(argv, "--action"))
        _validate_report_identity(
            report, agent_id=agent_id, verified_by=verified_by)

        # The strict builder remains the only conversion path. The binding
        # suffix becomes part of its canonical report digest and immutable
        # evidence source, so changed lesson/Identity/experiment state conflicts.
        bound_report = _bind_report(report, bindings)
        evidence = build_agent_lesson_ab_evidence(
            bound_report, action=action)
        registry = RevisionEvidenceRegistry(evidence_dir)
        existing = registry.load(evidence.reference)
        if existing is None:
            lesson = _catalogue_lesson(report, env)
            _validate_current_state(
                agent_id=agent_id,
                lesson=lesson,
                action=action,
                identity_dir=identity_dir,
                bindings=bindings,
            )
        registry.register(evidence)
    except ValueError as exc:
        print(f"  REFUSED: {exc}")
        print("=" * _W)
        return 1

    print(f"  agent          : {agent_id}")
    print(f"  action         : {action}")
    print(f"  lesson         : {evidence.value}")
    print(f"  attestation    : {report_path}")
    print(f"  attested by    : {verified_by}")
    print(f"  observed on    : {evidence.observed_on}")
    print(f"  lesson bind    : {bindings['lesson_fingerprint'][:16]}...")
    print(f"  identity bind  : {bindings['target_identity_fingerprint'][:16]}...")
    print(f"  experiment bind: {bindings['experiment_fingerprint'][:16]}...")
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
