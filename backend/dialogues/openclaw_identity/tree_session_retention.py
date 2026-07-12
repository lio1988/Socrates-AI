"""Exact, digest-bound retention of completed tree sessions for evidence work.

The observation extractor needs a completed ``SessionState`` + ``FinalResponse``
pair. Live objects evaporate with the process, so the operator bridge retains
EXACTLY the fields the extractor reads - nothing more (no draft texts, no
prompts, no keys) - as one versioned, hash-bound JSON artifact:

    openclaw_tree_session_artifact_v1

Loading re-verifies the digest and rebuilds read-only views that the SAME
``extract_tree_revision_observations`` consumes unchanged, so a retained
session can never yield different observations than the live one did
(round-trip equality is test-locked).

Retention is storage only: nothing here writes evidence, proposals, Identity,
Memory, or Soul, and the CED core never imports this module.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .tree_revision_schema import (
    canonical_json,
    clean_id,
    clean_text,
    digest,
    enum_text,
    finite_score,
)

TREE_SESSION_ARTIFACT_VERSION = "openclaw_tree_session_artifact_v1"

_ARTIFACT_FIELDS = {
    "schema_version", "session_id", "question", "section_drafts",
    "draft_scorecards", "moves", "task_log", "deliberation_tree",
    "artifact_digest",
}


# ── Read-only views the extractor consumes (attribute access only) ───────────

@dataclass(frozen=True)
class _Row:
    """Immutable attribute view over one retained record."""
    _data: Mapping[str, Any]

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


@dataclass(frozen=True)
class _Scorecard:
    _data: Mapping[str, Any]

    def __getattr__(self, name: str) -> Any:
        if name == "section_scores":
            return tuple(_Row(row) for row in self._data["section_scores"])
        try:
            return self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


@dataclass(frozen=True)
class RetainedTreeSession:
    """(state-like, final-like) pair rebuilt from one retained artifact."""
    session_id: str
    question: str
    section_drafts: Tuple[Any, ...]
    draft_scorecards: Tuple[Any, ...]
    moves: Tuple[Any, ...]
    task_log: Tuple[Any, ...]
    audit_summary: Dict[str, Any]

    @property
    def state(self) -> "RetainedTreeSession":
        return self

    @property
    def final(self) -> Any:
        return _Row({"audit_summary": self.audit_summary})


# ── Retention (live objects -> exact artifact) ───────────────────────────────

def _retain_move(move: Any) -> Dict[str, Any]:
    return {
        "move_id": str(getattr(move, "move_id", "") or ""),
        "task_kind": enum_text(getattr(move, "task_kind", "") or ""),
        "phase": enum_text(getattr(move, "phase", "") or ""),
        "agent_id": str(getattr(move, "agent_id", "") or ""),
        "provider_id": str(getattr(move, "provider_id", "") or ""),
    }


def _retain_draft(draft: Any) -> Dict[str, Any]:
    return {
        "draft_id": str(getattr(draft, "draft_id", "") or ""),
        "session_id": str(getattr(draft, "session_id", "") or ""),
        "author_agent_id": str(getattr(draft, "author_agent_id", "") or ""),
        "provider_id": str(getattr(draft, "provider_id", "") or ""),
        "move_id": str(getattr(draft, "move_id", "") or ""),
    }


def _retain_scorecard(card: Any) -> Dict[str, Any]:
    scores = []
    for score in getattr(card, "section_scores", ()) or ():
        scores.append({
            "session_id": str(getattr(score, "session_id", "") or ""),
            "draft_id": str(getattr(score, "draft_id", "") or ""),
            "author_agent_id": str(getattr(score, "author_agent_id", "") or ""),
            "voter_agent_id": str(getattr(score, "voter_agent_id", "") or ""),
            "section_name": enum_text(getattr(score, "section_name", "") or ""),
            "overall_score": round(finite_score(
                getattr(score, "overall_score", None),
                field="overall_score"), 6),
            "provider_status": enum_text(
                getattr(score, "provider_status", "ok") or "ok"),
        })
    return {
        "draft_id": str(getattr(card, "draft_id", "") or ""),
        "session_id": str(getattr(card, "session_id", "") or ""),
        "author_agent_id": str(getattr(card, "author_agent_id", "") or ""),
        "voter_agent_id": str(getattr(card, "voter_agent_id", "") or ""),
        "provider_status": enum_text(
            getattr(card, "provider_status", "ok") or "ok"),
        "section_scores": scores,
    }


def retain_tree_session(state: Any, final: Any) -> Dict[str, Any]:
    """Capture EXACTLY what the extractor reads, digest-bound."""
    session_id = clean_id(getattr(state, "session_id", ""), field="session_id")
    question = clean_text(getattr(state, "question", ""),
                          field="question", maximum=20000)
    audit = getattr(final, "audit_summary", None) or {}
    if not isinstance(audit, Mapping):
        raise ValueError("final audit_summary must be a mapping")
    tree = audit.get("deliberation_tree") or {}
    if not isinstance(tree, Mapping):
        raise ValueError("deliberation_tree audit must be a mapping")

    record: Dict[str, Any] = {
        "schema_version": TREE_SESSION_ARTIFACT_VERSION,
        "session_id": session_id,
        "question": question,
        "section_drafts": [
            _retain_draft(draft)
            for draft in getattr(state, "section_drafts", ()) or ()
        ],
        "draft_scorecards": [
            _retain_scorecard(card)
            for card in getattr(state, "draft_scorecards", ()) or ()
        ],
        "moves": [_retain_move(move)
                  for move in getattr(state, "moves", ()) or ()],
        "task_log": [_retain_move(entry)
                     for entry in getattr(state, "task_log", ()) or ()],
        "deliberation_tree": json.loads(canonical_json(dict(tree))),
    }
    record["artifact_digest"] = digest(
        {key: value for key, value in record.items()})
    return record


def save_tree_session_artifact(
    state: Any, final: Any, directory: pathlib.Path | str,
) -> pathlib.Path:
    record = retain_tree_session(state, final)
    directory = pathlib.Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record['session_id']}.tree_session.json"
    path.write_text(json.dumps(
        record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return path


# ── Loading (artifact -> extractor-compatible views, tamper-evident) ─────────

def load_tree_session_artifact(
    path_or_record: pathlib.Path | str | Mapping[str, Any],
) -> RetainedTreeSession:
    if isinstance(path_or_record, Mapping):
        record: Mapping[str, Any] = path_or_record
    else:
        path = pathlib.Path(path_or_record)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"tree session artifact {path} is unreadable or corrupt"
            ) from exc
    if not isinstance(record, Mapping) or set(record) != _ARTIFACT_FIELDS:
        raise ValueError(
            "tree session artifact contains missing or unknown fields")
    if record.get("schema_version") != TREE_SESSION_ARTIFACT_VERSION:
        raise ValueError("unknown tree session artifact schema version")
    supplied = str(record.get("artifact_digest", ""))
    # Retention computed the digest over the record WITHOUT the digest field
    # present; reproduce exactly that shape.
    expected = digest({key: value for key, value in record.items()
                       if key != "artifact_digest"})
    if supplied != expected:
        raise ValueError("tree session artifact digest mismatch")

    for field in ("section_drafts", "draft_scorecards", "moves", "task_log"):
        value = record.get(field)
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise ValueError(f"tree session artifact {field} must be a sequence")

    return RetainedTreeSession(
        session_id=str(record["session_id"]),
        question=str(record["question"]),
        section_drafts=tuple(_Row(row) for row in record["section_drafts"]),
        draft_scorecards=tuple(
            _Scorecard(row) for row in record["draft_scorecards"]),
        moves=tuple(_Row(row) for row in record["moves"]),
        task_log=tuple(_Row(row) for row in record["task_log"]),
        audit_summary={"deliberation_tree": dict(record["deliberation_tree"])},
    )


__all__ = [
    "TREE_SESSION_ARTIFACT_VERSION",
    "RetainedTreeSession",
    "retain_tree_session",
    "save_tree_session_artifact",
    "load_tree_session_artifact",
]
