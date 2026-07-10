"""Attest instrument findings into the trusted self-revision evidence registry.

THE MISSING BRIDGE of the self-revision chain: shadow runs accumulate
marker-verified comparisons on disk, but the governed self-review reads only
the immutable RevisionEvidenceRegistry - which nothing fed. This command
converts REPEATED, agent-attributed shadow section losses into
`add_known_failure` evidence records.

Attestation is a NAMED HUMAN ACT, not an automatic pipeline:

    python scripts/openclaw_attest_evidence.py local_apprentice_001 ^
        --verified-by "Your Name"

The named attester vouches that the shadow records being summarized are
genuine instrument output. The script only formats deterministically; the
strict evidence builders re-validate everything (distinct sessions, verified
attribution, no secrets), and exact re-runs are idempotent while a changed
evidence window produces a NEW record - history is append-only.

Environment:
    CED_SHADOW_DIR                    shadow records (default runs/openclaw_shadow)
    CED_SELF_REVISION_EVIDENCE_DIR    evidence registry
                                      (default runs/openclaw_self_revision_evidence)
    CED_ATTEST_DATE                   observed_on override (default: today, ISO)

No providers, no network, no keys. Nothing is proposed, approved, or applied
here - this only makes verified raw material available to the governed chain.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_memory import load_jsonl               # noqa: E402
from backend.dialogues.openclaw_identity import (                      # noqa: E402
    IDENTITY_FAILURE_REPORT_VERSION,
    RevisionEvidenceRegistry,
    build_identity_failure_evidence,
)

_W = 78
#: A pattern must repeat across at least this many DISTINCT shadow sessions.
MIN_OCCURRENCES = 2


def _section_losses(records, agent_id):
    """section -> [(session_id, source_trace)] for marker-verified losses."""
    losses = {}
    seen_sessions = set()
    for record in records:
        if record.get("shadow_run") is not True or record.get("ok") is not True:
            continue
        if str(record.get("apprentice_id", "")) != agent_id:
            continue
        session_id = str(record.get("session_id", ""))
        if not session_id or session_id in seen_sessions:
            continue                      # replays never double-count
        seen_sessions.add(session_id)
        for row in record.get("shadow_comparison", []) or []:
            if row.get("shadow_win") is True:
                continue
            section = str(row.get("section_name", "")).strip()
            if section:
                losses.setdefault(section, []).append(session_id)
    return losses


def _failure_report(agent_id, section, session_ids, *,
                    shadow_path, verified_by, observed_on):
    window_digest = hashlib.sha256(json.dumps(
        sorted(session_ids)).encode("utf-8")).hexdigest()[:12]
    observations = [
        {
            "session_id": session_id,
            "attributed_agent_id": agent_id,
            "pattern_key": f"shadow_section_loss:{section}",
            "attribution_verified": True,
            "source_trace": f"{shadow_path}#{session_id}",
        }
        for session_id in session_ids
    ]
    return {
        "schema_version": IDENTITY_FAILURE_REPORT_VERSION,
        # The evidence window is part of the reference: a NEW window makes a
        # NEW immutable record instead of colliding with the old one.
        "reference": (f"shadow/{agent_id}/section-loss/"
                      f"{section}/{window_digest}"),
        "agent_id": agent_id,
        "pattern_key": f"shadow_section_loss:{section}",
        "weakness": (f"loses the '{section}' section to the council in "
                     "marker-verified shadow comparisons"),
        "observations": observations,
        "source": "shadow-comparison-instrument",
        "verified_by": verified_by,
        "verification_reference": f"attestation/{agent_id}/{window_digest}",
        "observed_on": observed_on,
    }


def main(argv=None, env=None) -> int:
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env

    agent_id = str(argv[1]).strip() if len(argv) > 1 else ""
    verified_by = ""
    if "--verified-by" in argv:
        index = argv.index("--verified-by")
        if index + 1 < len(argv):
            verified_by = str(argv[index + 1]).strip()

    print("=" * _W)
    print("  OPENCLAW EVIDENCE ATTESTATION - a named human vouches; the")
    print("  system only formats. Nothing is proposed or applied here.")
    print("=" * _W)
    if not agent_id:
        print("  usage: openclaw_attest_evidence.py <agent_id> "
              "--verified-by \"Your Name\"")
        return 1
    if not verified_by:
        print("  REFUSED: attestation requires a named attester "
              "(--verified-by \"Your Name\").")
        return 1
    if verified_by == agent_id:
        print("  REFUSED: an agent can never attest its own evidence.")
        return 1

    shadow_path = pathlib.Path(env.get(
        "CED_SHADOW_DIR", str(_ROOT / "runs" / "openclaw_shadow"))) / \
        "shadow_records.jsonl"
    evidence_dir = env.get(
        "CED_SELF_REVISION_EVIDENCE_DIR",
        str(_ROOT / "runs" / "openclaw_self_revision_evidence"))
    observed_on = str(env.get("CED_ATTEST_DATE", "")).strip() or \
        _dt.date.today().isoformat()

    records = load_jsonl(shadow_path)
    losses = _section_losses(records, agent_id)
    registry = RevisionEvidenceRegistry(evidence_dir)

    written = []
    skipped = []
    for section in sorted(losses):
        session_ids = losses[section]
        if len(session_ids) < MIN_OCCURRENCES:
            skipped.append((section, len(session_ids)))
            continue
        report = _failure_report(
            agent_id, section, session_ids,
            shadow_path=shadow_path, verified_by=verified_by,
            observed_on=observed_on)
        evidence = build_identity_failure_evidence(
            report, min_occurrences=MIN_OCCURRENCES)
        registry.register(evidence)       # idempotent on exact repetition
        written.append(evidence.reference)

    print(f"  agent          : {agent_id}")
    print(f"  shadow records : {len(records)} read from {shadow_path}")
    print(f"  attested by    : {verified_by} (observed_on {observed_on})")
    if written:
        print(f"  evidence written ({len(written)}):")
        for reference in written:
            print(f"    {reference}")
    else:
        print("  evidence written: none")
    for section, count in skipped:
        print(f"  not attested   : '{section}' seen only {count}x "
              f"(needs {MIN_OCCURRENCES} distinct sessions)")
    print("-" * _W)
    print("  Next:")
    print(f"    python scripts/openclaw_self_review.py {agent_id}")
    print("    python scripts/openclaw_status.py")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
