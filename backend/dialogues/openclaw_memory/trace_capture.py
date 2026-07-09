"""
OpenClaw Memory Lessons — trace capture (Goal 5).

Every council run should produce an auditable trace that can later feed lesson
extraction and the learning pipeline. This module captures the trace as an
in-memory record (and optionally writes it to a JSONL file).

The trace consumer is duck-typed to the CED session-end pattern:
``trace_capturer.ingest_session(state, final)`` — same interface as
``training_corpus`` in Phase 22. CED calls it at session-end, failure-isolated,
so a trace failure never breaks a session result.

What the trace CONTAINS:
  - session id, question, timestamp
  - per-move summaries: phase, role, provider_id, content keys (not full text
    by default — full text is opt-in)
  - selected openclaw lesson ids (when available from audit)
  - assembly result (winning sections + their source draft ids)
  - ratification result (ratified, status, rounds)
  - audit summary (CED-owned diagnostics)

What the trace NEVER contains:
  - API keys, provider credentials, environment variables
  - hidden chain-of-thought (provider internals)
  - raw peer scores or leaderboard data in agent-facing sections
    (scores appear only in the CED-owned audit, which is already hidden)

No provider calls, no network, no API keys.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from backend.dialogues.models import (
    FinalResponse,
    SessionState,
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
        entry["content_keys"] = sorted(move.content.keys()) if isinstance(move.content, dict) else []
    return entry


def _assembly_summary(final: FinalResponse) -> Optional[Dict[str, Any]]:
    if final.synthesis is None:
        return None
    return {
        "sections": [
            {
                "section_name": s.section_name.value,
                "source_draft_id": s.selected_draft_id,
            }
            for s in final.synthesis.sections
        ],
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
    """Build an auditable trace record from a completed session.

    ``shadow_run`` marks the trace AT CAPTURE TIME as a Shadow-Apprentice
    run (outputs that never affected final answers). The marker lives inside
    the auditable record itself, so downstream evidence collection can filter
    shadow sessions mechanically instead of trusting a later declaration.
    """
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
            _move_summary(m, include_content=include_content)
            for m in state.moves
        ],
        "selected_openclaw_lessons": selected_lessons,
        "assembly": _assembly_summary(final),
        "ratification": _ratification_summary(final),
        "audit_keys": sorted(audit.keys()),
    }
    if metadata:
        trace["metadata"] = metadata
    return trace


class TraceCapturer:
    """In-memory trace collector with optional JSONL file output.

    Duck-typed to the CED session-end consumer pattern:
    ``capturer.ingest_session(state, final)``

    Pass to ``CEDOrchestrator`` (or ``build_council``) as the
    ``trace_capturer`` parameter (see below).
    """

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
        # Shadow-Apprentice capture: every trace this capturer writes is
        # marked shadow_run at capture time (auditable, mechanically
        # filterable by evidence collection — never a later declaration).
        self.shadow_run = bool(shadow_run)
        self.output_dir = Path(output_dir) if output_dir else None
        self.traces: List[Dict[str, Any]] = []

    def ingest_session(self, state: SessionState, final: FinalResponse) -> Dict[str, Any]:
        """Capture a trace from a completed session (CED session-end hook)."""
        trace = build_session_trace(
            state, final,
            include_content=self.include_content,
            metadata=self.metadata if self.metadata else None,
            shadow_run=self.shadow_run,
        )
        self.traces.append(trace)

        if self.output_dir is not None:
            self._write_trace(trace)

        return trace

    def _write_trace(self, trace: Dict[str, Any]) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{trace['session_id']}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")
        return path

    @property
    def session_count(self) -> int:
        return len(self.traces)

    def latest_trace(self) -> Optional[Dict[str, Any]]:
        return self.traces[-1] if self.traces else None

    def _assert_no_secrets(self, trace: Dict[str, Any]) -> None:
        """Debug guard: ensure no obvious secrets leaked into a trace."""
        text = json.dumps(trace, default=str)
        for forbidden in ("api_key", "ANTHROPIC_API_KEY", "sk-ant-", "Bearer "):
            assert forbidden not in text, f"trace contains {forbidden!r}"
