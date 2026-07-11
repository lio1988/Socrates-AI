"""Attest tree-revision observations into the immutable evidence registry.

Step 2 of the Retained Tree Evidence Operator Bridge - a NAMED HUMAN ACT:

    python scripts/openclaw_attest_tree_evidence.py local_apprentice_001 ^
        --report runs/openclaw_tree_evidence/TREE_EVIDENCE_REPORT_<id>.json ^
        --kind failure ^
        --pattern-key tree_regression:core_answer ^
        --weakness "revisions regress the core answer under review" ^
        --observation <digest> --observation <digest> ^
        --verified-by "Your Name" ^
        --verification-reference review/tree-001

For ``--kind resolution`` cite the matched windows explicitly:

        --before <digest> --before <digest> --after <digest> --after <digest>

The report's digest and every cited observation digest are re-verified; the
strict governed builders then re-validate causality, matched-compute
fairness, distinct sessions, and outcome thresholds. Exact reruns are
idempotent; a different observation set, verifier, or review artifact makes
a NEW immutable record; conflicting overwrites are refused.

This command registers evidence ONLY. It never proposes, approves, applies,
links Memory, changes Identity/Soul, or touches CED.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_identity import (                      # noqa: E402
    RevisionEvidenceRegistry,
    TreeRevisionObservation,
    build_tree_revision_failure_evidence,
    build_tree_revision_resolution_evidence,
)
from backend.dialogues.openclaw_identity.tree_revision_schema import (  # noqa: E402
    digest,
)

_W = 78
REPORT_VERSION = "openclaw_tree_evidence_report_v1"


def _flag(argv, name, default=""):
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return str(argv[index + 1]).strip()
    return default


def _flags(argv, name):
    values = []
    for index, value in enumerate(argv[:-1]):
        if value == name:
            cleaned = str(argv[index + 1]).strip()
            if cleaned:
                values.append(cleaned)
    return values


def _load_report(path: pathlib.Path):
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"tree evidence report {path} is unreadable") from exc
    if not isinstance(report, dict):
        raise ValueError("tree evidence report must be a JSON object")
    if report.get("schema_version") != REPORT_VERSION:
        raise ValueError(
            f"tree evidence report must use schema_version {REPORT_VERSION!r}")
    supplied = str(report.get("report_digest", ""))
    expected = digest({key: value for key, value in report.items()
                       if key != "report_digest"})
    if supplied != expected:
        raise ValueError("tree evidence report digest mismatch")
    observations = {}
    for record in report.get("observations", []):
        observation = TreeRevisionObservation.from_record(record)
        observations[observation.observation_digest] = observation
    return observations


def _pick(observations, digests, *, label):
    if not digests:
        raise ValueError(f"attestation requires at least one --{label} digest")
    if len(set(digests)) != len(digests):
        raise ValueError(f"--{label} digests repeat")
    picked = []
    for value in digests:
        if value not in observations:
            raise ValueError(
                f"--{label} digest {value[:16]}... is not in the report")
        picked.append(observations[value])
    return picked


def main(argv=None, env=None) -> int:
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env

    print("=" * _W)
    print("  OPENCLAW TREE EVIDENCE ATTESTATION - a named human vouches;")
    print("  the strict builders re-validate; only evidence is registered.")
    print("=" * _W)
    try:
        agent_id = str(argv[1]).strip() if len(argv) > 1 and \
            not str(argv[1]).startswith("--") else ""
        if not agent_id:
            raise ValueError(
                "usage: openclaw_attest_tree_evidence.py <agent_id> "
                "--report <report.json> --kind failure|resolution ...")
        verified_by = _flag(argv, "--verified-by")
        if not verified_by:
            raise ValueError(
                "attestation requires a named verifier (--verified-by)")
        if verified_by.casefold() == agent_id.casefold():
            raise ValueError(
                "an agent cannot attest its own tree evidence")
        verification_reference = _flag(argv, "--verification-reference")
        if not verification_reference:
            raise ValueError(
                "attestation requires --verification-reference")
        kind = _flag(argv, "--kind")
        if kind not in ("failure", "resolution"):
            raise ValueError("--kind must be failure or resolution")
        pattern_key = _flag(argv, "--pattern-key")
        weakness = _flag(argv, "--weakness")
        if not pattern_key or not weakness:
            raise ValueError(
                "attestation requires --pattern-key and --weakness "
                "(curator inputs, never invented by the system)")
        report_path = _flag(argv, "--report")
        if not report_path:
            raise ValueError("attestation requires --report <report.json>")
        observations = _load_report(pathlib.Path(report_path))
        observed_on = str(env.get("CED_ATTEST_DATE", "")).strip()

        if kind == "failure":
            picked = _pick(observations, _flags(argv, "--observation"),
                           label="observation")
            selection_digest = digest(sorted(
                item.observation_digest for item in picked))
            reference = (f"tree/{agent_id}/failure/"
                         f"{selection_digest[:12]}")
            evidence = build_tree_revision_failure_evidence(
                picked,
                reference=reference,
                agent_id=agent_id,
                pattern_key=pattern_key,
                weakness=weakness,
                verified_by=verified_by,
                verification_reference=verification_reference,
                observed_on=observed_on,
            )
        else:
            before = _pick(observations, _flags(argv, "--before"),
                           label="before")
            after = _pick(observations, _flags(argv, "--after"),
                          label="after")
            selection_digest = digest({
                "before": sorted(i.observation_digest for i in before),
                "after": sorted(i.observation_digest for i in after),
            })
            reference = (f"tree/{agent_id}/resolution/"
                         f"{selection_digest[:12]}")
            evidence = build_tree_revision_resolution_evidence(
                before, after,
                reference=reference,
                agent_id=agent_id,
                pattern_key=pattern_key,
                weakness=weakness,
                verified_by=verified_by,
                verification_reference=verification_reference,
                observed_on=observed_on,
            )

        evidence_dir = env.get(
            "CED_SELF_REVISION_EVIDENCE_DIR",
            str(_ROOT / "runs" / "openclaw_self_revision_evidence"))
        RevisionEvidenceRegistry(evidence_dir).register(evidence)
    except ValueError as exc:
        print(f"  REFUSED: {exc}")
        print("=" * _W)
        return 1

    print(f"  agent       : {agent_id}")
    print(f"  kind        : {kind}")
    print(f"  verified by : {verified_by}")
    print(f"  evidence    : {evidence.reference}")
    print("-" * _W)
    print("  Nothing was proposed, approved, or applied. The governed")
    print("  self-revision lifecycle still owns every next step.")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
