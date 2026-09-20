"""
Council Live View Foundation — identity reveal policy contract (§6.5, hardened).

Karpathy ships the reveal mapping to the browser at stage2_complete and
de-anonymizes client-side with an unescaped regex — the exact anti-pattern the
mapping brief rejects ("the mapping must not exist only in frontend memory").
This module is the Socrates replacement contract.

**Alias scope (round 3, finding 1 — RUN-SCOPED):** anonymous aliases are
scoped per ``(session_id, run_id, phase, round_index, evaluator_id,
evaluation_purpose)``. Blind evaluations happen inside a RUN, so two runs in
the same session get DIFFERENT aliases, independent registrations, and
independent close/reveal lifecycles — closing run A can never open run B,
and a NEVER policy in run A cannot affect run B. run_id participates in the
seed derivation, the context key, both digests, and every store API.

**Not a scheduler:** this layer never selects voters, never selects subjects,
and never decides eligibility. It receives an already-decided
(evaluator, subjects) pairing from the canonical CED assignment/eligibility
protocol and only anonymizes/permutes/seals it. The self-scoring prohibition
REMAINS the responsibility of that canonical protocol; ``SelfSubjectError``
is a defense-in-depth TRIPWIRE that surfaces an upstream eligibility
violation — it never repairs, reassigns, or filters the input.

Hardening (rounds 1–3):

- **The sealed-record digest covers the WHOLE record** — schema, full
  run-scoped context, **reveal policy**, assignments AND presentation order.
- **register() never overwrites** and is **TOCTOU-safe (round 3, finding 2)**:
  it first takes a private snapshot (re-validated model), verifies THE
  SNAPSHOT, and stores THE SNAPSHOT — a caller mutating the original mapping
  after verification can never reach the store.
- **verify_mapping() recomputes the canonical mapping from context**: seed,
  every anonymous id and the canonical order are re-derived from the real
  subject ids; exact equality is required BEFORE digest comparison
  (SHA-256 is integrity, not a MAC).
- **Concurrency-safe**: check-then-write is atomic under an internal lock.
- **Canonical JSON derivations**: no "|" joins, no delimiter collisions.
- **Structural uniqueness at the model**: duplicate aliases, duplicate real
  subjects, alias/assignment mismatches and self-subjects reject at
  construction.

Pure contract: imports nothing from ced.py / providers / registry.
"""

from __future__ import annotations

import json
import threading
from enum import Enum
from typing import Dict, List, Tuple

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from .events import sha256_hex
from .taxonomy import FORBIDDEN_RUN_ID_SENTINELS


REVEAL_CONTRACT_SCHEMA = "ced_reveal_mapping_v1"
REVEAL_CONTRACT_VERSION = 1

ContextKey = Tuple[str, str, str, int, str, str]


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


# ── deterministic derivations (canonical JSON — no delimiter collisions) ────

def _canonical_json(data: object) -> str:
    return json.dumps(
        data, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    )


def derive_permutation_seed(
    session_id: str,
    run_id: str,
    phase: str,
    round_index: int,
    evaluator_id: str,
    purpose: EvaluationPurpose,
) -> str:
    """SHA-256 seed over the run-scoped §6.5 context (canonical JSON array)."""
    return sha256_hex(_canonical_json(
        ["ced_reveal_seed", session_id, run_id, phase, round_index,
         evaluator_id, purpose.value]
    ))


def anonymous_subject_id(seed: str, real_subject_agent_id: str) -> str:
    """
    Stable, non-reversible anonymous id for one subject under one seed.
    Seed-scoped: the same subject gets a different alias per evaluator
    context (run/evaluator/phase/round/purpose).
    """
    return "anon_" + sha256_hex(
        _canonical_json(["subject", seed, real_subject_agent_id])
    )[:16]


def permute_subjects(seed: str, real_subject_ids: List[str]) -> List[str]:
    """
    Deterministic per-evaluator permutation: canonicalize (sorted), then order
    by SHA-256 over canonical JSON of (seed, subject). Same inputs → same
    order; different evaluator (different seed) → independently derived order.
    """
    return sorted(
        sorted(real_subject_ids),
        key=lambda sid: sha256_hex(_canonical_json(["order", seed, sid])),
    )


