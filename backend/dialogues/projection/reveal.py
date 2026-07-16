"""
Council Live View Foundation — identity reveal policy contract (§6.5, audited).

Karpathy ships the reveal mapping to the browser at stage2_complete and
de-anonymizes client-side with an unescaped regex — the exact anti-pattern the
mapping brief rejects ("the mapping must not exist only in frontend memory").
This module is the Socrates replacement contract.

**Alias scope (audited):** anonymous aliases are scoped per
``(session_id, phase, round_index, evaluator_id, evaluation_purpose)``.
The SAME subject receives a DIFFERENT anonymous id in each evaluator context —
aliases are never global, never reusable across phases/rounds/purposes, and a
shared A/B/C/D ordering across judges (Karpathy) is structurally impossible.

**Not a scheduler (audited):** this layer never selects voters, never selects
subjects, and never decides eligibility. It receives an already-decided
(evaluator, subjects) pairing from the canonical CED assignment/eligibility
protocol and only anonymizes/permutes/seals it. The self-scoring prohibition
REMAINS the responsibility of that canonical protocol; ``SelfSubjectError``
below is a defense-in-depth TRIPWIRE that surfaces an upstream eligibility
violation — it never repairs, reassigns, or filters the input.

Mechanics:
- **Per-evaluator deterministic permutation** derived from
  ``SHA-256(session_id | phase | round | evaluator_id | evaluation_purpose)``.
- **Backend-owned mapping** — ``anonymous_subject_id ↔ real_subject_agent_id``
  lives in a CED-side store, digest-sealed (permutation digest + mapping
  digest), never only in UI memory.
- **Controlled reveal** — real identities are released only after the
  evaluation is explicitly closed, per an explicit ``RevealPolicy``; a
  ``NEVER`` policy stays sealed permanently.
- **Forgery detection** — ``verify_mapping`` recomputes both digests; a forged
  or tampered mapping fails verification (§15.6).

Pure contract: imports nothing from ced.py / providers / registry.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .events import sha256_hex


REVEAL_CONTRACT_SCHEMA = "ced_reveal_mapping_v1"


class EvaluationPurpose(str, Enum):
    MOVE_SCORE    = "move_score"
    SECTION_SCORE = "section_score"
    RATIFICATION  = "ratification"


class RevealPolicy(str, Enum):
    AFTER_EVALUATION_CLOSE = "after_evaluation_close"
    NEVER                  = "never"


class RevealSealedError(RuntimeError):
    """Raised when real identities are requested before policy allows."""


class SelfSubjectError(ValueError):
    """
    Tripwire: the canonical assignment protocol handed an evaluator its own
    output. This layer refuses (it never repairs or filters) — the bug is
    upstream, in the eligibility protocol that owns the self-scoring rule.
    """


# ── deterministic derivations ────────────────────────────────────────────────

def derive_permutation_seed(
    session_id: str,
    phase: str,
    round_index: int,
    evaluator_id: str,
    purpose: EvaluationPurpose,
) -> str:
    """SHA-256 seed exactly as specified in mapping §6.5."""
    return sha256_hex(
        f"{session_id}|{phase}|{round_index}|{evaluator_id}|{purpose.value}"
    )


def anonymous_subject_id(seed: str, real_subject_agent_id: str) -> str:
    """
    Stable, non-reversible anonymous id for one subject under one seed.
    Seed-scoped: the same subject gets a different alias per evaluator
    context (evaluator/phase/round/purpose).
    """
    return "anon_" + sha256_hex(f"{seed}|subject|{real_subject_agent_id}")[:16]


def permute_subjects(seed: str, real_subject_ids: List[str]) -> List[str]:
    """
    Deterministic per-evaluator permutation: canonicalize (sorted), then order
    by SHA-256(seed | subject). Same inputs → same order; different evaluator
    (different seed) → independently derived order.
    """
    return sorted(
        sorted(real_subject_ids),
        key=lambda sid: sha256_hex(f"{seed}|order|{sid}"),
    )


def _canonical_json(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


# ── the sealed mapping record ────────────────────────────────────────────────

class AnonymousMapping(BaseModel):
    """
    Backend-owned record of one evaluator's blind view for one evaluation.
    Digest-sealed and frozen; retained per §6.5:
    anonymous_subject_id, real_subject_agent_id, permutation digest,
    mapping digest, reveal policy.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name:        str = Field(default=REVEAL_CONTRACT_SCHEMA,
                                    serialization_alias="schema")
    session_id:         str
    phase:              str
    round_index:        int
    evaluator_id:       str
    purpose:            EvaluationPurpose
    reveal_policy:      RevealPolicy = RevealPolicy.AFTER_EVALUATION_CLOSE
    # anonymous_subject_id -> real_subject_agent_id (backend-side only)
    assignments:        Dict[str, str]
    # anonymous ids in the evaluator's permuted presentation order
    presentation_order: List[str]
    permutation_digest: str
    mapping_digest:     str

    @model_validator(mode="after")
    def _check(self) -> "AnonymousMapping":
        if self.schema_name != REVEAL_CONTRACT_SCHEMA:
            raise ValueError(f"unknown reveal schema: {self.schema_name!r}")
        if set(self.presentation_order) != set(self.assignments.keys()):
            raise ValueError(
                "presentation_order must contain exactly the anonymous ids"
            )
        return self

    def context_key(self) -> Tuple[str, str, int, str, str]:
        return (self.session_id, self.phase, self.round_index,
                self.evaluator_id, self.purpose.value)


