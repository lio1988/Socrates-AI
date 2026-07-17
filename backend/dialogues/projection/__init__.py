"""
Council Live View Foundation (Slice 0 + inert ledger half of Slice 1) — audited.

Versioned, read-only CED event contracts and projection interfaces, per
docs/architecture/KARPATHY_LLM_COUNCIL_MAPPING.md §14/§18:

- taxonomy.py     — closed dotted event taxonomy + typed stream contract
- payloads.py     — strict typed payload model per event type (22/22)
- events.py       — ced_epistemic_event_v1 envelope + semantic digest
- ledger.py       — append-only EventLedger (seq starts at 1, idempotent,
                    conflict-detecting, per-stream, injected clock)
- reveal.py       — §6.5 blind-evaluation reveal-policy contract
- role_display.py — §6.2 role-loop display contract over canonical role_history

RUNTIME-INERT BY DESIGN: nothing in this package imports or is imported by
ced.py, the provider registry, or any provider adapter. No frontend, no
transport, no CED authority change. Emission is a later slice, flag-gated and
guarded by a byte-identical FinalResponse test.
"""

from .taxonomy import (
    FORBIDDEN_RUN_ID_SENTINELS,
    PENALTY_FLAG_NAMES,
    PHASE_NAMES,
    PHASE_REQUIRED_TYPES,
    ROLE_NAMES,
    SECTION_NAMES,
    SESSION_SCOPED_TYPES,
    VERDICT_NAMES,
    CedEventType,
    run_stream_id,
    session_stream_id,
)
from .contract_matrix import CONTRACT_MATRIX, EventContract
from .payloads import (
    PAYLOAD_MODELS,
    AssemblySectionRef,
    BasePayload,
    ProviderTokenUsage,
)
from .events import (
    RECEIPT_REF_SCHEMA,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    CedEpistemicEvent,
    CedEventDraft,
    ReceiptRef,
    build_draft,
    canonical_identity_digest,
    derive_event_idempotency_key,
    derive_idempotency_key,
    semantic_digest,
    sha256_hex,
)
from .ledger import CedCausalityError, CedEventConflictError, EventLedger
from .observer import (
    CedEventObserver,
    ObserverFailure,
    derive_projection_run_id,
)
from .reveal import (
    REVEAL_CONTRACT_SCHEMA,
    AnonymousMapping,
    EvaluationPurpose,
    RevealPolicy,
    RevealPolicyStore,
    RevealSealedError,
    SelfSubjectError,
    anonymous_subject_id,
    build_mapping,
    derive_permutation_seed,
    permute_subjects,
    verify_mapping,
)
from .role_display import (
    ROLE_DISPLAY_SCHEMA,
    RoleDisplayRow,
    group_by_phase,
    group_by_round,
    project_role_history,
)

__all__ = [
    # taxonomy / streams / vocabularies
    "FORBIDDEN_RUN_ID_SENTINELS",
    "PENALTY_FLAG_NAMES",
    "PHASE_NAMES",
    "PHASE_REQUIRED_TYPES",
    "ROLE_NAMES",
    "SECTION_NAMES",
    "SESSION_SCOPED_TYPES",
    "VERDICT_NAMES",
    "CedEventType",
    "run_stream_id",
    "session_stream_id",
    # contract matrix
    "CONTRACT_MATRIX",
    "EventContract",
    # payloads
    "PAYLOAD_MODELS",
    "AssemblySectionRef",
    "BasePayload",
    "ProviderTokenUsage",
    # envelope
    "RECEIPT_REF_SCHEMA",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "CedEpistemicEvent",
    "CedEventDraft",
    "ReceiptRef",
    "build_draft",
    "canonical_identity_digest",
    "derive_event_idempotency_key",
    "derive_idempotency_key",
    "semantic_digest",
    "sha256_hex",
    # ledger
    "CedCausalityError",
    "CedEventConflictError",
    "EventLedger",
    # observer bridge (the only projection module CED imports)
    "CedEventObserver",
    "ObserverFailure",
    "derive_projection_run_id",
    # reveal
    "REVEAL_CONTRACT_SCHEMA",
    "AnonymousMapping",
    "EvaluationPurpose",
    "RevealPolicy",
    "RevealPolicyStore",
    "RevealSealedError",
    "SelfSubjectError",
    "anonymous_subject_id",
    "build_mapping",
    "derive_permutation_seed",
    "permute_subjects",
    "verify_mapping",
    # role display
    "ROLE_DISPLAY_SCHEMA",
    "RoleDisplayRow",
    "group_by_phase",
    "group_by_round",
    "project_role_history",
]
