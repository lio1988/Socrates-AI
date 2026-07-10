"""
OpenClaw Memory Lessons — trace capture (Goal 5).

Captures auditable session traces in memory and optionally as JSONL. Trace
capture is failure-isolated by CED, but this module refuses to persist records
that contain obvious credential fields or token-shaped values.

No provider calls, no network, no API keys.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.dialogues.models import FinalResponse, SessionState


_SECRET_KEYS = frozenset({
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "client_secret",
    "password",
    "secret",
})
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _move_summary(move, *, include_content: bool = False) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "move_id": move.move_id,
        "phase": move.phase.value,
        "role": move.role.value,
        "confidence": move.confidence,
    }
    if move.provider_id:
        entry["provider_id"] = move.provider_id
    if move.task_kind:
        entry["task_kind"] = move.task_kind.value
    if include_content:
        entry["content"] = move.content
    else:
        entry["content_keys"] = (
            sorted(move.content.keys()) if isinstance(move.content, dict) else [])
    return entry


def _assembly_summary(final: FinalResponse) -> Optional[Dict[str, Any]]:
    if final.synthesis is None:
        return None
    return {
        "sections": [{
            "section_name": section.section_name.value,
            "source_draft_id": section.selected_draft_id,
        } for section in final.synthesis.sections],
    }


def _ratification_summary(final: FinalResponse) -> Dict[str, Any]:
    return {
        "ratified": final.ratified,
        "ratification_status": final.ratification_status,
    }


def build_session_trace(
    state: SessionState,
    final: FinalResponse,
    *,
    include_content: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    shadow_run: bool = False,
) -> Dict[str, Any]:
    """Build one auditable trace record from a completed session."""
    audit = final.audit_summary or {}
    openclaw = audit.get("openclaw_lessons")
    selected_lessons = openclaw.get("selected", []) if openclaw else []

    trace: Dict[str, Any] = {
        "trace_version": "openclaw_trace_v0",
        "session_id": state.session_id,
        "question": state.question,
        "timestamp": _utcnow().isoformat(),
        "shadow_run": bool(shadow_run),
        "move_count": len(state.moves),
        "moves": [
            _move_summary(move, include_content=include_content)
            for move in state.moves
        ],
        "selected_openclaw_lessons": selected_lessons,
        "assembly": _assembly_summary(final),
        "ratification": _ratification_summary(final),
        "audit_keys": sorted(audit.keys()),
    }
    if metadata:
        trace["metadata"] = metadata
    return trace


def load_jsonl(path: Path | str) -> List[Dict[str, Any]]:
    """Read a JSONL file; malformed lines are skipped without fabrication."""
    p = Path(path)
    if not p.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def load_traces(directory: Path | str) -> List[Dict[str, Any]]:
    """Load every JSONL trace in deterministic file/line order."""
    directory_path = Path(directory)
    if not directory_path.exists():
        return []
    traces: List[Dict[str, Any]] = []
    for path in sorted(directory_path.glob("*.jsonl")):
        traces.extend(load_jsonl(path))
    return traces


def _find_secret(value: Any, path: str = "trace") -> Optional[str]:
    """Return a human-readable violation path, or None.

    Exact sensitive key names are refused when their value is non-empty. String
    values are scanned for credential-shaped prefixes. This is deliberately
    narrow to avoid rejecting harmless fields such as ``api_key_present=False``.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            child_path = f"{path}.{key}"
            if normalized in _SECRET_KEYS and child not in (None, "", False):
                return child_path
            violation = _find_secret(child, child_path)
            if violation:
                return violation
        return None
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            violation = _find_secret(child, f"{path}[{index}]")
            if violation:
                return violation
        return None
    if isinstance(value, str):
        for pattern in _SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                return (
                    f"{path} contains token-shaped data matching "
                    f"{pattern.pattern!r}")
    return None


class TraceCapturer:
    """In-memory trace collector with optional JSONL output."""

    def __init__(
        self,
        *,
        output_dir: Optional[Path | str] = None,
        include_content: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        shadow_run: bool = False,
    ) -> None:
        self.include_content = include_content
        self.metadata = metadata or {}
        self.shadow_run = bool(shadow_run)
        self.output_dir = Path(output_dir) if output_dir else None
        self.traces: List[Dict[str, Any]] = []

    def ingest_session(
        self,
        state: SessionState,
        final: FinalResponse,
    ) -> Dict[str, Any]:
        """Capture a trace, refusing secrets before memory or disk mutation."""
        trace = build_session_trace(
            state,
            final,
            include_content=self.include_content,
            metadata=self.metadata if self.metadata else None,
            shadow_run=self.shadow_run,
        )
        self._assert_no_secrets(trace)
        self.traces.append(trace)

        if self.output_dir is not None:
            self._write_trace(trace)
        return trace

    def _write_trace(self, trace: Dict[str, Any]) -> Path:
        # Defense in depth for direct/private calls.
        self._assert_no_secrets(trace)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{trace['session_id']}.jsonl"
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(
                trace, ensure_ascii=False, default=str) + "\n")
        return path

    @property
    def session_count(self) -> int:
        return len(self.traces)

    def latest_trace(self) -> Optional[Dict[str, Any]]:
        return self.traces[-1] if self.traces else None

    def _assert_no_secrets(self, trace: Dict[str, Any]) -> None:
        """Runtime guard; raises even under ``python -O`` (not an assert)."""
        violation = _find_secret(trace)
        if violation:
            raise ValueError(
                f"trace refused because secret-shaped data was found at {violation}")
