"""Build bounded self-review artifacts for one agent identity.

This command does not call a provider and does not mutate identity. It creates
the safe input package that a future explicit self-review task may give to the
agent:

    <agent>.snapshot.json     machine-readable bounded state
    <agent>.summary.md        operator-readable summary
    <agent>.instruction.txt   exact proposal-only task contract

Usage:
    python scripts/openclaw_self_review.py local_apprentice_001

Environment:
    CED_IDENTITY_DIR                    identity profiles
    CED_SELF_REVISION_DIR               proposal lifecycle registry
    CED_SELF_REVISION_EVIDENCE_DIR      trusted immutable evidence registry
    CED_SELF_REVISION_EVIDENCE          legacy manifest JSON (optional fallback)
    CED_SELF_REVIEW_DIR                 output artifacts
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_identity import (                       # noqa: E402
    IdentityRegistry,
    RevisionEvidenceRegistry,
    StrictSelfRevisionRegistry,
    assert_revision_state_consistent,
    build_self_review_snapshot,
    build_self_revision_instruction,
    proposal_from_record,
    render_self_review_summary,
)

_W = 78
_PENDING_STATUSES = frozenset({
    "submitted",
    "evaluated_passed",
    "evaluated_failed",
    "approved",
    "probationary",
})


def _load_legacy_manifest(path: pathlib.Path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"evidence manifest {path} is unreadable or corrupt") from exc
    if not isinstance(value, dict):
        raise ValueError("self-revision evidence manifest must be a JSON object")
    return value


def _sequence_core(value, *, field):
    raw = value or ()
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple, set)):
        raise ValueError(f"evidence {field} must be a sequence, not text")
    return tuple(sorted(str(item).strip() for item in raw))


def _evidence_core(record):
    if not isinstance(record, dict):
        raise ValueError("evidence entries must be JSON objects")
    return {
        "agent_id": str(record.get("agent_id", "")).strip(),
        "verified": record.get("verified") is True,
        "source": str(record.get("source", "")).strip(),
        "supports": _sequence_core(record.get("supports"), field="supports"),
        "value": str(record.get("value", "")).strip(),
        "verified_by": str(record.get("verified_by", "")).strip(),
        "verification_reference": str(
            record.get("verification_reference", "")).strip(),
        "observed_on": str(record.get("observed_on", "")).strip(),
        "outcomes": _sequence_core(record.get("outcomes"), field="outcomes"),
    }


def _load_evidence(
    evidence_dir: pathlib.Path,
    legacy_path: pathlib.Path,
    agent_id: str,
):
    """Prefer immutable records; merge legacy JSON only on full semantic match."""
    manifest = RevisionEvidenceRegistry(evidence_dir).manifest(agent_id)
    legacy = _load_legacy_manifest(legacy_path)
    for reference, record in legacy.items():
        if reference in manifest:
            if _evidence_core(manifest[reference]) != _evidence_core(record):
                raise ValueError(
                    f"evidence reference {reference!r} conflicts between registry "
                    "and legacy manifest")
            continue
        manifest[reference] = record
    return manifest


def _atomic_write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
            temp_path = pathlib.Path(temporary.name)
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return path


def main(argv=None, env=None) -> int:
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env
    agent_id = (
        str(argv[1]).strip() if len(argv) > 1
        else str(env.get("CED_SELF_REVIEW_AGENT", "")).strip()
    )
    if not agent_id:
        print("Usage: python scripts/openclaw_self_review.py <agent_id>")
        return 2

    identity_dir = pathlib.Path(env.get(
        "CED_IDENTITY_DIR", str(_ROOT / "runs" / "openclaw_identity")))
    revision_dir = pathlib.Path(env.get(
        "CED_SELF_REVISION_DIR",
        str(_ROOT / "runs" / "openclaw_self_revisions"),
    ))
    evidence_dir = pathlib.Path(env.get(
        "CED_SELF_REVISION_EVIDENCE_DIR",
        str(_ROOT / "runs" / "openclaw_self_revision_evidence"),
    ))
    legacy_evidence_path = pathlib.Path(env.get(
        "CED_SELF_REVISION_EVIDENCE",
        str(_ROOT / "runs" / "openclaw_self_revision_evidence.json"),
    ))
    output_dir = pathlib.Path(env.get(
        "CED_SELF_REVIEW_DIR", str(_ROOT / "runs" / "openclaw_self_review")))

    try:
        profile = IdentityRegistry(identity_dir).load_profile(agent_id)
        if profile is None:
            print(f"No identity profile found for {agent_id!r} in {identity_dir}")
            return 1
        manifest = _load_evidence(
            evidence_dir, legacy_evidence_path, agent_id)
        lifecycle_records = StrictSelfRevisionRegistry(
            revision_dir).all_records(agent_id)
        assert_revision_state_consistent(profile, lifecycle_records)
        pending = tuple(
            proposal_from_record(
                record["proposal"], expected_agent_id=agent_id)
            for record in lifecycle_records
            if record.get("status") in _PENDING_STATUSES
        )
        snapshot = build_self_review_snapshot(
            profile,
            evidence_manifest=manifest,
            pending_proposals=pending,
        )
    except ValueError as exc:
        print(f"Self-review refused: {exc}")
        return 1

    snapshot_path = _atomic_write(
        output_dir / f"{agent_id}.snapshot.json",
        json.dumps(
            snapshot.to_record(), ensure_ascii=False, sort_keys=True, indent=2
        ) + "\n",
    )
    summary_path = _atomic_write(
        output_dir / f"{agent_id}.summary.md",
        render_self_review_summary(snapshot) + "\n",
    )
    instruction_path = _atomic_write(
        output_dir / f"{agent_id}.instruction.txt",
        build_self_revision_instruction(snapshot) + "\n",
    )

    print("=" * _W)
    print("  OPENCLAW SELF-REVIEW - bounded proposal input, no authority")
    print("=" * _W)
    print(f"  agent        : {agent_id}")
    print(f"  evidence     : {len(snapshot.verified_evidence)} verified record(s)")
    print(f"  pending      : {len(snapshot.pending_proposal_ids)} proposal(s)")
    print(f"  consistency  : identity and lifecycle registries agree")
    print(f"  snapshot     : {snapshot_path}")
    print(f"  summary      : {summary_path}")
    print(f"  instruction  : {instruction_path}")
    print("-" * _W)
    print("  Nothing was activated. The agent may author a proposal from this")
    print("  bounded package; evidence validation and non-self approval still follow.")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
