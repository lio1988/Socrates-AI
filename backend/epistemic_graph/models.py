from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join((p or "").strip().lower() for p in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


class ClaimStatus(str, Enum):
    PROPOSED = "proposed"
    CHALLENGED = "challenged"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    REVISED = "revised"
    REJECTED = "rejected"
    INTEGRATED = "integrated"


@dataclass
class Evidence:
    text: str
    source: str = ""
    supports_claim_id: Optional[str] = None
    evidence_id: Optional[str] = None
    quality: float = 0.0
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.evidence_id is None:
            self.evidence_id = stable_id("ev", self.text, self.source, self.supports_claim_id or "")
        self.quality = max(0.0, min(1.0, float(self.quality)))

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Claim:
    text: str
    author_model: str
    claim_id: Optional[str] = None
    status: ClaimStatus = ClaimStatus.PROPOSED
    confidence: float = 0.5
    evidence_ids: List[str] = field(default_factory=list)
    contradicts: List[str] = field(default_factory=list)
    supports: List[str] = field(default_factory=list)
    revision_of: Optional[str] = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.claim_id is None:
            self.claim_id = stable_id("claim", self.author_model, self.text, self.revision_of or "")
        if isinstance(self.status, str):
            self.status = ClaimStatus(self.status)
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "author_model": self.author_model,
            "status": self.status.value,
            "confidence": round(self.confidence, 3),
            "evidence_ids": list(self.evidence_ids),
            "contradicts": list(self.contradicts),
            "supports": list(self.supports),
            "revision_of": self.revision_of,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Contradiction:
    claim_a: str
    claim_b: str
    type: str = "possible_contradiction"
    reason: str = ""
    contradiction_id: Optional[str] = None
    resolved: bool = False
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.contradiction_id is None:
            ordered = sorted([self.claim_a, self.claim_b])
            self.contradiction_id = stable_id("con", ordered[0], ordered[1], self.type)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class EpistemicEvent:
    event_type: str
    description: str
    actor: str = "system"
    claim_id: Optional[str] = None
    event_id: Optional[str] = None
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.event_id is None:
            self.event_id = stable_id("evt", self.event_type, self.description, self.claim_id or "", self.created_at)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CurrentBestExplanation:
    text: str
    based_on_claims: List[str]
    open_questions: List[str] = field(default_factory=list)
    unresolved_contradictions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    provisional: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "based_on_claims": list(self.based_on_claims),
            "open_questions": list(self.open_questions),
            "unresolved_contradictions": list(self.unresolved_contradictions),
            "confidence": round(self.confidence, 3),
            "provisional": self.provisional,
            "note": "This is provisional: a Current Best Explanation, not final truth.",
        }

