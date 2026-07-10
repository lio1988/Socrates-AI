"""
OpenClaw Agent Identity — the Self-Improving Agent Identity Layer.

"Soul" here is not mystical and not autonomy: it is an auditable, versioned
identity profile per agent seat, derived from evidence and advanced only through
governed, non-self-approved transitions.

Constitution:
  CED governs. Evidence Harness measures. OpenClaw remembers. Agents execute.
  Identity is earned through verified performance.

This package is SYSTEM-owned and runtime-inert: the CED core never imports it,
full profiles never enter ordinary reasoning contexts, and nothing here grants
any agent authority. An explicit self-review task may expose only a bounded,
agent-owned snapshot with verified evidence references and no write capability.
Pure, deterministic, offline.
"""

from .identity_profile import (
    SECTION_NAMES,
    AgentIdentityProfile,
    build_identity_profile,
    from_record,
)
from .identity_registry import IdentityRegistry
from .evidence_collection import (
    collect_gate_evidence,
    evidence_from_arena,
    evidence_from_shadow_profile,
    evidence_from_shadow_traces,
    evidence_from_trace_windows,
)
from .promotion_policy import (
    IDENTITY_LADDER,
    STAGE_NAMES,
    VERSION_GATES,
    GateResult,
    VersionGate,
    advance_stage,
    evaluate_gate,
    next_gate_for,
    record_promotion,
)
from .self_revision import (
    REVISION_TARGET_ACTIONS,
    RevisionEvaluation,
    SelfRevisionProposal,
    approve_and_apply_self_revision,
    evaluate_self_revision,
    proposal_from_record,
)
from .self_review import (
    MAX_INSTRUCTION_BYTES,
    MAX_KNOWN_FAILURES,
    MAX_PENDING_PROPOSALS,
    MAX_REVIEW_EVIDENCE,
    MAX_SOUL_PRINCIPLES,
    MAX_STABLE_LESSONS,
    SELF_REVIEW_BOUNDARIES,
    SNAPSHOT_VERSION,
    SelfReviewEvidence,
    SelfReviewSnapshot,
    build_self_review_snapshot,
    build_self_revision_instruction,
    governed_profile_fingerprint,
    observational_profile_fingerprint,
    profile_fingerprint,
    render_self_review_summary,
)
from .revision_registry import (
    REGISTRY_SCHEMA_VERSION,
    SelfRevisionRegistry as BaseSelfRevisionRegistry,
)
from .revision_registry_governed import (
    MAX_ACTIVE_PROPOSALS_PER_AGENT,
    SelfRevisionRegistry,
    SelfRevisionRegistry as GovernedSelfRevisionRegistry,
)
from .revision_transaction_governed import SelfRevisionTransactionCoordinator
from .governed_system_transactional import GovernedSelfRevisionSystem
from .revision_reconciliation import (
    RevisionConsistencyReport,
    assert_revision_state_consistent,
    reconcile_revision_state,
)
from .revision_reversal import (
    INVERSE_REVISION_ACTIONS,
    build_reversal_proposal,
    is_canonical_reversal,
)
from .revision_evidence import (
    EVIDENCE_SCHEMA_VERSION,
    RevisionEvidenceRecord,
    RevisionEvidenceRegistry,
    evidence_from_record,
)
from .revision_evidence_builders_hardened import (
    AGENT_LESSON_AB_REPORT_VERSION,
    IDENTITY_FAILURE_REPORT_VERSION,
    IDENTITY_RESOLUTION_REPORT_VERSION,
    SOUL_ATTESTATION_VERSION,
    build_agent_lesson_ab_evidence,
    build_identity_failure_evidence,
    build_identity_resolution_evidence,
    build_soul_attestation_evidence,
)
from .revision_transaction import TRANSACTION_SCHEMA_VERSION
from .soul_card import CARD_HEADER, GUIDING_SENTENCE, render_soul_card

__all__ = [
    "SECTION_NAMES",
    "AgentIdentityProfile",
    "build_identity_profile",
    "from_record",
    "IdentityRegistry",
    "collect_gate_evidence",
    "evidence_from_arena",
    "evidence_from_shadow_profile",
    "evidence_from_shadow_traces",
    "evidence_from_trace_windows",
    "IDENTITY_LADDER",
    "STAGE_NAMES",
    "VERSION_GATES",
    "GateResult",
    "VersionGate",
    "advance_stage",
    "evaluate_gate",
    "next_gate_for",
    "record_promotion",
    "REVISION_TARGET_ACTIONS",
    "RevisionEvaluation",
    "SelfRevisionProposal",
    "approve_and_apply_self_revision",
    "evaluate_self_revision",
    "proposal_from_record",
    "MAX_INSTRUCTION_BYTES",
    "MAX_KNOWN_FAILURES",
    "MAX_PENDING_PROPOSALS",
    "MAX_REVIEW_EVIDENCE",
    "MAX_SOUL_PRINCIPLES",
    "MAX_STABLE_LESSONS",
    "SELF_REVIEW_BOUNDARIES",
    "SNAPSHOT_VERSION",
    "SelfReviewEvidence",
    "SelfReviewSnapshot",
    "build_self_review_snapshot",
    "build_self_revision_instruction",
    "governed_profile_fingerprint",
    "observational_profile_fingerprint",
    "profile_fingerprint",
    "render_self_review_summary",
    "REGISTRY_SCHEMA_VERSION",
    "BaseSelfRevisionRegistry",
    "SelfRevisionRegistry",
    "GovernedSelfRevisionRegistry",
    "MAX_ACTIVE_PROPOSALS_PER_AGENT",
    "SelfRevisionTransactionCoordinator",
    "GovernedSelfRevisionSystem",
    "RevisionConsistencyReport",
    "assert_revision_state_consistent",
    "reconcile_revision_state",
    "INVERSE_REVISION_ACTIONS",
    "build_reversal_proposal",
    "is_canonical_reversal",
    "EVIDENCE_SCHEMA_VERSION",
    "RevisionEvidenceRecord",
    "RevisionEvidenceRegistry",
    "evidence_from_record",
    "AGENT_LESSON_AB_REPORT_VERSION",
    "IDENTITY_FAILURE_REPORT_VERSION",
    "IDENTITY_RESOLUTION_REPORT_VERSION",
    "SOUL_ATTESTATION_VERSION",
    "build_agent_lesson_ab_evidence",
    "build_identity_failure_evidence",
    "build_identity_resolution_evidence",
    "build_soul_attestation_evidence",
    "TRANSACTION_SCHEMA_VERSION",
    "CARD_HEADER",
    "GUIDING_SENTENCE",
    "render_soul_card",
]
