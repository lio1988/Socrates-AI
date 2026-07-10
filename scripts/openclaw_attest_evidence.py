"""Attest instrument findings into the trusted self-revision evidence registry.

Attestation is always a NAMED HUMAN ACT. The command never proposes, approves,
or applies a self-revision; it only converts explicit instrument/review facts
into immutable evidence records through the strict builders.

Backward-compatible failure mode:

    python scripts/openclaw_attest_evidence.py local_apprentice_001 ^
        --verified-by "Your Name"

Explicit resolution mode (same section weakness, matched adjacent windows):

    python scripts/openclaw_attest_evidence.py local_apprentice_001 ^
        --mode resolution --section blind_spots --window 2 ^
        --verified-by "Your Name"

Explicit Soul constitutional review:

    python scripts/openclaw_attest_evidence.py local_apprentice_001 ^
        --mode soul --action add_principle ^
        --principle "State uncertainty before asserting a verdict." ^
        --evidence-ref shadow/... --rationale "Repeated evidence warrants it." ^
        --review-reference review/soul-001 ^
        --constitutional-review --risk-reviewed ^
        --verified-by "Your Name"

Environment:
    CED_SHADOW_DIR                    shadow records
    CED_SELF_REVISION_EVIDENCE_DIR    immutable evidence registry
    CED_ATTEST_DATE                   observed_on override (default: today, ISO)

No providers, network, keys, automatic promotion, or canonical profile writes.
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
    IDENTITY_RESOLUTION_REPORT_VERSION,
    SOUL_ATTESTATION_VERSION,
    RevisionEvidenceRegistry,
    build_identity_failure_evidence,
    build_identity_resolution_evidence,
    build_soul_attestation_evidence,
)

_W = 78
MIN_OCCURRENCES = 2
DEFAULT_RESOLUTION_WINDOW = 2


def _value(argv, name, default=""):
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        return default
    return str(argv[index + 1]).strip()


def _values(argv, name):
    values = []
    for index, value in enumerate(argv):
        if value == name and index + 1 < len(argv):
            cleaned = str(argv[index + 1]).strip()
            if cleaned:
                values.append(cleaned)
    return values


def _positive_int(value, *, field, default):
    if value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed < 2:
        raise ValueError(f"{field} must be an integer >= 2")
    return parsed


def _weakness_for_section(section):
    return (f"loses the '{section}' section to the council in "
            "marker-verified shadow comparisons")


def _valid_agent_records(records, agent_id):
    seen_sessions = set()
    for record in records:
        if record.get("shadow_run") is not True or record.get("ok") is not True:
            continue
        if str(record.get("apprentice_id", "")).strip() != agent_id:
            continue
        session_id = str(record.get("session_id", "")).strip()
        if not session_id or session_id in seen_sessions:
            continue
        seen_sessions.add(session_id)
        yield session_id, record


def _section_losses(records, agent_id):
    """section -> distinct marker-verified loss session ids."""
    losses = {}
    for session_id, record in _valid_agent_records(records, agent_id):
        for row in record.get("shadow_comparison", []) or []:
            if row.get("shadow_win") is True:
                continue
            section = str(row.get("section_name", "")).strip()
            if section:
                losses.setdefault(section, []).append(session_id)
    return losses


def _section_outcomes(records, agent_id, section):
    """Ordered distinct `(session_id, won)` values for one exact section."""
    outcomes = []
    for session_id, record in _valid_agent_records(records, agent_id):
        rows = [
            row for row in (record.get("shadow_comparison", []) or [])
            if str(row.get("section_name", "")).strip() == section
        ]
        if not rows:
            continue
        if len(rows) != 1:
            raise ValueError(
                f"session {session_id!r} contains ambiguous duplicate section rows")
        won = rows[0].get("shadow_win")
        if not isinstance(won, bool):
            raise ValueError(
                f"session {session_id!r} has non-boolean shadow_win")
        outcomes.append((session_id, won))
    return outcomes


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
        "reference": (f"shadow/{agent_id}/section-loss/"
                      f"{section}/{window_digest}"),
        "agent_id": agent_id,
        "pattern_key": f"shadow_section_loss:{section}",
        "weakness": _weakness_for_section(section),
        "observations": observations,
        "source": "shadow-comparison-instrument",
        "verified_by": verified_by,
        "verification_reference": f"attestation/{agent_id}/{window_digest}",
        "observed_on": observed_on,
    }


def _resolution_report(agent_id, section, outcomes, *, window,
                       shadow_path, verified_by, observed_on,
                       prior_evidence_reference):
    if len(outcomes) < window * 2:
        raise ValueError(
            f"resolution needs at least {window * 2} distinct section sessions")
    before = outcomes[-(window * 2):-window]
    after = outcomes[-window:]
    if not all(won is False for _, won in before):
        raise ValueError(
            "resolution before-window must contain only verified failures")
    if not all(won is True for _, won in after):
        raise ValueError(
            "resolution after-window must contain only verified wins")

    before_ids = [session_id for session_id, _ in before]
    after_ids = [session_id for session_id, _ in after]
    digest_payload = {
        "agent_id": agent_id,
        "section": section,
        "before": before_ids,
        "after": after_ids,
        "prior_evidence": prior_evidence_reference,
    }
    window_digest = hashlib.sha256(json.dumps(
        digest_payload, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()[:12]
    return {
        "schema_version": IDENTITY_RESOLUTION_REPORT_VERSION,
        "reference": (f"shadow/{agent_id}/section-resolution/"
                      f"{section}/{window_digest}"),
        "agent_id": agent_id,
        "pattern_key": f"shadow_section_loss:{section}",
        "weakness": _weakness_for_section(section),
        "before_session_ids": before_ids,
        "after_session_ids": after_ids,
        "before_failures": len(before_ids),
        "after_failures": 0,
        "matched_window": True,
        "source": "shadow-comparison-resolution-instrument",
        "verified_by": verified_by,
        "verification_reference": (
            f"attestation/{agent_id}/{window_digest};"
            f"prior={prior_evidence_reference}"
        ),
        "observed_on": observed_on,
    }


def _soul_report(agent_id, *, action, principle, evidence_references,
                 rationale, review_reference, reviewed_by, observed_on,
                 constitutional_review, risk_reviewed):
    payload = {
        "agent_id": agent_id,
        "action": action,
        "principle": principle,
        "evidence_references": sorted(evidence_references),
        "rationale": rationale,
        "review_reference": review_reference,
    }
    digest = hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()[:12]
    return {
        "schema_version": SOUL_ATTESTATION_VERSION,
        "reference": f"soul/{agent_id}/{action}/{digest}",
        "agent_id": agent_id,
        "action": action,
        "principle": principle,
        "constitutional_review": constitutional_review,
        "risk_reviewed": risk_reviewed,
        "evidence_references": list(evidence_references),
        "rationale": rationale,
        "reviewed_by": reviewed_by,
        "review_reference": review_reference,
        "observed_on": observed_on,
    }


def _attest_failures(records, registry, *, agent_id, shadow_path,
                     verified_by, observed_on):
    losses = _section_losses(records, agent_id)
    written = []
    skipped = []
    for section in sorted(losses):
        session_ids = losses[section]
        if len(session_ids) < MIN_OCCURRENCES:
            skipped.append(
                f"'{section}' seen only {len(session_ids)}x "
                f"(needs {MIN_OCCURRENCES} distinct sessions)")
            continue
        report = _failure_report(
            agent_id, section, session_ids,
            shadow_path=shadow_path,
            verified_by=verified_by,
            observed_on=observed_on,
        )
        evidence = build_identity_failure_evidence(
            report, min_occurrences=MIN_OCCURRENCES)
        registry.register(evidence)
        written.append(evidence.reference)
    return written, skipped


def _attest_resolution(records, registry, *, agent_id, section, window,
                       shadow_path, verified_by, observed_on):
    if not section:
        raise ValueError("resolution mode requires --section")
    weakness = _weakness_for_section(section)
    prior = [
        evidence for evidence in registry.all_records(agent_id)
        if evidence.value == weakness
        and evidence.supports == ("identity:add_known_failure",)
    ]
    if not prior:
        raise ValueError(
            "resolution requires an existing attested failure for the same weakness")
    outcomes = _section_outcomes(records, agent_id, section)
    report = _resolution_report(
        agent_id, section, outcomes,
        window=window,
        shadow_path=shadow_path,
        verified_by=verified_by,
        observed_on=observed_on,
        prior_evidence_reference=prior[0].reference,
    )
    evidence = build_identity_resolution_evidence(report, min_window=window)
    registry.register(evidence)
    return [evidence.reference], []


def _attest_soul(registry, *, agent_id, action, principle,
                 evidence_references, rationale, review_reference,
                 verified_by, observed_on, constitutional_review,
                 risk_reviewed):
    if action not in {"add_principle", "retire_principle"}:
        raise ValueError(
            "soul mode requires --action add_principle or retire_principle")
    if not principle:
        raise ValueError("soul mode requires --principle")
    if not rationale:
        raise ValueError("soul mode requires --rationale")
    if not review_reference:
        raise ValueError("soul mode requires --review-reference")
    if not evidence_references:
        raise ValueError("soul mode requires at least one --evidence-ref")
    if len(set(evidence_references)) != len(evidence_references):
        raise ValueError("soul evidence references must be distinct")
    if not constitutional_review:
        raise ValueError("soul mode requires --constitutional-review")
    if not risk_reviewed:
        raise ValueError("soul mode requires --risk-reviewed")

    for reference in evidence_references:
        evidence = registry.load(reference)
        if evidence is None:
            raise ValueError(f"Soul evidence reference {reference!r} does not exist")
        if evidence.agent_id != agent_id:
            raise ValueError(
                f"Soul evidence reference {reference!r} belongs to another agent")

    report = _soul_report(
        agent_id,
        action=action,
        principle=principle,
        evidence_references=evidence_references,
        rationale=rationale,
        review_reference=review_reference,
        reviewed_by=verified_by,
        observed_on=observed_on,
        constitutional_review=constitutional_review,
        risk_reviewed=risk_reviewed,
    )
    evidence = build_soul_attestation_evidence(report)
    registry.register(evidence)
    return [evidence.reference], []


def main(argv=None, env=None) -> int:
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env

    agent_id = str(argv[1]).strip() if len(argv) > 1 else ""
    verified_by = _value(argv, "--verified-by")
    mode = _value(argv, "--mode", "failure").lower()
    if mode == "resolve":
        mode = "resolution"

    print("=" * _W)
    print("  OPENCLAW EVIDENCE ATTESTATION - named human act; evidence only")
    print("=" * _W)
    if not agent_id:
        print("  usage: openclaw_attest_evidence.py <agent_id> "
              "--verified-by \"Your Name\"")
        return 1
    if not verified_by:
        print("  REFUSED: attestation requires a named attester "
              "(--verified-by \"Your Name\").")
        return 1
    if verified_by.casefold() == agent_id.casefold():
        print("  REFUSED: an agent can never attest its own evidence.")
        return 1
    if mode not in {"failure", "resolution", "soul"}:
        print(f"  REFUSED: unknown attestation mode {mode!r}.")
        return 1

    shadow_path = pathlib.Path(env.get(
        "CED_SHADOW_DIR", str(_ROOT / "runs" / "openclaw_shadow"))) / \
        "shadow_records.jsonl"
    evidence_dir = env.get(
        "CED_SELF_REVISION_EVIDENCE_DIR",
        str(_ROOT / "runs" / "openclaw_self_revision_evidence"))
    observed_on = str(env.get("CED_ATTEST_DATE", "")).strip() or \
        _dt.date.today().isoformat()
    registry = RevisionEvidenceRegistry(evidence_dir)

    try:
        if mode == "failure":
            records = load_jsonl(shadow_path)
            written, skipped = _attest_failures(
                records, registry,
                agent_id=agent_id,
                shadow_path=shadow_path,
                verified_by=verified_by,
                observed_on=observed_on,
            )
        elif mode == "resolution":
            records = load_jsonl(shadow_path)
            window = _positive_int(
                _value(argv, "--window"),
                field="resolution window",
                default=DEFAULT_RESOLUTION_WINDOW,
            )
            written, skipped = _attest_resolution(
                records, registry,
                agent_id=agent_id,
                section=_value(argv, "--section"),
                window=window,
                shadow_path=shadow_path,
                verified_by=verified_by,
                observed_on=observed_on,
            )
        else:
            written, skipped = _attest_soul(
                registry,
                agent_id=agent_id,
                action=_value(argv, "--action"),
                principle=_value(argv, "--principle"),
                evidence_references=_values(argv, "--evidence-ref"),
                rationale=_value(argv, "--rationale"),
                review_reference=_value(argv, "--review-reference"),
                verified_by=verified_by,
                observed_on=observed_on,
                constitutional_review="--constitutional-review" in argv,
                risk_reviewed="--risk-reviewed" in argv,
            )
    except ValueError as exc:
        print(f"  REFUSED: {exc}")
        print("=" * _W)
        return 1

    print(f"  mode           : {mode}")
    print(f"  agent          : {agent_id}")
    if mode != "soul":
        print(f"  shadow records : {len(records)} read from {shadow_path}")
    print(f"  attested by    : {verified_by} (observed_on {observed_on})")
    if written:
        print(f"  evidence written ({len(written)}):")
        for reference in written:
            print(f"    {reference}")
    else:
        print("  evidence written: none")
    for message in skipped:
        print(f"  not attested   : {message}")
    print("-" * _W)
    print("  Next:")
    print(f"    python scripts/openclaw_self_review.py {agent_id}")
    print("    python scripts/openclaw_review.py")
    print("    python scripts/openclaw_status.py")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
