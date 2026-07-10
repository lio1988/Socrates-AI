"""OpenClaw Agent Identity — governed self-revision proposals.

Agents may propose changes to their own descriptive Memory, Identity, and Soul
record, but they cannot activate those changes, approve themselves, manufacture
trusted evidence, or reach the CED runtime through this module.

Lifecycle:

    agent proposal -> strict parse -> named non-self evidence verification
    -> independent evaluation -> named non-self approval
    -> append-only profile revision with evidence provenance

The proposal and evidence manifest are untrusted inputs. The apply path
recomputes validation; caller-supplied ``passed=True`` is insufficient. Secret-
shaped text, missing provenance, hidden fields, unsafe IDs, and oversized inputs
fail closed.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from .identity_profile import AgentIdentityProfile

REVISION_TARGET_ACTIONS: Mapping[str, Tuple[str, ...]] = {
    "identity": ("add_known_failure", "resolve_known_failure"),
    "memory": ("link_stable_lesson", "unlink_stable_lesson"),
    "soul": ("add_principle", "retire_principle"),
}

_PROPOSAL_FIELDS = {
    "proposal_id", "agent_id", "proposed_by", "target", "action", "value",
    "reason", "evidence_references", "risk", "status",
}
_REVISION_ENTRY_FIELDS = {
    "entry_type", "proposal_id", "target", "action", "value", "proposed_by",
    "reason", "risk", "evidence_support", "evidence_references",
    "evidence_verifiers", "verification_references", "evidence_manifest_digest",
    "approved_by", "approved_on", "approval_reference",
}
_PROPOSAL_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_LESSON_ID_RE = re.compile(r"^LESSON-[A-Za-z0-9._-]+$")
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
_MAX_VALUE_LENGTH = 500
_MAX_REASON_LENGTH = 2000
_MAX_RISK_LENGTH = 2000
_MAX_EVIDENCE_REFERENCES = 64


def _clean_text(value: Any, *, field: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise ValueError(f"{field} contains control characters")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                f"{field} contains secret-shaped data matching {pattern.pattern!r}")
    return text


def _clean_optional_text(value: Any, *, field: str, maximum: int) -> str:
    text = str(value or "").strip()
    return _clean_text(text, field=field, maximum=maximum) if text else ""


def _clean_sequence(
    values: Iterable[Any],
    *,
    field: str,
    maximum_entries: int,
    maximum_text: int,
    require_nonempty: bool = True,
    deduplicate: bool = False,
) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field} must be a sequence, not text")
    cleaned = []
    seen = set()
    for value in values:
        item = _clean_text(value, field=field, maximum=maximum_text)
        if deduplicate and item in seen:
            continue
        cleaned.append(item)
        seen.add(item)
    if require_nonempty and not cleaned:
        raise ValueError(f"{field} requires at least one entry")
    if len(cleaned) > maximum_entries:
        raise ValueError(f"{field} exceeds {maximum_entries} entries")
    return tuple(cleaned)


def _canonical_digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("self-revision evidence must be canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _support_key(target: str, action: str) -> str:
    return f"{target}:{action}"


def _clean_references(values: Iterable[Any]) -> Tuple[str, ...]:
    return _clean_sequence(
        values,
        field="evidence reference",
        maximum_entries=_MAX_EVIDENCE_REFERENCES,
        maximum_text=256,
        deduplicate=True,
    )


@dataclass(frozen=True)
class SelfRevisionProposal:
    """Untrusted, reviewable proposal authored by an agent about itself."""

    proposal_id: str
    agent_id: str
    proposed_by: str
    target: str
    action: str
    value: str
    reason: str
    evidence_references: Tuple[str, ...]
    risk: str
    status: str = "proposed"

    def __post_init__(self) -> None:
        proposal_id = _clean_text(
            self.proposal_id, field="proposal_id", maximum=96)
        if not _PROPOSAL_ID_RE.fullmatch(proposal_id):
            raise ValueError("proposal_id must be filesystem-safe")
        agent_id = _clean_text(self.agent_id, field="agent_id", maximum=128)
        if not _AGENT_ID_RE.fullmatch(agent_id):
            raise ValueError("agent_id must be filesystem-safe")
        proposed_by = _clean_text(
            self.proposed_by, field="proposed_by", maximum=128)
        if proposed_by != agent_id:
            raise ValueError(
                "a self-revision proposal must be authored by the same agent")
        target = _clean_text(self.target, field="target", maximum=32)
        action = _clean_text(self.action, field="action", maximum=64)
        if target not in REVISION_TARGET_ACTIONS:
            raise ValueError(f"unknown self-revision target {target!r}")
        if action not in REVISION_TARGET_ACTIONS[target]:
            raise ValueError(
                f"action {action!r} is not valid for target {target!r}")
        value = _clean_text(
            self.value, field="value", maximum=_MAX_VALUE_LENGTH)
        if target == "memory" and not _LESSON_ID_RE.fullmatch(value):
            raise ValueError(
                "memory self-revisions must reference a LESSON-* id")
        reason = _clean_text(
            self.reason, field="reason", maximum=_MAX_REASON_LENGTH)
        risk = _clean_text(self.risk, field="risk", maximum=_MAX_RISK_LENGTH)
        refs = _clean_references(self.evidence_references)
        if self.status != "proposed":
            raise ValueError("agent self-revisions enter only as status='proposed'")

        object.__setattr__(self, "proposal_id", proposal_id)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "proposed_by", proposed_by)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "risk", risk)
        object.__setattr__(self, "evidence_references", refs)

    def to_record(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "proposed_by": self.proposed_by,
            "target": self.target,
            "action": self.action,
            "value": self.value,
            "reason": self.reason,
            "evidence_references": list(self.evidence_references),
            "risk": self.risk,
            "status": self.status,
        }


@dataclass(frozen=True)
class RevisionEvaluation:
    """A recommendation, never an activation."""

    proposal_id: str
    passed: bool
    reasons: Tuple[str, ...]
    evidence_used: Tuple[str, ...]


def proposal_from_record(
    record: Mapping[str, Any],
    *,
    expected_agent_id: str = "",
) -> SelfRevisionProposal:
    """Parse untrusted agent output into the exact strict proposal schema."""
    if not isinstance(record, Mapping):
        raise ValueError("self-revision proposal must be a mapping")
    if set(record) != _PROPOSAL_FIELDS:
        raise ValueError(
            "self-revision proposal contains missing or unknown fields: "
            f"{sorted(set(record) ^ _PROPOSAL_FIELDS)}")
    raw_references = record.get("evidence_references") or ()
    if isinstance(raw_references, (str, bytes)):
        raise ValueError("evidence_references must be a sequence, not text")
    proposal = SelfRevisionProposal(
        proposal_id=record.get("proposal_id", ""),
        agent_id=record.get("agent_id", ""),
        proposed_by=record.get("proposed_by", ""),
        target=record.get("target", ""),
        action=record.get("action", ""),
        value=record.get("value", ""),
        reason=record.get("reason", ""),
        evidence_references=tuple(raw_references),
        risk=record.get("risk", ""),
        status=record.get("status", ""),
    )
    if expected_agent_id and proposal.agent_id != expected_agent_id:
        raise ValueError(
            "self-revision proposal agent_id does not match the reviewed seat")
    return proposal


def _evidence_provenance(
    proposal: SelfRevisionProposal,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
) -> Tuple[Tuple[str, ...], Tuple[str, ...], str]:
    records = []
    verifiers = []
    verification_references = []
    for reference in proposal.evidence_references:
        evidence = evidence_manifest[reference]
        verifier = _clean_text(
            evidence.get("verified_by", ""),
            field="evidence verified_by",
            maximum=128,
        )
        if verifier == proposal.agent_id:
            raise ValueError("an agent cannot verify its own self-revision evidence")
        verification_reference = _clean_text(
            evidence.get("verification_reference", ""),
            field="evidence verification_reference",
            maximum=512,
        )
        verifiers.append(verifier)
        verification_references.append(verification_reference)
        records.append({
            "reference": reference,
            "record": dict(evidence),
        })
    return (
        tuple(verifiers),
        tuple(verification_references),
        _canonical_digest(records),
    )


def evaluate_self_revision(
    proposal: SelfRevisionProposal,
    *,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
    stable_lesson_ids: Iterable[str] = (),
) -> RevisionEvaluation:
    """Verify evidence ownership, provenance, action, and value relevance."""
    if not isinstance(evidence_manifest, Mapping):
        raise ValueError("evidence_manifest must be a mapping")
    if isinstance(stable_lesson_ids, (str, bytes)):
        raise ValueError("stable_lesson_ids must be a sequence, not text")

    support_key = _support_key(proposal.target, proposal.action)
    reasons = []
    matched = []

    for reference in proposal.evidence_references:
        evidence = evidence_manifest.get(reference)
        if not isinstance(evidence, Mapping):
            reasons.append(f"missing evidence reference: {reference}")
            continue
        if evidence.get("verified") is not True:
            reasons.append(f"evidence is not verified: {reference}")
            continue
        if str(evidence.get("agent_id", "")).strip() != proposal.agent_id:
            reasons.append(f"evidence belongs to another agent: {reference}")
            continue
        try:
            _clean_text(
                evidence.get("source", ""),
                field="evidence source",
                maximum=512,
            )
        except ValueError:
            reasons.append(f"evidence has no valid auditable source: {reference}")
            continue
        verifier = str(evidence.get("verified_by", "")).strip()
        if not verifier:
            reasons.append(f"evidence has no named verifier: {reference}")
            continue
        if verifier == proposal.agent_id:
            reasons.append(f"evidence was self-verified by the agent: {reference}")
            continue
        try:
            _clean_text(
                verifier, field="evidence verified_by", maximum=128)
            _clean_text(
                evidence.get("verification_reference", ""),
                field="evidence verification_reference",
                maximum=512,
            )
        except ValueError:
            reasons.append(f"evidence has invalid verification provenance: {reference}")
            continue
        supports = evidence.get("supports") or ()
        if not isinstance(supports, (list, tuple, set, frozenset)):
            reasons.append(f"evidence supports field is invalid: {reference}")
            continue
        try:
            normalized_supports = {
                _clean_text(item, field="evidence support", maximum=128)
                for item in supports
            }
        except ValueError:
            reasons.append(f"evidence supports field is invalid: {reference}")
            continue
        if support_key not in normalized_supports:
            reasons.append(
                f"evidence does not support {support_key}: {reference}")
            continue
        try:
            evidence_value = _clean_text(
                evidence.get("value", ""), field="evidence value", maximum=500)
        except ValueError:
            reasons.append(f"evidence value is invalid: {reference}")
            continue
        if evidence_value != proposal.value:
            reasons.append(
                f"evidence value does not match proposal value: {reference}")
            continue
        matched.append(reference)

    stable = {
        str(lesson_id).strip()
        for lesson_id in stable_lesson_ids
        if str(lesson_id).strip()
    }
    if (proposal.target == "memory"
            and proposal.action == "link_stable_lesson"
            and proposal.value not in stable):
        reasons.append(
            f"lesson {proposal.value!r} is not in the stable/verified catalogue")

    passed = not reasons and tuple(matched) == proposal.evidence_references
    if passed:
        reasons.append(
            f"{len(matched)} action-specific evidence record(s) verified")
    return RevisionEvaluation(
        proposal_id=proposal.proposal_id,
        passed=passed,
        reasons=tuple(reasons),
        evidence_used=tuple(matched),
    )


def _apply_action(
    known_failures: Sequence[str],
    stable_lessons: Sequence[str],
    soul_principles: Sequence[str],
    *,
    target: str,
    action: str,
    value: str,
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    failures = list(known_failures)
    lessons = list(stable_lessons)
    principles = list(soul_principles)

    if target == "identity" and action == "add_known_failure":
        if value in failures:
            raise ValueError("known failure is already recorded")
        failures.append(value)
    elif target == "identity" and action == "resolve_known_failure":
        if value not in failures:
            raise ValueError("cannot resolve a known failure that is not recorded")
        failures.remove(value)
    elif target == "memory" and action == "link_stable_lesson":
        if value in lessons:
            raise ValueError("stable lesson is already linked")
        lessons.append(value)
    elif target == "memory" and action == "unlink_stable_lesson":
        if value not in lessons:
            raise ValueError("cannot unlink a stable lesson that is not linked")
        lessons.remove(value)
    elif target == "soul" and action == "add_principle":
        if value in principles:
            raise ValueError("soul principle is already recorded")
        principles.append(value)
    elif target == "soul" and action == "retire_principle":
        if value not in principles:
            raise ValueError("cannot retire a soul principle that is not recorded")
        principles.remove(value)
    else:
        raise ValueError(
            f"unsupported self-revision operation {target!r}/{action!r}")

    return tuple(failures), tuple(lessons), tuple(principles)


def approve_and_apply_self_revision(
    profile: AgentIdentityProfile,
    proposal: SelfRevisionProposal,
    evaluation: RevisionEvaluation,
    *,
    evidence_manifest: Mapping[str, Mapping[str, Any]],
    approved_by: str,
    approval_reference: str,
    stable_lesson_ids: Iterable[str] = (),
    approved_on: str = "",
) -> AgentIdentityProfile:
    """Return a new profile after evidence revalidation and non-self approval."""
    if proposal.agent_id != profile.agent_id:
        raise ValueError("proposal agent_id does not match the identity profile")
    if any(entry.get("proposal_id") == proposal.proposal_id
           for entry in profile.revision_history):
        raise ValueError("self-revision proposal_id has already been applied")
    if evaluation.proposal_id != proposal.proposal_id:
        raise ValueError("revision evaluation does not match the proposal")
    if not evaluation.passed:
        raise ValueError("self-revision requires a passing evaluation")

    verified = evaluate_self_revision(
        proposal,
        evidence_manifest=evidence_manifest,
        stable_lesson_ids=stable_lesson_ids,
    )
    if not verified.passed:
        raise ValueError(
            "self-revision evidence does not pass independent re-evaluation: "
            f"{verified.reasons[0]}")
    if tuple(evaluation.evidence_used) != tuple(verified.evidence_used):
        raise ValueError(
            "supplied revision evaluation does not match independently verified evidence")

    approver = _clean_text(approved_by, field="approved_by", maximum=128)
    if approver == profile.agent_id:
        raise ValueError("an agent can never approve its own self-revision")
    approval_ref = _clean_text(
        approval_reference, field="approval_reference", maximum=512)
    approval_date = _clean_optional_text(
        approved_on, field="approved_on", maximum=64)
    verifiers, verification_refs, evidence_digest = _evidence_provenance(
        proposal, evidence_manifest)

    failures, lessons, principles = _apply_action(
        profile.known_failures,
        profile.stable_lessons,
        profile.soul_principles,
        target=proposal.target,
        action=proposal.action,
        value=proposal.value,
    )
    entry = {
        "entry_type": "self_revision",
        "proposal_id": proposal.proposal_id,
        "target": proposal.target,
        "action": proposal.action,
        "value": proposal.value,
        "proposed_by": proposal.proposed_by,
        "reason": proposal.reason,
        "risk": proposal.risk,
        "evidence_support": _support_key(proposal.target, proposal.action),
        "evidence_references": list(verified.evidence_used),
        "evidence_verifiers": list(verifiers),
        "verification_references": list(verification_refs),
        "evidence_manifest_digest": evidence_digest,
        "approved_by": approver,
        "approved_on": approval_date,
        "approval_reference": approval_ref,
    }
    return dataclasses.replace(
        profile,
        known_failures=failures,
        stable_lessons=lessons,
        soul_principles=principles,
        revision_history=profile.revision_history + (entry,),
    )


def replay_revision_entry(
    known_failures: Sequence[str],
    stable_lessons: Sequence[str],
    soul_principles: Sequence[str],
    entry: Mapping[str, Any],
    *,
    agent_id: str,
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    """Validate and replay one stored revision entry for registry integrity."""
    if not isinstance(entry, Mapping):
        raise ValueError("revision history entry must be a mapping")
    if set(entry) != _REVISION_ENTRY_FIELDS:
        raise ValueError(
            "revision history entry contains missing or unknown fields")
    if entry.get("entry_type") != "self_revision":
        raise ValueError("revision history entry must be type 'self_revision'")
    raw_references = entry["evidence_references"]
    if isinstance(raw_references, (str, bytes)):
        raise ValueError("evidence_references must be a sequence, not text")

    proposal = SelfRevisionProposal(
        proposal_id=entry["proposal_id"],
        agent_id=agent_id,
        proposed_by=entry["proposed_by"],
        target=entry["target"],
        action=entry["action"],
        value=entry["value"],
        reason=entry["reason"],
        evidence_references=tuple(raw_references or ()),
        risk=entry["risk"],
    )
    expected_support = _support_key(proposal.target, proposal.action)
    if str(entry["evidence_support"]).strip() != expected_support:
        raise ValueError("revision evidence_support does not match its action")

    verifiers = _clean_sequence(
        entry["evidence_verifiers"],
        field="evidence verifier",
        maximum_entries=_MAX_EVIDENCE_REFERENCES,
        maximum_text=128,
    )
    verification_refs = _clean_sequence(
        entry["verification_references"],
        field="verification reference",
        maximum_entries=_MAX_EVIDENCE_REFERENCES,
        maximum_text=512,
    )
    if len(verifiers) != len(proposal.evidence_references) or \
            len(verification_refs) != len(proposal.evidence_references):
        raise ValueError(
            "revision evidence provenance count does not match evidence references")
    if any(verifier == agent_id for verifier in verifiers):
        raise ValueError("an agent cannot verify its own self-revision evidence")
    digest = str(entry["evidence_manifest_digest"])
    if not _HEX64_RE.fullmatch(digest):
        raise ValueError("revision evidence_manifest_digest is invalid")

    approver = _clean_text(entry["approved_by"], field="approved_by", maximum=128)
    if approver == agent_id:
        raise ValueError("an agent cannot approve its own self-revision")
    _clean_optional_text(entry["approved_on"], field="approved_on", maximum=64)
    _clean_text(
        entry["approval_reference"],
        field="approval_reference",
        maximum=512,
    )
    return _apply_action(
        known_failures,
        stable_lessons,
        soul_principles,
        target=proposal.target,
        action=proposal.action,
        value=proposal.value,
    )