# ── the sealed mapping record ────────────────────────────────────────────────

class AnonymousMapping(BaseModel):
    """
    Backend-owned record of one evaluator's blind view for one evaluation,
    scoped to a RUN. Digest-sealed and frozen; retained per §6.5:
    anonymous_subject_id, real_subject_agent_id, permutation digest,
    mapping digest, reveal policy. Structural integrity (uniqueness,
    alias/assignment agreement, no self-subject) is enforced at construction.
    """
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True,
                              populate_by_name=True)

    schema_name:        str = Field(
        default=REVEAL_CONTRACT_SCHEMA,
        validation_alias=AliasChoices("schema", "schema_name"),
        serialization_alias="schema",
    )
    schema_version:     int = REVEAL_CONTRACT_VERSION
    session_id:         str = Field(min_length=1)
    run_id:             str = Field(min_length=1)
    phase:              str = Field(min_length=1)
    round_index:        int = Field(ge=0)
    evaluator_id:       str = Field(min_length=1)
    purpose:            EvaluationPurpose
    reveal_policy:      RevealPolicy = RevealPolicy.AFTER_EVALUATION_CLOSE
    # anonymous_subject_id -> real_subject_agent_id (backend-side only)
    assignments:        Dict[str, str]
    # anonymous ids in the evaluator's permuted presentation order
    presentation_order: List[str]
    permutation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    mapping_digest:     str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="before")
    @classmethod
    def _normalize_wire_enums(cls, values: object) -> object:
        """
        Canonical enum parsing ONLY (round 4): under strict=True the raw
        wire strings for the enum fields must be turned into enum instances
        before strict field validation, so wire JSON still round-trips. No
        other coercion happens — everything else is validated strictly.
        """
        if not isinstance(values, dict):
            return values
        normalized = dict(values)
        if "purpose" in normalized:
            normalized["purpose"] = EvaluationPurpose(normalized["purpose"])
        if "reveal_policy" in normalized:
            normalized["reveal_policy"] = RevealPolicy(
                normalized["reveal_policy"]
            )
        return normalized

    @model_validator(mode="after")
    def _check(self) -> "AnonymousMapping":
        if self.schema_name != REVEAL_CONTRACT_SCHEMA:
            raise ValueError(f"unknown reveal schema: {self.schema_name!r}")
        if self.schema_version != REVEAL_CONTRACT_VERSION:
            raise ValueError(
                f"unsupported reveal schema_version {self.schema_version}"
            )
        # Context identifiers must carry a non-whitespace character
        # (min_length=1 does not exclude "   "). Round 4.
        for field_name in ("session_id", "run_id", "phase", "evaluator_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(
                    f"{field_name} must contain a non-whitespace character"
                )
        if self.run_id.strip().lower() in FORBIDDEN_RUN_ID_SENTINELS:
            raise ValueError(
                f"run_id {self.run_id!r} is a forbidden sentinel"
            )
        for real in self.assignments.values():
            if not real.strip():
                raise ValueError(
                    "real subject ids must contain a non-whitespace character"
                )
        order = self.presentation_order
        if len(order) == 0:
            raise ValueError(
                "a blind mapping must contain at least one subject"
            )
        if len(order) != len(set(order)):
            raise ValueError(
                "presentation_order must not contain duplicate aliases"
            )
        if len(order) != len(self.assignments):
            raise ValueError(
                "presentation_order and assignments must be the same size"
            )
        if set(order) != set(self.assignments.keys()):
            raise ValueError(
                "presentation_order must contain exactly the anonymous ids"
            )
        reals = list(self.assignments.values())
        if len(reals) != len(set(reals)):
            raise ValueError(
                "assignments must not map two aliases to the same real subject"
            )
        if self.evaluator_id in reals:
            raise SelfSubjectError(
                f"evaluator '{self.evaluator_id}' may not appear among the "
                "real subjects — upstream eligibility protocol violated"
            )
        return self

    def context_key(self) -> ContextKey:
        return (self.session_id, self.run_id, self.phase, self.round_index,
                self.evaluator_id, self.purpose.value)


