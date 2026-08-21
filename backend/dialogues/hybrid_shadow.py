"""Append-only Hybrid v1 records for H1 observation-only shadow mode.

This module does not decide claim truth, support, eligibility, ratification, or
release. It records digests and provenance for artifacts the canonical CED has
already produced. CED and its public models remain the only runtime authority
during H1.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
import hashlib
import json
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from .models import FinalResponse, SessionState


HYBRID_SHADOW_SCHEMA_VERSION = "socrates.hybrid-shadow.h1/v1"
SHADOW_AUTHORITY = "shadow_non_authoritative"


class HybridLedgerConflict(ValueError):
    """An idempotency identity was reused with different immutable content."""


class HybridLedgerIntegrityError(ValueError):
    """A record stream failed deterministic sequence/hash-chain validation."""


class HybridRecordKind(str, Enum):
    SESSION_OBSERVED = "session.observed"
    PROVIDER_OBSERVED = "provider.observed"
    PHASE_OBSERVED = "phase.observed"
    ROLE_ASSIGNMENT_OBSERVED = "role_assignment.observed"
    TASK_OBSERVED = "task.observed"
    MOVE_OBSERVED = "move.observed"
    SECTION_DRAFT_OBSERVED = "section_draft.observed"
    MOVE_QUALITY_SCORE_OBSERVED = "move_quality_score.observed"
    SECTION_QUALITY_SCORE_OBSERVED = "section_quality_score.observed"
    ASSEMBLY_OBSERVED = "assembly.observed"
    RATIFICATION_OBSERVED = "ratification.observed"
    FINAL_RESPONSE_OBSERVED = "final_response.observed"
    # H2 quality/epistemic-support separation. Appended to this same
    # ledger on purpose: the preservation contract forbids a second
    # authority, which a parallel store would be.
    SESSION_SUPPORT_ASSESSED = "session_support.assessed"
    MOVE_SUPPORT_ASSESSED = "move_support.assessed"


class HybridShadowRecord(BaseModel):
    """One immutable H1 observation envelope.

    ``idempotency_key`` identifies the canonical subject slot; ``record_id``
    also commits to the payload and previous record. Neither is random.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[HYBRID_SHADOW_SCHEMA_VERSION] = HYBRID_SHADOW_SCHEMA_VERSION
    record_id: str
    idempotency_key: str
    session_id: str
    sequence: int = Field(ge=1)
    previous_record_id: Optional[str] = None
    kind: HybridRecordKind
    subject_ref: str
    authority: Literal[SHADOW_AUTHORITY] = SHADOW_AUTHORITY
    payload_sha256: str
    payload: Dict[str, Any]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest(value: Any) -> str:
    return _sha256_text(_canonical_json(value))


def _content_digest(value: Any) -> str:
    """Digest model output without retaining raw provider prose."""
    try:
        canonical = _canonical_json(value)
    except (TypeError, ValueError):
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    return _sha256_text(canonical)


def _stable_ref(prefix: str, *parts: Any) -> str:
    return f"{prefix}:{_digest(list(parts))[:32]}"


