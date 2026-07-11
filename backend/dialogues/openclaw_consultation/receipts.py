"""Tamper-evident consultation receipts and their immutable store.

A receipt binds one canonical request digest to one canonical result digest
plus the isolation flags and provider status. It stores no keys, no auth
headers, and no hidden provider reasoning. The store is append-only and
idempotent: the same (request, result) writes once; a different content under
the same request_id is refused.
"""

from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from .schemas import (
    RECEIPT_VERSION,
    ConsultationError,
    ConsultationResult,
    ExternalConsultationRequest,
    canonical_json,
    clean_hex64,
    clean_id,
    clean_iso,
    digest,
)

_RECEIPT_FIELDS = {
    "schema_version", "request_id", "request_digest", "result_digest",
    "requesting_agent_id", "mode", "provider", "model", "consultation_relation",
    "worker_id", "isolated_session", "tools_disabled", "delegation_disabled",
    "started_at", "completed_at", "provider_status", "token_usage",
    "receipt_digest",
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


class ConsultationReceiptStore:
    """One JSON file per request_id; append-only, idempotent, conflict-safe."""

    def __init__(self, directory: pathlib.Path | str) -> None:
        self.directory = pathlib.Path(directory)

    def _path_for(self, request_id: str) -> pathlib.Path:
        request_id = clean_id(request_id, field="request_id")
        return self.directory / f"{request_id}.receipt.json"

    def save(self, record: Mapping[str, Any]) -> pathlib.Path:
        verified = verify_receipt(record)
        path = self._path_for(verified["request_id"])
        self.directory.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = verify_receipt(json.loads(
                path.read_text(encoding="utf-8")))
            if existing["receipt_digest"] != verified["receipt_digest"]:
                raise ConsultationError(
                    "conflicting consultation receipt for the same request_id")
            return path                            # idempotent exact rewrite
        payload = json.dumps(verified, ensure_ascii=False, sort_keys=True,
                             indent=2) + "\n"
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
        return path

    def load(self, request_id: str) -> Optional[Dict[str, Any]]:
        path = self._path_for(request_id)
        if not path.exists():
            return None
        return verify_receipt(json.loads(path.read_text(encoding="utf-8")))

    def all_receipts(self) -> List[Dict[str, Any]]:
        if not self.directory.exists():
            return []
        return [verify_receipt(json.loads(p.read_text(encoding="utf-8")))
                for p in sorted(self.directory.glob("*.receipt.json"))]


__all__ = [
    "build_receipt", "verify_receipt", "ConsultationReceiptStore",
]
