"""Micro-Socratic Kernel v1 — a bounded, local self-check inside each agent.

Before finalizing an answer, an agent may run ONE small structured audit of its
own draft: what is the central claim, which assumptions does it need, what is the
strongest challenge, what still needs verification, and one bounded decision. The
result is a recommendation to the caller, never authority.

Central invariant:

    Every agent may question itself.
    No agent may certify itself.

The kernel is NOT a second orchestrator/council, NOT an approval engine, NOT a
Memory/Identity/Soul writer, NOT a tool executor, and NOT a chain-of-thought
recorder. It performs exactly one provider call per request, opens no
consultation, executes no tool, and mutates no state. It is additive and
runtime-inert: it is not imported by the CED runtime in v1.

Hierarchy it must preserve:
    Micro-Socratic Kernel = one agent's local self-check
    External Consultation = an independent second opinion
    Deliberation Tree     = multiple alternatives / revisions
    CEDOrchestrator       = the sole production execution authority
"""

from __future__ import annotations

from .adapters import (
    KernelCall,
    KernelProvider,
    KernelRawResponse,
    MockKernelProvider,
    TimeoutKernelProvider,
    default_mock_responder,
    run_kernel_check,
)
from .parser import parse_check_payload
from .policy import KernelPolicy, enforce_policy
from .prompting import build_system_prompt, build_user_prompt
from .receipts import (
    MicroSocraticReceiptStore,
    build_receipt,
    verify_receipt,
)
from .schemas import (
    CHECK_VERSION,
    DECISIONS,
    MAX_DRAFT_CHARS,
    MAX_INNER_ROUNDS,
    MAX_TASK_CHARS,
    MAX_TIMEOUT_SECONDS,
    MAX_TOKENS_CEILING,
    MODES,
    PRIORITIES,
    RECEIPT_VERSION,
    REQUEST_VERSION,
    VERIFICATION_KINDS,
    MicroSocraticCheck,
    MicroSocraticError,
    MicroSocraticRequest,
    canonical_json,
    digest,
    sha256_text,
    validate_check_payload,
)
from .service import (
    KernelGateway,
    KernelOutcome,
    MicroSocraticKernelService,
)

__all__ = [
    # versions / vocab / limits
    "REQUEST_VERSION", "CHECK_VERSION", "RECEIPT_VERSION",
    "MODES", "DECISIONS", "VERIFICATION_KINDS", "PRIORITIES",
    "MAX_INNER_ROUNDS", "MAX_TASK_CHARS", "MAX_DRAFT_CHARS",
    "MAX_TOKENS_CEILING", "MAX_TIMEOUT_SECONDS",
    # schemas + helpers
    "MicroSocraticError", "MicroSocraticRequest", "MicroSocraticCheck",
    "validate_check_payload", "canonical_json", "digest", "sha256_text",
    # policy
    "KernelPolicy", "enforce_policy",
    # adapter boundary
    "KernelCall", "KernelRawResponse", "KernelProvider",
    "MockKernelProvider", "TimeoutKernelProvider",
    "default_mock_responder", "run_kernel_check",
    # prompting + parsing
    "build_system_prompt", "build_user_prompt", "parse_check_payload",
    # receipts
    "build_receipt", "verify_receipt", "MicroSocraticReceiptStore",
    # service + inert seam
    "MicroSocraticKernelService", "KernelOutcome", "KernelGateway",
]
