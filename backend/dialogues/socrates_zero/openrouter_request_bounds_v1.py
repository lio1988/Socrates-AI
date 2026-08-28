"""Unit-safe bounds for a provider-visible request.

Two guards have now been wrong here, and both are worth stating plainly.

The first compared a **character** count against 65,536, a number labelled
tokens. That number was Gemini's `max_completion_tokens` — an *output* ceiling
for one seat — pressed into service as an *input* bound for all three. An
invented limit, enforced in the wrong unit.

The second replaced it with `prompt_tokens <= character_count`, described as
provable. It is not. Tokenizers in this family operate on **UTF-8 bytes**, not
Unicode scalars, so one character can become several tokens: an emoji is a
single character and four UTF-8 bytes, and a combining sequence is several
characters that may merge or split unpredictably. A character count can
therefore *understate* the token count, which is the dangerous direction.

What this module uses instead
-----------------------------
Byte-level BPE builds every token from at least one UTF-8 byte, so

    prompt_tokens <= canonical_wire_utf8_bytes

is the conservative direction, and it is stated here as a **documented
assumption about byte-backed tokenization**, not as exact counting. No
tokenizer for any of these three families is installed offline, and measured on
this experiment's own receipts the real ratio is neither constant nor close to
one: 4.01 bytes per token for GPT-5 Mini, 3.99 for GPT-4.1 Mini, 3.20 for
Gemini. The bound is therefore roughly three to four times looser than reality.
That costs headroom and never safety.

If an endpoint cannot be justified under the byte-backed assumption, its
estimator is marked unsupported and the request is refused rather than
estimated.

Every quantity carries its unit in its name, and no comparison crosses units:

    wire_request_bytes        bytes, the exact serialized body
    prompt_token_upper_bound  tokens, derived from those bytes
    reserved_output_tokens    tokens, from the execution policy
    context_window_tokens     tokens, from the endpoint's own listing
    transport_byte_limit      bytes, an independent transport limit
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Mapping

#: Identifies the estimator in every record it produces.
PROMPT_TOKEN_ESTIMATOR_ID_V1 = "wire_utf8_byte_upper_bound_v1"

#: Tokens a chat wrapper may add that correspond to no byte of visible content
#: (role markers, turn delimiters, BOS/EOS). Deliberately generous.
PER_MESSAGE_SPECIAL_TOKEN_ALLOWANCE_V1 = 8
REQUEST_SPECIAL_TOKEN_ALLOWANCE_V1 = 32

#: Independent transport payload limit, in bytes. Never reused as a token limit.
TRANSPORT_BYTE_LIMIT_V1 = 4 * 1024 * 1024

#: Endpoints for which byte-backed tokenization is a defensible assumption.
#: All three seats are byte-level BPE families (OpenAI o200k/cl100k, Gemini's
#: SentencePiece-with-byte-fallback). An endpoint absent from this set is not
#: estimated at all.
BYTE_BACKED_TOKENIZER_ENDPOINTS_V1: FrozenSet[str] = frozenset(
    {"openai/flex", "azure/swedencentral", "google-vertex/global", "google-vertex/global/flex"}
)


class RequestBoundError(ValueError):
    """A request exceeded a declared bound. Local refusal, never a provider fault."""

    def __init__(self, guard_id: str, unit: str, observed: int, limit: int, detail: str):
        self.guard_id = guard_id
        self.unit = unit
        self.observed = observed
        self.limit = limit
        super().__init__(
            f"{guard_id}: {detail} — observed {observed} {unit}, limit {limit} {unit}"
        )


class EstimatorUnsupportedError(ValueError):
    """No defensible token bound exists for this endpoint; refuse, do not guess."""


@dataclass(frozen=True)
class RequestSizeMeasurementV1:
    """One rendered request, measured. Each value keeps its unit in its name."""

    wire_request_bytes: int
    characters: int
    prompt_token_upper_bound: int
    special_wrapper_allowance_tokens: int
    reserved_output_tokens: int
    context_window_tokens: int
    estimator_id: str
    message_count: int
    provider_selector: str

    def as_record(self) -> Dict[str, Any]:
        return {
            "wire_request_bytes": self.wire_request_bytes,
            "characters": self.characters,
            "prompt_token_upper_bound": self.prompt_token_upper_bound,
            "special_wrapper_allowance_tokens": self.special_wrapper_allowance_tokens,
            "reserved_output_tokens": self.reserved_output_tokens,
            "context_window_tokens": self.context_window_tokens,
            "prompt_token_estimator_id": self.estimator_id,
            "message_count": self.message_count,
            "provider_selector": self.provider_selector,
        }


def canonical_wire_bytes_v1(body: Mapping[str, Any]) -> bytes:
    """The exact bytes that would be dispatched, serialized once, canonically."""

    return json.dumps(
        dict(body), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def measure_request_v1(
    body: Mapping[str, Any],
    *,
    reserved_output_tokens: int,
    context_window_tokens: int,
    provider_selector: str,
) -> RequestSizeMeasurementV1:
    """Measure the complete request. Nothing is compared here.

    The token bound is taken from the **whole canonical wire body**, so system
    prompt, user content, accumulated dialogue context and the response schema
    are all counted — the provider charges context for all of them.
    """

    if provider_selector not in BYTE_BACKED_TOKENIZER_ENDPOINTS_V1:
        raise EstimatorUnsupportedError(
            f"{provider_selector}: byte-backed tokenization is not justified for "
            "this endpoint, so no token upper bound may be claimed"
        )
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise RequestBoundError(
            "rendered_messages_v1", "messages", 0, 1, "rendered messages are absent"
        )
    characters = 0
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RequestBoundError(
                "rendered_messages_v1", "messages", 0, 1,
                "only string message content can be bounded",
            )
        characters += len(message["content"])
    wire_bytes = len(canonical_wire_bytes_v1(body))
    allowance = (
        PER_MESSAGE_SPECIAL_TOKEN_ALLOWANCE_V1 * len(messages)
        + REQUEST_SPECIAL_TOKEN_ALLOWANCE_V1
    )
    return RequestSizeMeasurementV1(
        wire_request_bytes=wire_bytes,
        characters=characters,
        prompt_token_upper_bound=wire_bytes + allowance,
        special_wrapper_allowance_tokens=allowance,
        reserved_output_tokens=int(reserved_output_tokens),
        context_window_tokens=int(context_window_tokens),
        estimator_id=PROMPT_TOKEN_ESTIMATOR_ID_V1,
        message_count=len(messages),
        provider_selector=provider_selector,
    )


def assert_request_within_bounds_v1(
    measurement: RequestSizeMeasurementV1,
    *,
    max_prompt_tokens: int,
    transport_byte_limit: int = TRANSPORT_BYTE_LIMIT_V1,
) -> None:
    """Three checks, each entirely within one unit."""

    if measurement.prompt_token_upper_bound > max_prompt_tokens:
        raise RequestBoundError(
            "experiment_prompt_budget_v1", "tokens",
            measurement.prompt_token_upper_bound, int(max_prompt_tokens),
            "prompt upper bound exceeds the local experiment prompt budget",
        )
    context_budget = (
        measurement.context_window_tokens - measurement.reserved_output_tokens
    )
    if measurement.prompt_token_upper_bound > context_budget:
        raise RequestBoundError(
            "endpoint_context_window_v1", "tokens",
            measurement.prompt_token_upper_bound, int(context_budget),
            "prompt upper bound plus the reserved output would exceed the "
            "endpoint context window",
        )
    if measurement.wire_request_bytes > transport_byte_limit:
        raise RequestBoundError(
            "transport_payload_v1", "bytes",
            measurement.wire_request_bytes, int(transport_byte_limit),
            "canonical wire request exceeds the transport payload limit",
        )


#: Fields a refused-request receipt may contain. Raw prompt text is not among
#: them: the receipt records how the request was constructed and how large it
#: was, never what it said.
REFUSAL_RECEIPT_ALLOWLIST_V1: FrozenSet[str] = frozenset(
    {
        "schema_version", "seat", "provider_selector", "model", "phase",
        "task_kind", "guard_id", "unit", "observed", "limit",
        "canonical_body_sha256", "wire_request_bytes", "characters",
        "prompt_token_upper_bound", "special_wrapper_allowance_tokens",
        "reserved_output_tokens", "context_window_tokens",
        "prompt_token_estimator_id", "message_count", "message_content_lengths",
        "source_artifact_references", "refused_at_utc",
    }
)


def build_refusal_receipt_v1(
    *,
    seat: str,
    model: str,
    phase: str,
    task_kind: str,
    body: Mapping[str, Any],
    measurement: RequestSizeMeasurementV1,
    error: RequestBoundError,
    source_artifact_references: Any,
    refused_at_utc: str,
) -> Dict[str, Any]:
    """Construction evidence for a refused request, with no raw prompt text.

    A refusal costs nothing and dispatches nothing, but the prompt still holds
    the whole dialogue. Keeping it would create a raw-prompt archive outside the
    established evidence boundary, so what is kept is the digest, the sizes, the
    estimator and the limits — enough to audit the decision and to recognise the
    same body again, and not enough to reconstruct its contents from the
    receipt.
    """

    import hashlib

    receipt = {
        "schema_version": "socrates-refused-request-receipt/v1",
        "seat": seat,
        "provider_selector": measurement.provider_selector,
        "model": model,
        "phase": phase,
        "task_kind": task_kind,
        "guard_id": error.guard_id,
        "unit": error.unit,
        "observed": error.observed,
        "limit": error.limit,
        "canonical_body_sha256": hashlib.sha256(
            canonical_wire_bytes_v1(body)
        ).hexdigest(),
        "message_content_lengths": [
            len(m.get("content", "")) for m in body.get("messages", [])
        ],
        "source_artifact_references": list(source_artifact_references),
        "refused_at_utc": refused_at_utc,
        **measurement.as_record(),
    }
    leaked = sorted(set(receipt) - REFUSAL_RECEIPT_ALLOWLIST_V1)
    if leaked:
        raise ContractLeakError(f"refusal receipt carries non-allowlisted fields: {leaked}")
    return receipt


class ContractLeakError(ValueError):
    """A receipt tried to carry a field outside its allowlist."""


__all__ = [
    "BYTE_BACKED_TOKENIZER_ENDPOINTS_V1",
    "ContractLeakError",
    "EstimatorUnsupportedError",
    "PER_MESSAGE_SPECIAL_TOKEN_ALLOWANCE_V1",
    "PROMPT_TOKEN_ESTIMATOR_ID_V1",
    "REFUSAL_RECEIPT_ALLOWLIST_V1",
    "REQUEST_SPECIAL_TOKEN_ALLOWANCE_V1",
    "RequestBoundError",
    "RequestSizeMeasurementV1",
    "TRANSPORT_BYTE_LIMIT_V1",
    "assert_request_within_bounds_v1",
    "build_refusal_receipt_v1",
    "canonical_wire_bytes_v1",
    "measure_request_v1",
]