class HybridEpistemicLedger:
    """In-memory append-only H1 ledger with per-session sequence ownership.

    Identical appends are idempotent. Reusing the same subject identity with a
    different payload is an integrity conflict and never overwrites history.
    Reads are deep copies so callers cannot mutate retained records.
    """

    def __init__(self) -> None:
        self._records: Dict[str, List[HybridShadowRecord]] = defaultdict(list)
        self._by_key: Dict[Tuple[str, str], HybridShadowRecord] = {}

    @staticmethod
    def _idempotency_key(
        session_id: str,
        kind: HybridRecordKind,
        subject_ref: str,
    ) -> str:
        return "hybrid_key_" + _digest({
            "schema_version": HYBRID_SHADOW_SCHEMA_VERSION,
            "session_id": session_id,
            "kind": kind.value,
            "subject_ref": subject_ref,
        })

    @staticmethod
    def _record_id(
        *,
        idempotency_key: str,
        sequence: int,
        previous_record_id: Optional[str],
        payload_sha256: str,
    ) -> str:
        return "hybrid_record_" + _digest({
            "idempotency_key": idempotency_key,
            "sequence": sequence,
            "previous_record_id": previous_record_id,
            "payload_sha256": payload_sha256,
        })

    def append(
        self,
        *,
        session_id: str,
        kind: HybridRecordKind,
        subject_ref: str,
        payload: Mapping[str, Any],
    ) -> HybridShadowRecord:
        session_id = str(session_id).strip()
        subject_ref = str(subject_ref).strip()
        if not session_id:
            raise ValueError("session_id is required")
        if not subject_ref:
            raise ValueError("subject_ref is required")
        kind = HybridRecordKind(kind)

        # Round-trip through strict JSON to retain a detached immutable snapshot.
        payload_snapshot = json.loads(_canonical_json(dict(payload)))
        payload_sha256 = _digest(payload_snapshot)
        idempotency_key = self._idempotency_key(session_id, kind, subject_ref)
        existing = self._by_key.get((session_id, idempotency_key))
        if existing is not None:
            if existing.payload_sha256 != payload_sha256:
                raise HybridLedgerConflict(
                    "Hybrid shadow idempotency identity conflicts with retained content"
                )
            return existing.model_copy(deep=True)

        stream = self._records[session_id]
        sequence = len(stream) + 1
        previous_record_id = stream[-1].record_id if stream else None
        record_id = self._record_id(
            idempotency_key=idempotency_key,
            sequence=sequence,
            previous_record_id=previous_record_id,
            payload_sha256=payload_sha256,
        )
        record = HybridShadowRecord(
            record_id=record_id,
            idempotency_key=idempotency_key,
            session_id=session_id,
            sequence=sequence,
            previous_record_id=previous_record_id,
            kind=kind,
            subject_ref=subject_ref,
            payload_sha256=payload_sha256,
            payload=payload_snapshot,
        )
        stream.append(record)
        self._by_key[(session_id, idempotency_key)] = record
        return record.model_copy(deep=True)

    def records(self, session_id: str) -> List[HybridShadowRecord]:
        return [record.model_copy(deep=True)
                for record in self._records.get(session_id, ())]

    def replay(self, session_id: str) -> List[HybridShadowRecord]:
        records = self.records(session_id)
        previous: Optional[str] = None
        for expected_sequence, record in enumerate(records, start=1):
            payload_sha256 = _digest(record.payload)
            idempotency_key = self._idempotency_key(
                record.session_id, record.kind, record.subject_ref,
            )
            record_id = self._record_id(
                idempotency_key=idempotency_key,
                sequence=expected_sequence,
                previous_record_id=previous,
                payload_sha256=payload_sha256,
            )
            if (
                record.session_id != session_id
                or record.sequence != expected_sequence
                or record.previous_record_id != previous
                or record.payload_sha256 != payload_sha256
                or record.idempotency_key != idempotency_key
                or record.record_id != record_id
            ):
                raise HybridLedgerIntegrityError(
                    f"Hybrid shadow stream integrity failed at sequence {expected_sequence}"
                )
            previous = record.record_id
        return records

    @classmethod
    def from_records(
        cls,
        records: Iterable[HybridShadowRecord],
    ) -> "HybridEpistemicLedger":
        ledger = cls()
        for source in records:
            source = HybridShadowRecord.model_validate(source)
            appended = ledger.append(
                session_id=source.session_id,
                kind=source.kind,
                subject_ref=source.subject_ref,
                payload=source.payload,
            )
            if appended != source:
                raise HybridLedgerIntegrityError(
                    f"Hybrid shadow replay mismatch at sequence {source.sequence}"
                )
        for session_id in list(ledger._records):
            ledger.replay(session_id)
        return ledger