def _compute_digests(
    context: Tuple[str, str, int, str, str],
    assignments: Dict[str, str],
    presentation_order: List[str],
) -> Tuple[str, str]:
    permutation_digest = sha256_hex(
        _canonical_json({"context": list(context),
                         "order": presentation_order})
    )
    mapping_digest = sha256_hex(
        _canonical_json({"context": list(context),
                         "assignments": assignments})
    )
    return permutation_digest, mapping_digest


def build_mapping(
    *,
    session_id: str,
    phase: str,
    round_index: int,
    evaluator_id: str,
    purpose: EvaluationPurpose,
    real_subject_agent_ids: List[str],
    reveal_policy: RevealPolicy = RevealPolicy.AFTER_EVALUATION_CLOSE,
) -> AnonymousMapping:
    """
    Build the digest-sealed blind mapping for ONE evaluator, for an
    (evaluator, subjects) pairing ALREADY decided by the canonical CED
    protocol. This function assigns nothing and filters nothing: a
    self-subject in the input is an upstream eligibility bug and raises
    SelfSubjectError (tripwire, not repair).
    """
    if evaluator_id in real_subject_agent_ids:
        raise SelfSubjectError(
            f"evaluator '{evaluator_id}' may not receive its own output to "
            "evaluate — upstream eligibility protocol violated"
        )
    if len(set(real_subject_agent_ids)) != len(real_subject_agent_ids):
        raise ValueError("real_subject_agent_ids must be unique")

    seed = derive_permutation_seed(
        session_id, phase, round_index, evaluator_id, purpose
    )
    ordered_real = permute_subjects(seed, real_subject_agent_ids)
    assignments = {
        anonymous_subject_id(seed, real): real for real in ordered_real
    }
    presentation_order = [
        anonymous_subject_id(seed, real) for real in ordered_real
    ]
    context = (session_id, phase, round_index, evaluator_id, purpose.value)
    permutation_digest, mapping_digest = _compute_digests(
        context, assignments, presentation_order
    )
    return AnonymousMapping(
        session_id=session_id,
        phase=phase,
        round_index=round_index,
        evaluator_id=evaluator_id,
        purpose=purpose,
        reveal_policy=reveal_policy,
        assignments=assignments,
        presentation_order=presentation_order,
        permutation_digest=permutation_digest,
        mapping_digest=mapping_digest,
    )


def verify_mapping(mapping: AnonymousMapping) -> bool:
    """Recompute both digests; False means forged/tampered (§15.6)."""
    permutation_digest, mapping_digest = _compute_digests(
        mapping.context_key(), dict(mapping.assignments),
        list(mapping.presentation_order),
    )
    return (
        permutation_digest == mapping.permutation_digest
        and mapping_digest == mapping.mapping_digest
    )


# ── the backend-owned store with gated reveal ────────────────────────────────

class RevealPolicyStore:
    """
    CED-side registry of blind mappings. The pre-close surface exposes ONLY
    anonymous ids in presentation order; real identities are released solely
    by ``reveal()`` after ``close_evaluation()`` — and never for a mapping
    whose policy is NEVER. The store schedules nothing and assigns nothing.
    """

    def __init__(self) -> None:
        self._mappings: Dict[Tuple[str, str, int, str, str], AnonymousMapping] = {}
        self._closed: set = set()

    def register(self, mapping: AnonymousMapping) -> None:
        if not verify_mapping(mapping):
            raise ValueError("refusing to register a mapping that fails "
                             "digest verification (possible forgery)")
        key = mapping.context_key()
        existing = self._mappings.get(key)
        if existing is not None and existing.mapping_digest != mapping.mapping_digest:
            raise ValueError(
                "conflicting mapping already registered for this context"
            )
        self._mappings[key] = mapping

    def evaluator_view(
        self,
        session_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> List[str]:
        """Anonymous ids in presentation order — safe at any time."""
        mapping = self._require(
            session_id, phase, round_index, evaluator_id, purpose
        )
        return list(mapping.presentation_order)

    def close_evaluation(
        self,
        session_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> None:
        key = (session_id, phase, round_index, evaluator_id, purpose.value)
        if key not in self._mappings:
            raise KeyError(f"no mapping registered for context {key}")
        self._closed.add(key)

    def is_closed(
        self,
        session_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> bool:
        return (session_id, phase, round_index,
                evaluator_id, purpose.value) in self._closed

    def reveal(
        self,
        session_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> Dict[str, str]:
        """anonymous_subject_id -> real_subject_agent_id, policy-gated."""
        mapping = self._require(
            session_id, phase, round_index, evaluator_id, purpose
        )
        if mapping.reveal_policy == RevealPolicy.NEVER:
            raise RevealSealedError(
                "this mapping's reveal policy is NEVER — identities stay sealed"
            )
        if not self.is_closed(session_id, phase, round_index,
                              evaluator_id, purpose):
            raise RevealSealedError(
                "evaluation not closed — identities are sealed until "
                "close_evaluation() (§6.5 controlled reveal)"
            )
        return dict(mapping.assignments)

    def _require(
        self,
        session_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> AnonymousMapping:
        key = (session_id, phase, round_index, evaluator_id, purpose.value)
        mapping = self._mappings.get(key)
        if mapping is None:
            raise KeyError(f"no mapping registered for context {key}")
        return mapping
