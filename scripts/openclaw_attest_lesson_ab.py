"""Attest a single-agent Lesson A/B result into immutable Memory evidence.

The command accepts only a strict attestation envelope containing:

- an ``openclaw_agent_lesson_ab_v1`` instrument report;
- the SHA-256 fingerprint of the exact curated lesson tested;
- the governed Identity fingerprint of the exact target agent tested;
- a retained experiment manifest and its verified canonical SHA-256 digest.

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
import math
import os
import pathlib
import re
import sys
from typing import Any, Mapping, Sequence

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
EXPERIMENT_SCHEMA_VERSION = "openclaw_agent_lesson_ab_experiment_v1"
_W = 78
_MAX_REPORT_BYTES = 1_000_000
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
        r"client[_-]?secret)\s*[:=]\s*\S{8,}",
        re.IGNORECASE,
    ),
)
_ENVELOPE_FIELDS = {
    "schema_version",
    "lesson_fingerprint",
    "target_identity_fingerprint",
    "experiment_fingerprint",
    "experiment_manifest",
    "instrument_report",
}
_EXPERIMENT_FIELDS = {
    "schema_version",
    "target_agent_id",
    "lesson_id",
    "treatment_scope",
    "question_hashes",
    "control_configuration",
    "treatment_configuration",
    "execution_mode",
    "provider_ids",
    "judge_configuration",
    "random_seeds",
    "arm_orders",
    "counterbalanced",
    "compute_budget",
    "producer_version",
}
_ARM_CONFIGURATION_FIELDS = {
    "base_configuration_fingerprint",
    "injected_lesson_fingerprints",
    "injection_target_agent_id",
}
_JUDGE_CONFIGURATION_FIELDS = {
    "judge_set_fingerprint",
    "self_judging_allowed",
}
_COMPUTE_BUDGET_FIELDS = {
    "token_limit",
    "timeout_seconds",
    "retry_limit",
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


def _nonempty_text(value: Any, *, field: str, maximum: int = 256) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    if any(ord(char) < 32 for char in text):
        raise ValueError(f"{field} contains control characters")
    return text


def _find_secret(value: Any, path: str = "experiment_manifest") -> str:
    if isinstance(value, Mapping):
        for key, child in value.items():
            violation = _find_secret(child, f"{path}.{key}")
            if violation:
                return violation
        return ""
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            violation = _find_secret(child, f"{path}[{index}]")
            if violation:
                return violation
        return ""
    if isinstance(value, str):
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                return f"{path} contains secret-shaped data"
    return ""


def _canonical_digest(value: Any, *, field: str) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be canonical JSON") from exc
    return hashlib.sha256(payload).hexdigest()


def _sequence(value: Any, *, field: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be a sequence")
    return tuple(value)


def _exact_mapping(value: Any, *, field: str, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a JSON object")
    if set(value) != fields:
        raise ValueError(
            f"{field} contains missing or unknown fields: "
            f"{sorted(set(value) ^ fields)}")
    return value


def _validate_arm_configuration(
    value: Any,
    *,
    field: str,
) -> Mapping[str, Any]:
    config = _exact_mapping(
        value, field=field, fields=_ARM_CONFIGURATION_FIELDS)
    _hex_digest(
        config.get("base_configuration_fingerprint"),
        field=f"{field}.base_configuration_fingerprint",
    )
    injections = _sequence(
        config.get("injected_lesson_fingerprints"),
        field=f"{field}.injected_lesson_fingerprints",
    )
    for index, fingerprint in enumerate(injections):
        _hex_digest(
            fingerprint,
            field=f"{field}.injected_lesson_fingerprints[{index}]",
        )
    if len(set(injections)) != len(injections):
        raise ValueError(f"{field} contains duplicate lesson fingerprints")
    target = str(config.get("injection_target_agent_id", "")).strip()
    return {
        "base_configuration_fingerprint": config[
            "base_configuration_fingerprint"],
        "injected_lesson_fingerprints": injections,
        "injection_target_agent_id": target,
    }


def _validate_experiment_manifest(
    manifest: Mapping[str, Any],
    *,
    report: Mapping[str, Any],
    bindings: Mapping[str, str],
) -> None:
    _exact_mapping(
        manifest,
        field="experiment_manifest",
        fields=_EXPERIMENT_FIELDS,
    )
    if manifest.get("schema_version") != EXPERIMENT_SCHEMA_VERSION:
        raise ValueError(
            f"experiment_manifest must use schema_version "
            f"{EXPERIMENT_SCHEMA_VERSION!r}")

    target_agent_id = _nonempty_text(
        manifest.get("target_agent_id"),
        field="experiment_manifest.target_agent_id",
        maximum=128,
    )
    lesson_id = _nonempty_text(
        manifest.get("lesson_id"),
        field="experiment_manifest.lesson_id",
        maximum=128,
    )
    if target_agent_id != str(report.get("target_agent_id", "")).strip():
        raise ValueError(
            "experiment_manifest target_agent_id does not match instrument_report")
    if lesson_id != str(report.get("lesson_id", "")).strip():
        raise ValueError(
            "experiment_manifest lesson_id does not match instrument_report")
    if manifest.get("treatment_scope") != "single_agent" or \
            report.get("treatment_scope") != "single_agent":
        raise ValueError(
            "experiment_manifest and instrument_report must use "
            "treatment_scope='single_agent'")

    question_hashes = _sequence(
        manifest.get("question_hashes"),
        field="experiment_manifest.question_hashes",
    )
    if not question_hashes:
        raise ValueError("experiment_manifest requires question_hashes")
    normalized_questions = tuple(
        _hex_digest(value, field=f"question_hashes[{index}]")
        for index, value in enumerate(question_hashes)
    )
    if len(set(normalized_questions)) != len(normalized_questions):
        raise ValueError("experiment_manifest question_hashes must be distinct")

    seeds = _sequence(
        manifest.get("random_seeds"),
        field="experiment_manifest.random_seeds",
    )
    if len(seeds) != len(question_hashes):
        raise ValueError(
            "experiment_manifest random_seeds must align with question_hashes")
    if any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 0
           for seed in seeds):
        raise ValueError(
            "experiment_manifest random_seeds must be non-negative integers")

    arm_orders = _sequence(
        manifest.get("arm_orders"),
        field="experiment_manifest.arm_orders",
    )
    if len(arm_orders) != len(question_hashes):
        raise ValueError(
            "experiment_manifest arm_orders must align with question_hashes")
    normalized_orders = []
    for index, order in enumerate(arm_orders):
        pair = _sequence(order, field=f"arm_orders[{index}]")
        if pair not in {
            ("control", "treatment"),
            ("treatment", "control"),
        }:
            raise ValueError(
                "each experiment arm order must contain control and treatment "
                "exactly once")
        normalized_orders.append(pair)
    counterbalanced = manifest.get("counterbalanced")
    if not isinstance(counterbalanced, bool):
        raise ValueError("experiment_manifest counterbalanced must be boolean")
    if counterbalanced and len(normalized_orders) > 1 and len(
            set(normalized_orders)) < 2:
        raise ValueError(
            "counterbalanced experiment must exercise both arm orders")

    control = _validate_arm_configuration(
        manifest.get("control_configuration"),
        field="control_configuration",
    )
    treatment = _validate_arm_configuration(
        manifest.get("treatment_configuration"),
        field="treatment_configuration",
    )
    if control["base_configuration_fingerprint"] != \
            treatment["base_configuration_fingerprint"]:
        raise ValueError(
            "control and treatment must share one base configuration fingerprint")
    if control["injected_lesson_fingerprints"] or \
            control["injection_target_agent_id"]:
        raise ValueError(
            "control configuration must contain no lesson injection")
    if treatment["injected_lesson_fingerprints"] != (
            bindings["lesson_fingerprint"],):
        raise ValueError(
            "treatment configuration must inject exactly the bound lesson")
    if treatment["injection_target_agent_id"] != target_agent_id:
        raise ValueError(
            "treatment configuration must inject only into the target agent")

    providers = _sequence(
        manifest.get("provider_ids"),
        field="experiment_manifest.provider_ids",
    )
    normalized_providers = tuple(
        _nonempty_text(value, field="provider_id", maximum=128)
        for value in providers
    )
    if not normalized_providers:
        raise ValueError("experiment_manifest requires provider_ids")
    if len(set(normalized_providers)) != len(normalized_providers):
        raise ValueError("experiment_manifest provider_ids must be distinct")

    _nonempty_text(
        manifest.get("execution_mode"),
        field="experiment_manifest.execution_mode",
        maximum=128,
    )
    _nonempty_text(
        manifest.get("producer_version"),
        field="experiment_manifest.producer_version",
        maximum=128,
    )

    judge = _exact_mapping(
        manifest.get("judge_configuration"),
        field="judge_configuration",
        fields=_JUDGE_CONFIGURATION_FIELDS,
    )
    _hex_digest(
        judge.get("judge_set_fingerprint"),
        field="judge_configuration.judge_set_fingerprint",
    )
    if judge.get("self_judging_allowed") is not False:
        raise ValueError("single-agent Lesson A/B forbids self-judging")

    budget = _exact_mapping(
        manifest.get("compute_budget"),
        field="compute_budget",
        fields=_COMPUTE_BUDGET_FIELDS,
    )
    token_limit = budget.get("token_limit")
    retry_limit = budget.get("retry_limit")
    timeout_seconds = budget.get("timeout_seconds")
    if isinstance(token_limit, bool) or not isinstance(token_limit, int) or \
            token_limit <= 0:
        raise ValueError("compute_budget.token_limit must be a positive integer")
    if isinstance(retry_limit, bool) or not isinstance(retry_limit, int) or \
            retry_limit < 0:
        raise ValueError(
            "compute_budget.retry_limit must be a non-negative integer")
    if isinstance(timeout_seconds, bool) or not isinstance(
            timeout_seconds, (int, float)) or not math.isfinite(
                float(timeout_seconds)) or float(timeout_seconds) <= 0:
        raise ValueError(
            "compute_budget.timeout_seconds must be a positive finite number")

    tested = report.get("tested")
    if isinstance(tested, bool) or not isinstance(tested, int) or \
            tested > len(question_hashes):
        raise ValueError(
            "instrument_report tested count exceeds experiment question count")


def _unpack_envelope(
    envelope: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, str], Mapping[str, Any]]:
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
    manifest = envelope.get("experiment_manifest")
    if not isinstance(manifest, Mapping) or not manifest:
        raise ValueError("experiment_manifest must be a non-empty JSON object")
    violation = _find_secret(manifest)
    if violation:
        raise ValueError(violation)
    supplied_experiment = _hex_digest(
        envelope.get("experiment_fingerprint"),
        field="experiment_fingerprint",
    )
    actual_experiment = _canonical_digest(
        manifest, field="experiment_manifest")
    if supplied_experiment != actual_experiment:
        raise ValueError(
            "experiment_fingerprint does not match experiment_manifest")
    bindings = {
        "lesson_fingerprint": _hex_digest(
            envelope.get("lesson_fingerprint"), field="lesson_fingerprint"),
        "target_identity_fingerprint": _hex_digest(
            envelope.get("target_identity_fingerprint"),
            field="target_identity_fingerprint",
        ),
        "experiment_fingerprint": supplied_experiment,
    }
    return report, bindings, manifest


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
    source = str(report.get("source", "")).strip()
    if not source:
        raise ValueError("Lesson A/B report requires a non-empty instrument source")
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
    binding_digest = _canonical_digest(
        dict(bindings), field="attestation bindings")
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
        report, bindings, manifest = _unpack_envelope(envelope)
        action = _normalize_action(_value(argv, "--action"))
        _validate_report_identity(
            report, agent_id=agent_id, verified_by=verified_by)
        _validate_experiment_manifest(
            manifest,
            report=report,
            bindings=bindings,
        )

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