class HybridShadowObserver:
    """Post-finalization projection of canonical artifacts into the H1 ledger."""

    def __init__(self, ledger: HybridEpistemicLedger) -> None:
        self.ledger = ledger

    def _append(
        self,
        state: SessionState,
        kind: HybridRecordKind,
        subject_ref: str,
        payload: Mapping[str, Any],
    ) -> HybridShadowRecord:
        return self.ledger.append(
            session_id=state.session_id,
            kind=kind,
            subject_ref=subject_ref,
            payload=payload,
        )

    def capture_session(
        self,
        state: SessionState,
        final: FinalResponse,
        *,
        provider_catalog: Iterable[Mapping[str, Any]] = (),
    ) -> List[HybridShadowRecord]:
        """Observe a completed canonical session without mutating either model."""
        provider_rows: Dict[str, Dict[str, Any]] = {}
        for raw in provider_catalog:
            provider_id = str(raw.get("provider_id") or raw.get("seat") or "").strip()
            if not provider_id:
                continue
            provider_rows[provider_id] = {
                "provider_id": provider_id,
                "model": str(raw.get("model") or "Unknown"),
                "company": str(raw.get("company") or "Unknown"),
            }

        self._append(
            state,
            HybridRecordKind.SESSION_OBSERVED,
            f"session:{state.session_id}",
            {
                "question_sha256": _sha256_text(state.question),
                "final_phase": state.phase.value,
                "round_number": state.round_number,
                "agent_count": len(state.agent_states),
                "move_count": len(state.moves),
                "task_count": len(state.task_log),
                "shadow_mode": True,
            },
        )

        for provider_id in sorted(provider_rows):
            self._append(
                state,
                HybridRecordKind.PROVIDER_OBSERVED,
                f"provider:{provider_id}",
                provider_rows[provider_id],
            )

        for ordinal, phase in enumerate(state.phase_history):
            self._append(
                state,
                HybridRecordKind.PHASE_OBSERVED,
                f"phase:{ordinal}:{phase.value}",
                {"phase": phase.value, "ordinal": ordinal},
            )

        for ordinal, assignment in enumerate(state.role_history):
            payload = {
                "phase": str(assignment.get("phase") or ""),
                "round_index": int(assignment.get("round_index") or 0),
                "agent_id": str(assignment.get("agent_id") or ""),
                "role": str(assignment.get("role") or ""),
            }
            self._append(
                state,
                HybridRecordKind.ROLE_ASSIGNMENT_OBSERVED,
                f"role:{ordinal}:{payload['phase']}:{payload['agent_id']}",
                payload,
            )

        task_occurrences: Dict[str, int] = defaultdict(int)
        for task in state.task_log:
            task_kind = task.task_kind.value if task.task_kind else None
            base = _stable_ref(
                "task",
                task.phase.value,
                task.round_index,
                task.agent_id,
                task_kind,
                task.slot_index,
                task.attempt_index,
                task.context_hash,
            )
            occurrence = task_occurrences[base]
            task_occurrences[base] += 1
            subject_ref = f"{base}:{occurrence}"
            payload = {
                "phase": task.phase.value,
                "round_index": task.round_index,
                "agent_id": task.agent_id,
                "assigned_role": task.assigned_role.value,
                "task_kind": task_kind,
                "slot_index": task.slot_index,
                "attempt_index": task.attempt_index,
                "schema_name": task.schema_name,
                "context_hash": task.context_hash,
                "provider_id": task.provider_id,
                "provider_status": (task.provider_status.value
                                    if task.provider_status else None),
                # Some auxiliary scoring-task move IDs remain random in the H0
                # compatibility model. H1 uses a deterministic shadow reference
                # without changing that canonical field (byte parity is locked).
                "move_ref": (_stable_ref("task_output", subject_ref)
                             if task.move_id else None),
            }
            self._append(
                state, HybridRecordKind.TASK_OBSERVED, subject_ref, payload,
            )

        for move in state.moves:
            provider = provider_rows.get(move.provider_id or "", {})
            self._append(
                state,
                HybridRecordKind.MOVE_OBSERVED,
                f"move:{move.move_id}",
                {
                    "move_ref": move.move_id,
                    "agent_id": move.agent_id,
                    "role": move.role.value,
                    "phase": move.phase.value,
                    "task_kind": move.task_kind.value if move.task_kind else None,
                    "slot_index": move.slot_index,
                    "attempt_index": move.attempt_index,
                    "provider_id": move.provider_id,
                    "model": provider.get("model"),
                    "confidence": move.confidence,
                    "epistemic_markers": [m.value for m in move.epistemic_markers],
                    "content_sha256": _content_digest(move.content),
                    "semantic_authority": "unassessed_model_output",
                },
            )

        draft_refs: Dict[str, str] = {}
        for draft in state.section_drafts:
            candidate_ref = _stable_ref(
                "candidate", state.session_id, draft.move_id, draft.author_agent_id,
            )
            draft_refs[draft.draft_id] = candidate_ref
            provider = provider_rows.get(draft.provider_id or "", {})
            self._append(
                state,
                HybridRecordKind.SECTION_DRAFT_OBSERVED,
                candidate_ref,
                {
                    "candidate_ref": candidate_ref,
                    "move_ref": draft.move_id,
                    "author_agent_id": draft.author_agent_id,
                    "provider_id": draft.provider_id,
                    "model": provider.get("model"),
                    "section_sha256": {
                        name.value: _sha256_text(draft.section_text(name))
                        for name in draft.sections()
                    },
                    "semantic_authority": "unassessed_candidate",
                },
            )

        score_occurrences: Dict[str, int] = defaultdict(int)
        for score in state.micro_scores:
            base = _stable_ref(
                "move_quality",
                score.output_id,
                score.phase.value,
                score.author_agent_id,
                score.voter_agent_id,
                score.provider_id,
            )
            occurrence = score_occurrences[base]
            score_occurrences[base] += 1
            self._append(
                state,
                HybridRecordKind.MOVE_QUALITY_SCORE_OBSERVED,
                f"{base}:{occurrence}",
                {
                    "output_ref": score.output_id,
                    "phase": score.phase.value,
                    "author_agent_id": score.author_agent_id,
                    "voter_agent_id": score.voter_agent_id,
                    "provider_id": score.provider_id,
                    "score_breakdown": score.score_breakdown.model_dump(mode="json"),
                    "overall_score": score.overall_score,
                    "confidence": score.confidence,
                    "penalty_flags": [flag.value for flag in score.penalty_flags],
                    "provider_status": score.provider_status.value,
                    "signal_class": "quality_only",
                },
            )

        section_score_occurrences: Dict[str, int] = defaultdict(int)
        for card in state.draft_scorecards:
            for score in card.section_scores:
                candidate_ref = draft_refs.get(
                    score.draft_id,
                    _stable_ref("candidate_unknown", state.session_id, score.draft_id),
                )
                base = _stable_ref(
                    "section_quality",
                    candidate_ref,
                    score.section_name.value,
                    score.author_agent_id,
                    score.voter_agent_id,
                    score.provider_id,
                )
                occurrence = section_score_occurrences[base]
                section_score_occurrences[base] += 1
                self._append(
                    state,
                    HybridRecordKind.SECTION_QUALITY_SCORE_OBSERVED,
                    f"{base}:{occurrence}",
                    {
                        "candidate_ref": candidate_ref,
                        "section": score.section_name.value,
                        "author_agent_id": score.author_agent_id,
                        "voter_agent_id": score.voter_agent_id,
                        "provider_id": score.provider_id,
                        "score_breakdown": score.score_breakdown.model_dump(mode="json"),
                        "overall_score": score.overall_score,
                        "confidence": score.confidence,
                        "penalty_flags": [flag.value for flag in score.penalty_flags],
                        "provider_status": score.provider_status.value,
                        "signal_class": "quality_only",
                    },
                )

        assembled = state.assembled_answer
        if assembled is not None:
            sections = []
            for section in assembled.sections:
                sections.append({
                    "section": section.section_name.value,
                    "candidate_ref": draft_refs.get(
                        section.selected_draft_id,
                        _stable_ref(
                            "candidate_unknown",
                            state.session_id,
                            section.selected_draft_id,
                        ),
                    ),
                    "author_agent_id": section.selected_author_agent_id,
                    "content_sha256": _sha256_text(section.content),
                    "average_score": section.average_score,
                    "score_count": section.score_count,
                    "variance": section.variance,
                    "unresolved": section.unresolved,
                })
            answer_ref = _stable_ref(
                "assembly", state.session_id, assembled.assembly_method, sections,
            )
            self._append(
                state,
                HybridRecordKind.ASSEMBLY_OBSERVED,
                answer_ref,
                {
                    "answer_ref": answer_ref,
                    "assembly_method": assembled.assembly_method,
                    "sections": sections,
                    "unresolved_sections": [s.value for s in assembled.unresolved_sections],
                    "answer_sha256": _sha256_text(assembled.full_text()),
                    "semantic_authority": "canonical_assembly_observation_only",
                },
            )

        ratification = state.council_ratification
        if ratification is not None:
            verdicts = []
            for verdict in ratification.verdicts:
                provider = provider_rows.get(verdict.provider_id or "", {})
                verdicts.append({
                    "agent_id": verdict.agent_id,
                    "provider_id": verdict.provider_id,
                    "model": provider.get("model"),
                    "verdict": verdict.verdict.value,
                    "confidence": verdict.confidence,
                    "target_section": (verdict.target_section.value
                                       if verdict.target_section else None),
                    "severity": verdict.severity.value,
                    "caveat_present": verdict.is_caveat(),
                    "critical_block_schema_valid": (
                        verdict.is_schema_valid_critical_block()),
                    "rationale_sha256": _sha256_text(verdict.rationale),
                    "required_fix_sha256": (_sha256_text(verdict.required_fix)
                                             if verdict.required_fix else None),
                    "provider_status": verdict.provider_status.value,
                })
            payload = {
                "source": "council_ratification",
                "status": ratification.status.value,
                "valid_verdicts": ratification.valid_verdicts,
                "invalid_verdicts": ratification.invalid_verdicts,
                "quorum": ratification.quorum,
                "caveat_count": ratification.caveat_count,
                "critical_block_count": ratification.critical_block_count,
                "target_sections": [s.value for s in ratification.target_sections],
                "failed_providers": list(ratification.failed_providers),
                "timed_out_providers": list(ratification.timed_out_providers),
                "verdicts": verdicts,
                "semantic_authority": "canonical_ratification_observation_only",
            }
        else:
            payload = {
                "source": "legacy_final_votes",
                "status": final.ratification_status,
                "ratified": final.ratified,
                "votes": [
                    {
                        "voter_agent_id": vote.voter_agent_id,
                        "decision": vote.decision.value,
                        "severity": vote.severity.value,
                        "target_section": (vote.target_section.value
                                           if vote.target_section else None),
                        "reason_sha256": _sha256_text(vote.reason),
                    }
                    for vote in final.ratification_votes
                ],
                "semantic_authority": "canonical_ratification_observation_only",
            }
        self._append(
            state,
            HybridRecordKind.RATIFICATION_OBSERVED,
            f"ratification:{state.session_id}",
            payload,
        )

        self._append(
            state,
            HybridRecordKind.FINAL_RESPONSE_OBSERVED,
            f"final_response:{state.session_id}",
            {
                "authority_projection_sha256": _digest({
                    "session_id": final.session_id,
                    "question_sha256": _sha256_text(final.question),
                    "answer_sha256": _sha256_text(final.answer),
                    "ratification_status": final.ratification_status,
                    "ratified": final.ratified,
                    "blocking_objection_sha256": [
                        _sha256_text(item) for item in final.blocking_objections
                    ],
                    "unresolved_sections": [
                        section.value for section in final.unresolved_sections
                    ],
                    "epistemic_status": final.epistemic_status.value,
                }),
                "answer_sha256": _sha256_text(final.answer),
                "ratification_status": final.ratification_status,
                "ratified": final.ratified,
                "answer_present": bool(final.answer),
                "epistemic_status": final.epistemic_status.value,
                "score_coverage": final.audit_summary.get("score_coverage"),
                "release_authority": "canonical_ced_only",
            },
        )
        return self.ledger.records(state.session_id)


__all__ = [
    "HYBRID_SHADOW_SCHEMA_VERSION",
    "SHADOW_AUTHORITY",
    "HybridLedgerConflict",
    "HybridLedgerIntegrityError",
    "HybridRecordKind",
    "HybridShadowRecord",
    "HybridEpistemicLedger",
    "HybridShadowObserver",
]
