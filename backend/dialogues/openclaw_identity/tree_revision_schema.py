"""Deterministic per-agent observations from Deliberation Tree revisions."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

TREE_REVISION_OBSERVATION_VERSION = "openclaw_tree_revision_observation_v1"

_AGENT_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SAFE_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,256}$")
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
_OUTCOMES = frozenset({"improved", "regressed", "neutral"})
_FIELDS = {
    "schema_version", "session_id", "comparison_key", "question_hash",
    "agent_id", "provider_id", "parent_draft_id", "child_draft_id",
    "parent_score", "child_score", "margin", "effect_margin", "outcome",
    "matched_score_count", "judge_ids", "matched_sections",
    "tree_exploration", "tree_total_expansions", "scorecard_digest",
    "source_trace", "observation_digest",
}


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("tree evidence must be canonical finite JSON") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def clean_text(value: Any, *, field: str, maximum: int = 256) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise ValueError(f"{field} contains control characters")
    if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
        raise ValueError(f"{field} contains secret-shaped data")
    return text


def clean_agent(value: Any, *, field: str = "agent_id") -> str:
    text = clean_text(value, field=field, maximum=128)
    if not _AGENT_RE.fullmatch(text):
        raise ValueError(f"{field} contains unsupported characters")
    return text


def clean_id(value: Any, *, field: str) -> str:
    text = clean_text(value, field=field, maximum=256)
    if not _SAFE_RE.fullmatch(text):
        raise ValueError(f"{field} contains unsupported characters")
    return text


def finite_score(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 10.0:
        raise ValueError(f"{field} must be finite and between 0 and 10")
    return number


def enum_text(value: Any) -> str:
    return str(getattr(value, "value", value))


def status_ok(value: Any) -> bool:
    return enum_text(value or "ok") == "ok"


@dataclass(frozen=True)
class TreeRevisionObservation:
    session_id: str
    comparison_key: str
    question_hash: str
    agent_id: str
    provider_id: str
    parent_draft_id: str
    child_draft_id: str
    parent_score: float
    child_score: float
    margin: float
    effect_margin: float
    outcome: str
    matched_score_count: int
    judge_ids: Tuple[str, ...]
    matched_sections: Tuple[str, ...]
    tree_exploration: float
    tree_total_expansions: int
    scorecard_digest: str
    source_trace: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", clean_id(self.session_id, field="session_id"))
        object.__setattr__(
            self, "comparison_key",
            clean_text(self.comparison_key, field="comparison_key"),
        )
        question_hash = clean_text(self.question_hash, field="question_hash", maximum=64)
        if not _HEX64_RE.fullmatch(question_hash):
            raise ValueError("question_hash must be lowercase SHA-256")
        object.__setattr__(self, "question_hash", question_hash)
        object.__setattr__(self, "agent_id", clean_agent(self.agent_id))
        provider = str(self.provider_id or "").strip()
        object.__setattr__(
            self, "provider_id", clean_id(provider, field="provider_id") if provider else "",
        )
        object.__setattr__(
            self, "parent_draft_id", clean_id(self.parent_draft_id, field="parent_draft_id"),
        )
        object.__setattr__(
            self, "child_draft_id", clean_id(self.child_draft_id, field="child_draft_id"),
        )
        if self.parent_draft_id == self.child_draft_id:
            raise ValueError("tree revision parent and child must differ")

        parent = finite_score(self.parent_score, field="parent_score")
        child = finite_score(self.child_score, field="child_score")
        if isinstance(self.margin, bool) or not isinstance(self.margin, (int, float)):
            raise ValueError("margin must be numeric")
        margin = float(self.margin)
        if not math.isfinite(margin):
            raise ValueError("margin must be finite")
        if round(child - parent, 6) != round(margin, 6):
            raise ValueError("tree revision margin does not match scores")
        object.__setattr__(self, "parent_score", parent)
        object.__setattr__(self, "child_score", child)
        object.__setattr__(self, "margin", margin)

        if isinstance(self.effect_margin, bool) or not isinstance(
                self.effect_margin, (int, float)):
            raise ValueError("effect_margin must be numeric")
        effect_margin = float(self.effect_margin)
        if not math.isfinite(effect_margin) or effect_margin <= 0:
            raise ValueError("effect_margin must be finite and positive")
        object.__setattr__(self, "effect_margin", effect_margin)
        outcome = clean_text(self.outcome, field="outcome", maximum=16)
        if outcome not in _OUTCOMES:
            raise ValueError(f"unknown tree revision outcome {outcome!r}")
        expected_outcome = (
            "improved" if margin >= effect_margin
            else "regressed" if margin <= -effect_margin
            else "neutral"
        )
        if outcome != expected_outcome:
            raise ValueError("tree revision outcome does not match margin threshold")
        object.__setattr__(self, "outcome", outcome)
        if (
            isinstance(self.matched_score_count, bool)
            or not isinstance(self.matched_score_count, int)
            or self.matched_score_count < 1
        ):
            raise ValueError("matched_score_count must be a positive integer")
        judges = tuple(sorted({clean_id(item, field="judge_id") for item in self.judge_ids}))
        sections = tuple(sorted({clean_text(item, field="matched_section", maximum=64)
                                 for item in self.matched_sections}))
        if not judges or not sections:
            raise ValueError("tree observation requires matched judges and sections")
        object.__setattr__(self, "judge_ids", judges)
        object.__setattr__(self, "matched_sections", sections)

        if isinstance(self.tree_exploration, bool):
            raise ValueError("tree_exploration must be numeric")
        exploration = float(self.tree_exploration)
        if not math.isfinite(exploration) or exploration < 0:
            raise ValueError("tree_exploration must be finite and non-negative")
        object.__setattr__(self, "tree_exploration", exploration)
        if (
            isinstance(self.tree_total_expansions, bool)
            or not isinstance(self.tree_total_expansions, int)
            or self.tree_total_expansions < 1
        ):
            raise ValueError("tree_total_expansions must be a positive integer")
        score_digest = clean_text(self.scorecard_digest, field="scorecard_digest", maximum=64)
        if not _HEX64_RE.fullmatch(score_digest):
            raise ValueError("scorecard_digest must be lowercase SHA-256")
        object.__setattr__(self, "scorecard_digest", score_digest)
        object.__setattr__(
            self, "source_trace", clean_text(self.source_trace, field="source_trace", maximum=512),
        )

    def unsigned_record(self) -> Dict[str, Any]:
        return {
            "schema_version": TREE_REVISION_OBSERVATION_VERSION,
            "session_id": self.session_id,
            "comparison_key": self.comparison_key,
            "question_hash": self.question_hash,
            "agent_id": self.agent_id,
            "provider_id": self.provider_id,
            "parent_draft_id": self.parent_draft_id,
            "child_draft_id": self.child_draft_id,
            "parent_score": round(self.parent_score, 6),
            "child_score": round(self.child_score, 6),
            "margin": round(self.margin, 6),
            "effect_margin": self.effect_margin,
            "outcome": self.outcome,
            "matched_score_count": self.matched_score_count,
            "judge_ids": list(self.judge_ids),
            "matched_sections": list(self.matched_sections),
            "tree_exploration": self.tree_exploration,
            "tree_total_expansions": self.tree_total_expansions,
            "scorecard_digest": self.scorecard_digest,
            "source_trace": self.source_trace,
        }

    @property
    def observation_digest(self) -> str:
        return digest(self.unsigned_record())

    def to_record(self) -> Dict[str, Any]:
        record = self.unsigned_record()
        record["observation_digest"] = self.observation_digest
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "TreeRevisionObservation":
        if not isinstance(record, Mapping) or set(record) != _FIELDS:
            raise ValueError("tree revision observation contains missing or unknown fields")
        if record.get("schema_version") != TREE_REVISION_OBSERVATION_VERSION:
            raise ValueError("unknown tree revision observation schema version")
        if isinstance(record.get("judge_ids"), (str, bytes)):
            raise ValueError("judge_ids must be a sequence")
        if isinstance(record.get("matched_sections"), (str, bytes)):
            raise ValueError("matched_sections must be a sequence")
        observation = cls(
            session_id=record["session_id"],
            comparison_key=record["comparison_key"],
            question_hash=record["question_hash"],
            agent_id=record["agent_id"],
            provider_id=record["provider_id"],
            parent_draft_id=record["parent_draft_id"],
            child_draft_id=record["child_draft_id"],
            parent_score=record["parent_score"],
            child_score=record["child_score"],
            margin=record["margin"],
            effect_margin=record["effect_margin"],
            outcome=record["outcome"],
            matched_score_count=record["matched_score_count"],
            judge_ids=tuple(record["judge_ids"]),
            matched_sections=tuple(record["matched_sections"]),
            tree_exploration=record["tree_exploration"],
            tree_total_expansions=record["tree_total_expansions"],
            scorecard_digest=record["scorecard_digest"],
            source_trace=record["source_trace"],
        )
        if record["observation_digest"] != observation.observation_digest:
            raise ValueError("tree revision observation digest mismatch")
        return observation

__all__ = [
    "TREE_REVISION_OBSERVATION_VERSION",
    "TreeRevisionObservation",
    "canonical_json",
    "digest",
    "clean_text",
    "clean_agent",
    "clean_id",
    "finite_score",
    "enum_text",
    "status_ok",
]