def _compute_digests(
    context: ContextKey,
    reveal_policy: RevealPolicy,
    assignments: Dict[str, str],
    presentation_order: List[str],
) -> Tuple[str, str]:
    """
    Sealed-record digests. The mapping digest covers the WHOLE record —
    schema/version, full run-scoped context, reveal policy, assignments AND
    order — so no field can change without changing the digest.
    """
    permutation_digest = sha256_hex(_canonical_json({
        "schema": REVEAL_CONTRACT_SCHEMA,
        "version": REVEAL_CONTRACT_VERSION,
        "context": list(context),
        "order": presentation_order,
    }))
    mapping_digest = sha256_hex(_canonical_json({
        "schema": REVEAL_CONTRACT_SCHEMA,
        "version": REVEAL_CONTRACT_VERSION,
        "context": list(context),
        "reveal_policy": reveal_policy.value,
        "assignments": assignments,
        "order": presentation_order,
    }))
    return permutation_digest, mapping_digest


def build_mapping(
    *,
    session_id: str,
    run_id: str,
    phase: str,
    round_index: int,
    evaluator_id: str,
    purpose: EvaluationPurpose,
    real_subject_agent_ids: List[str],
    reveal_policy: RevealPolicy = RevealPolicy.AFTER_EVALUATION_CLOSE,
) -> AnonymousMapping:
    """
    Build the digest-sealed blind mapping for ONE evaluator in ONE run, for
    an (evaluator, subjects) pairing ALREADY decided by the canonical CED
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
    if any(not str(sid).strip() for sid in real_subject_agent_ids):
        raise ValueError(
            "real subject ids must contain a non-whitespace character"
        )

    seed = derive_permutation_seed(
        session_id, run_id, phase, round_index, evaluator_id, purpose
    )
    ordered_real = permute_subjects(seed, real_subject_agent_ids)
    assignments = {
        anonymous_subject_id(seed, real): real for real in ordered_real
    }
    presentation_order = [
        anonymous_subject_id(seed, real) for real in ordered_real
    ]
    context: ContextKey = (session_id, run_id, phase, round_index,
                           evaluator_id, purpose.value)
    permutation_digest, mapping_digest = _compute_digests(
        context, reveal_policy, assignments, presentation_order
    )
    return AnonymousMapping(
        session_id=session_id,
        run_id=run_id,
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
    """
    CANONICAL verification: re-derive the whole blind view from the mapping's
    run-scoped context and real subjects, require exact equality, then check
    the sealed-record digests. An attacker who recomputes digests over a
    non-canonical alias set or order still fails, because the aliases and
    order themselves are recomputed here from the context.
    """
    order = list(mapping.presentation_order)
    assignments = dict(mapping.assignments)

    # Structural integrity (also enforced at construction — re-checked so a
    # verification path never trusts upstream construction).
    if len(order) == 0 or len(order) != len(set(order)):
        return False
    if len(order) != len(assignments):
        return False
    if set(order) != set(assignments.keys()):
        return False
    reals = list(assignments.values())
    if len(reals) != len(set(reals)):
        return False
    if mapping.evaluator_id in reals:
        return False

    # Canonical recomputation from context + real subjects.
    seed = derive_permutation_seed(
        mapping.session_id, mapping.run_id, mapping.phase,
        mapping.round_index, mapping.evaluator_id, mapping.purpose,
    )
    expected_real_order = permute_subjects(seed, reals)
    expected_assignments = {
        anonymous_subject_id(seed, real): real
        for real in expected_real_order
    }
    expected_order = [
        anonymous_subject_id(seed, real) for real in expected_real_order
    ]
    if assignments != expected_assignments:
        return False
    if order != expected_order:
        return False

    # Sealed-record digest check (covers schema, context, POLICY, content).
    permutation_digest, mapping_digest = _compute_digests(
        mapping.context_key(), mapping.reveal_policy, assignments, order,
    )
    return (
        permutation_digest == mapping.permutation_digest
        and mapping_digest == mapping.mapping_digest
    )


# ── the backend-owned store with gated reveal ────────────────────────────────

class RevealPolicyStore:
    """
    CED-side registry of blind mappings, keyed by the RUN-SCOPED context.
    The pre-close surface exposes ONLY anonymous ids in presentation order;
    real identities are released solely by ``reveal()`` after
    ``close_evaluation()`` — and never for a mapping whose policy is NEVER.
    The store schedules nothing and assigns nothing.

    Registration is write-once per context, TOCTOU-safe (round 3, finding 2):
    a private re-validated SNAPSHOT is taken first, verification runs on the
    snapshot, and the snapshot is what gets stored — the caller-owned object
    is never touched again after the snapshot, so mutating it after
    verification cannot reach the store. Check-then-write is atomic under an
    internal lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mappings: Dict[ContextKey, AnonymousMapping] = {}
        self._closed: set = set()

    def register(self, mapping: AnonymousMapping) -> None:
        # 1. Private snapshot FIRST (fresh nested containers via dump/validate).
        candidate = AnonymousMapping.model_validate(
            mapping.model_dump(mode="python")
        )
        # 2. Verify THE SNAPSHOT (pure — outside the lock).
        if not verify_mapping(candidate):
            raise ValueError("refusing to register a mapping that fails "
                             "canonical verification (possible forgery)")
        # 3. From here on, only the snapshot is used.
        key = candidate.context_key()
        with self._lock:
            existing = self._mappings.get(key)
            if existing is not None:
                if existing == candidate:
                    return                      # idempotent re-registration
                raise ValueError(
                    "conflicting mapping already registered for this "
                    "context — a registered mapping is never overwritten "
                    "(policy, order and assignments are all part of its "
                    "identity)"
                )
            self._mappings[key] = candidate

    def evaluator_view(
        self,
        session_id: str,
        run_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> List[str]:
        """Anonymous ids in presentation order — safe at any time.
        Returns a fresh list; mutating it cannot change the store."""
        mapping = self._require(
            session_id, run_id, phase, round_index, evaluator_id, purpose
        )
        return list(mapping.presentation_order)

    def close_evaluation(
        self,
        session_id: str,
        run_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> None:
        key = (session_id, run_id, phase, round_index, evaluator_id,
               purpose.value)
        with self._lock:
            if key not in self._mappings:
                raise KeyError(f"no mapping registered for context {key}")
            self._closed.add(key)

    def is_closed(
        self,
        session_id: str,
        run_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> bool:
        with self._lock:
            return (session_id, run_id, phase, round_index,
                    evaluator_id, purpose.value) in self._closed

    def reveal(
        self,
        session_id: str,
        run_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> Dict[str, str]:
        """anonymous_subject_id -> real_subject_agent_id, policy-gated.
        Returns a fresh dict; mutating it cannot change the store."""
        mapping = self._require(
            session_id, run_id, phase, round_index, evaluator_id, purpose
        )
        if mapping.reveal_policy == RevealPolicy.NEVER:
            raise RevealSealedError(
                "this mapping's reveal policy is NEVER — identities stay sealed"
            )
        if not self.is_closed(session_id, run_id, phase, round_index,
                              evaluator_id, purpose):
            raise RevealSealedError(
                "evaluation not closed — identities are sealed until "
                "close_evaluation() (§6.5 controlled reveal)"
            )
        return dict(mapping.assignments)

    def _require(
        self,
        session_id: str,
        run_id: str,
        phase: str,
        round_index: int,
        evaluator_id: str,
        purpose: EvaluationPurpose,
    ) -> AnonymousMapping:
        key = (session_id, run_id, phase, round_index, evaluator_id,
               purpose.value)
        with self._lock:
            mapping = self._mappings.get(key)
        if mapping is None:
            raise KeyError(f"no mapping registered for context {key}")
        return mapping
