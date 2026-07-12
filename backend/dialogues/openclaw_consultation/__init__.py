"""External Self-Consultation v1 — isolated advisory consultation.

A requesting agent may open ONE isolated, stateless session with another (or the
same) model, submit a bounded question as a user, and receive strictly-validated
advice before finalizing its own answer.

Central invariant:

    The requesting agent may ask.
    The consulted model may advise.
    The consulted model may not execute, approve, delegate, or mutate.
    Only governed evidence may justify a lasting change.

A consultation result is advice / candidate evidence. It is NEVER authority,
approval, ground truth, or a Memory/Identity/Soul/prompt/CED mutation. Nothing
in this package writes agent state or governance state. It is additive and
runtime-inert: it is not imported by the CED runtime in v1.

Three modes: ``critic`` (sees task + draft), ``independent_solver`` (task only,
no draft — reduces confirmation bias), ``judge`` (two anonymous candidates).
"""

from __future__ import annotations

from .adapters import (
    ConsultationCall,
    ConsultationProvider,
    ConsultationRawResponse,
    MockConsultationProvider,
    TimeoutConsultationProvider,
    default_mock_responder,
    run_consultation,
)
from .parser import parse_structured_payload
from .policy import ConsultationPolicy, enforce_policy
from .prompting import build_system_prompt, build_user_prompt
from .receipts import (
    ConsultationReceiptStore,
    build_receipt,
    verify_receipt,
)
from .schemas import (
    CONSULTATION_DEPTH,
    MAX_CANDIDATE_CHARS,
    MAX_DRAFT_CHARS,
    MAX_EVIDENCE_REFERENCES,
    MAX_QUESTION_CHARS,
    MAX_TIMEOUT_SECONDS,
    MAX_TOKENS_CEILING,
    MODES,
    RECEIPT_VERSION,
    RELATIONS,
    REQUEST_VERSION,
    RESULT_VERSION,
    ConsultationError,
    ConsultationResult,
    ExternalConsultationRequest,
    canonical_json,
    digest,
    sha256_text,
    validate_payload,
)
from .service import (
    ConsultationGateway,
    ConsultationOutcome,
    ExternalConsultationService,
)

__all__ = [
    # versions / limits
    "REQUEST_VERSION", "RESULT_VERSION", "RECEIPT_VERSION",
    "MODES", "RELATIONS", "CONSULTATION_DEPTH",
    "MAX_QUESTION_CHARS", "MAX_DRAFT_CHARS", "MAX_CANDIDATE_CHARS",
    "MAX_EVIDENCE_REFERENCES", "MAX_TOKENS_CEILING", "MAX_TIMEOUT_SECONDS",
    # schemas + helpers
    "ConsultationError", "ExternalConsultationRequest", "ConsultationResult",
    "validate_payload", "canonical_json", "digest", "sha256_text",
    # policy
    "ConsultationPolicy", "enforce_policy",
    # adapter boundary
    "ConsultationCall", "ConsultationRawResponse", "ConsultationProvider",
    "MockConsultationProvider", "TimeoutConsultationProvider",
    "default_mock_responder", "run_consultation",
    # prompting + parsing
    "build_system_prompt", "build_user_prompt", "parse_structured_payload",
    # receipts
    "build_receipt", "verify_receipt", "ConsultationReceiptStore",
    # service + inert seam
    "ExternalConsultationService", "ConsultationOutcome", "ConsultationGateway",
]
