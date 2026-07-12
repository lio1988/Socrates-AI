"""Tamper-evident consultation receipts and their immutable store.

A receipt binds one canonical request digest to one canonical result digest
plus the isolation flags and provider status. It stores no keys, no auth
headers, and no hidden provider reasoning. The store is append-only and
idempotent: the same (request, result) writes once; a different content under
the same request_id is refused.

Record construction and verification (schema, fields, digests) live here; the
atomic, immutable, concurrency-safe *publication* is the neutral shared
primitive ``backend.dialogues.openclaw_receipts.AtomicReceiptStore`` — this
module only supplies the domain error type, the record verifier, and the
request-id validator.
"""

from __future__ import annotations

import os      # noqa: F401  exposed so tests can monkeypatch the global os used
import uuid    # noqa: F401  by the shared publication primitive (same singletons)
from typing import Any, Dict, Mapping, Optional

from ..openclaw_receipts import AtomicReceiptStore
from .schemas import (
    RECEIPT_VERSION,
    ConsultationError,
    ConsultationResult,
    ExternalConsultationRequest,
    clean_hex64,
    clean_id,
    clean_iso,
    clean_request_id,
    digest,
)

_RECEIPT_FIELDS = {
    "schema_version", "request_id", "request_digest", "result_digest",
    "requesting_agent_id", "mode", "provider", "model", "consultation_relation",
    "candidate_order", "worker_id", "isolated_session", "tools_disabled",
    "delegation_disabled", "started_at", "completed_at", "provider_status",
    "token_usage", "receipt_digest",
}


def build_receipt(
    request: ExternalConsultationRequest,
    result: ConsultationResult,
    *,
    worker_id: str,
    started_at: str,
    completed_at: str,
    token_usage: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    """Bind request+result into an unforgeable receipt record."""
    if result.request_digest != request.request_digest:
        raise ConsultationError("receipt result does not match its request")
    usage: Optional[Dict[str, int]] = None
    if token_usage is not None:
        usage = {}
        for key, value in token_usage.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ConsultationError("token_usage values must be counts")
            usage[clean_id(str(key), field="token_usage key")] = value

    unsigned = {
        "schema_version": RECEIPT_VERSION,
        "request_id": request.request_id,
        "request_digest": request.request_digest,
        "result_digest": result.response_digest,
        "requesting_agent_id": request.requesting_agent_id,
        "mode": request.mode,
        "provider": result.provider,
        "model": result.model,
        "consultation_relation": request.consultation_relation,
        # Resolved judge order: candidate_a -> candidate_order[0],
        # candidate_b -> candidate_order[1] (empty for critic/solver). This
        # makes the verdict->original-candidate mapping auditable from the
        # receipt alone.
        "candidate_order": list(request.candidate_order),
        "worker_id": clean_id(worker_id, field="worker_id"),
        "isolated_session": True,
        "tools_disabled": True,
        "delegation_disabled": True,
        "started_at": clean_iso(started_at, field="started_at"),
        "completed_at": clean_iso(completed_at, field="completed_at"),
        "provider_status": result.provider_status,
        "token_usage": usage,
    }
    record = dict(unsigned)
    record["receipt_digest"] = digest(unsigned)
    return record


def verify_receipt(record: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(record, Mapping) or set(record) != _RECEIPT_FIELDS:
        raise ConsultationError("receipt has missing or unknown fields")
    if record.get("schema_version") != RECEIPT_VERSION:
        raise ConsultationError("unknown consultation receipt schema version")
    clean_hex64(record["request_digest"], field="request_digest")
    clean_hex64(record["result_digest"], field="result_digest")
    supplied = str(record.get("receipt_digest", ""))
    unsigned = {key: value for key, value in record.items()
                if key != "receipt_digest"}
    if digest(unsigned) != supplied:
        raise ConsultationError("consultation receipt digest mismatch")
    return dict(record)


class ConsultationReceiptStore(AtomicReceiptStore):
    """Thin domain wrapper over the shared hardened publication primitive.

    Behavior (atomic immutable publication, one shared lock across os.link and
    os.replace, one deadline, DELETE_PENDING handling, ownership-aware cleanup,
    strict normalized reads) is entirely inherited; this class only binds the
    consultation error type, verifier, and request-id validator so the primitive
    stays domain-neutral and the two domain stores share ONE implementation.
    """

    _error_type = ConsultationError
    _noun = "consultation receipt"

    def _verify(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        return verify_receipt(record)

    def _clean_request_id(self, value: Any) -> str:
        return clean_request_id(value, field="request_id")


__all__ = [
    "build_receipt", "verify_receipt", "ConsultationReceiptStore",
]
