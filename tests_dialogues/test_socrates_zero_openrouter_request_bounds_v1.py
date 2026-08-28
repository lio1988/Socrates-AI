"""Request bounds must never compare across units, and must bound the right one.

Two guards have been wrong here. The first compared characters against 65,536, a
number that was Gemini's `max_completion_tokens` — an output field for one seat.
The second replaced it with `prompt_tokens <= character_count`, described as
provable. It is not: these tokenizers work on UTF-8 bytes, so one character can
become several tokens, and a character count can *understate* tokens. The tests
below fix that claim in place so it cannot come back.

The estimator now bounds tokens by canonical wire UTF-8 bytes, stated as a
documented byte-backed-tokenization assumption rather than exact counting.

No sockets are opened anywhere in this file.
"""

from __future__ import annotations

import json

import pytest

from backend.dialogues.socrates_zero.openrouter_request_bounds_v1 import (
    BYTE_BACKED_TOKENIZER_ENDPOINTS_V1,
    PROMPT_TOKEN_ESTIMATOR_ID_V1,
    REFUSAL_RECEIPT_ALLOWLIST_V1,
    TRANSPORT_BYTE_LIMIT_V1,
    ContractLeakError,
    EstimatorUnsupportedError,
    RequestBoundError,
    assert_request_within_bounds_v1,
    build_refusal_receipt_v1,
    canonical_wire_bytes_v1,
    measure_request_v1,
)

GPT_5_MINI_CONTEXT_TOKENS = 400_000
GEMINI_CONTEXT_TOKENS = 1_048_576
GPT_4_1_MINI_CONTEXT_TOKENS = 1_047_576
EXPERIMENT_BUDGET_TOKENS = 262_144

#: The number the first guard compared characters against. Kept so the mistake
#: stays visible rather than being quietly deleted.
GEMINI_MAX_COMPLETION_TOKENS_MISUSED_AS_INPUT = 65_536


def _body(content: str, *, schema: dict | None = None) -> dict:
    body = {
        "model": "openai/gpt-5-mini",
        "messages": [
            {"role": "system", "content": "You are one bounded council provider."},
            {"role": "user", "content": content},
        ],
        "max_tokens": 4096,
        "stream": False,
    }
    if schema is not None:
        body["response_format"] = schema
    return body


def _measure(content, *, context=GPT_5_MINI_CONTEXT_TOKENS, reserved=4096, schema=None,
             selector="openai/flex"):
    return measure_request_v1(
        _body(content, schema=schema),
        reserved_output_tokens=reserved,
        context_window_tokens=context,
        provider_selector=selector,
    )


# -- why a character count is not a token upper bound -------------------------
#
# Each case is a string whose UTF-8 byte count exceeds its character count, so a
# character-based bound would claim a smaller number of tokens than the text can
# actually produce. A representative byte-level tokenizer emits at least one
# token per UTF-8 byte for these, which is exactly the direction that matters.

MULTI_BYTE_CASES = [
    pytest.param("🩺", 4, id="emoji-one-char-four-bytes"),
    pytest.param("👩‍⚕️", 6, id="zwj-sequence"),
    pytest.param("ȩ́", 2, id="combining-marks"),
    pytest.param("移植", 2, id="cjk"),
    pytest.param("επιτροπή", 2, id="greek"),
    pytest.param("—…", 2, id="punctuation"),
]


@pytest.mark.parametrize("text,min_bytes_per_char", MULTI_BYTE_CASES)
def test_character_count_understates_bytes_and_so_cannot_bound_tokens(
    text: str, min_bytes_per_char: int
) -> None:
    encoded = text.encode("utf-8")
    assert len(encoded) >= len(text) * min_bytes_per_char / max(len(text), 1)
    assert len(encoded) > len(text), (
        "this fixture exists because bytes exceed characters here, which is why "
        "prompt_tokens <= character_count is not a valid upper bound"
    )


def test_estimator_bounds_by_bytes_not_characters() -> None:
    """The bound must track bytes, so multibyte text raises it."""
    ascii_m = _measure("a" * 400)
    emoji_m = _measure("🩺" * 400)
    assert emoji_m.characters == ascii_m.characters
    assert emoji_m.wire_request_bytes > ascii_m.wire_request_bytes
    assert emoji_m.prompt_token_upper_bound > ascii_m.prompt_token_upper_bound
    assert emoji_m.estimator_id == PROMPT_TOKEN_ESTIMATOR_ID_V1


@pytest.mark.parametrize(
    "label,content",
    [
        ("ascii", "The committee argues that no allocation rule is fair. " * 40),
        ("greek", "Το επιχείρημα της επιτροπής δεν είναι έγκυρο στο βήμα 4. " * 40),
        ("json_escaping", json.dumps({"a": 'quote " backslash \\ newline \n'}) * 200),
        ("emoji", "🩺🫀📋⚖️" * 200),
        ("cjk", "移植委員会の議論は第四段階で妥当性を欠く。" * 100),
        ("combining", "ȩ́" * 500),
    ],
)
def test_bound_is_at_least_the_wire_bytes_for_every_script(label, content) -> None:
    m = _measure(content)
    assert m.prompt_token_upper_bound >= m.wire_request_bytes
    assert m.wire_request_bytes >= len(content.encode("utf-8"))


def test_schema_heavy_payload_counts_toward_the_bound() -> None:
    schema = {"json_schema": {"schema": {"properties": {
        f"field_{i}": {"type": "string", "description": "d" * 40} for i in range(300)}}}}
    assert _measure("short", schema=schema).prompt_token_upper_bound > _measure(
        "short"
    ).prompt_token_upper_bound


# -- unsupported endpoints are refused, not guessed ---------------------------


def test_unknown_endpoint_is_unsupported_rather_than_estimated() -> None:
    with pytest.raises(EstimatorUnsupportedError):
        _measure("short", selector="some/unvalidated-endpoint")
    for selector in ("openai/flex", "azure/swedencentral", "google-vertex/global"):
        assert selector in BYTE_BACKED_TOKENIZER_ENDPOINTS_V1


# -- boundaries ---------------------------------------------------------------


def test_exactly_at_the_budget_is_accepted_and_one_over_is_refused() -> None:
    m = _measure("a" * 100)
    assert_request_within_bounds_v1(m, max_prompt_tokens=m.prompt_token_upper_bound)
    with pytest.raises(RequestBoundError) as caught:
        assert_request_within_bounds_v1(
            m, max_prompt_tokens=m.prompt_token_upper_bound - 1
        )
    assert caught.value.unit == "tokens"
    assert caught.value.guard_id == "experiment_prompt_budget_v1"


def test_completion_reservation_can_overflow_the_context_window() -> None:
    m = measure_request_v1(
        _body("short"), reserved_output_tokens=399_999,
        context_window_tokens=400_000, provider_selector="openai/flex",
    )
    with pytest.raises(RequestBoundError) as caught:
        assert_request_within_bounds_v1(m, max_prompt_tokens=EXPERIMENT_BUDGET_TOKENS)
    assert caught.value.guard_id == "endpoint_context_window_v1"


def test_transport_byte_limit_is_independent_of_the_token_budget() -> None:
    m = _measure("a" * 5_000)
    with pytest.raises(RequestBoundError) as caught:
        assert_request_within_bounds_v1(
            m, max_prompt_tokens=EXPERIMENT_BUDGET_TOKENS, transport_byte_limit=100
        )
    assert caught.value.guard_id == "transport_payload_v1"
    assert caught.value.unit == "bytes"
    assert TRANSPORT_BYTE_LIMIT_V1 == 4 * 1024 * 1024
    assert TRANSPORT_BYTE_LIMIT_V1 != EXPERIMENT_BUDGET_TOKENS


def test_65536_is_not_a_context_window_for_any_seat() -> None:
    for context in (GPT_5_MINI_CONTEXT_TOKENS, GEMINI_CONTEXT_TOKENS,
                    GPT_4_1_MINI_CONTEXT_TOKENS):
        assert context != GEMINI_MAX_COMPLETION_TOKENS_MISUSED_AS_INPUT


# -- privacy of the refusal receipt -------------------------------------------


SECRET_SHAPED_PROMPT = (
    "Authorization: Bearer sk-or-v1-abcdef0123456789abcdef0123456789 and the "
    "council's entire confidential deliberation about patient Mira follows here."
)


def _receipt(content: str = SECRET_SHAPED_PROMPT):
    body = _body(content)
    m = _measure(content)
    err = RequestBoundError("experiment_prompt_budget_v1", "tokens", 999, 1, "too big")
    return body, build_refusal_receipt_v1(
        seat="gpt_5_mini", model="openai/gpt-5-mini", phase="reconstruction",
        task_kind="reconstruction_proposal", body=body, measurement=m, error=err,
        source_artifact_references=("hard_logic_live_test_collection_v1.json",),
        refused_at_utc="2026-08-28T00:00:00Z",
    )


def test_refusal_receipt_never_carries_raw_prompt_text() -> None:
    body, receipt = _receipt()
    serialized = json.dumps(receipt, ensure_ascii=False)
    for fragment in ("Bearer", "sk-or-v1", "Mira", "council's entire",
                     "You are one bounded council provider"):
        assert fragment not in serialized, f"{fragment!r} leaked into the receipt"


def test_refusal_receipt_fields_are_allowlisted() -> None:
    _body_, receipt = _receipt()
    assert set(receipt) <= REFUSAL_RECEIPT_ALLOWLIST_V1


def test_refusal_receipt_still_identifies_the_request() -> None:
    body, receipt = _receipt()
    import hashlib

    assert receipt["canonical_body_sha256"] == hashlib.sha256(
        canonical_wire_bytes_v1(body)
    ).hexdigest()
    assert receipt["wire_request_bytes"] > 0
    assert receipt["message_content_lengths"] == [
        len(m["content"]) for m in body["messages"]
    ]
    assert receipt["prompt_token_estimator_id"] == PROMPT_TOKEN_ESTIMATOR_ID_V1


def test_a_receipt_carrying_an_extra_field_is_refused() -> None:
    import backend.dialogues.socrates_zero.openrouter_request_bounds_v1 as bounds

    original = bounds.REFUSAL_RECEIPT_ALLOWLIST_V1
    try:
        bounds.REFUSAL_RECEIPT_ALLOWLIST_V1 = frozenset({"seat"})
        with pytest.raises(ContractLeakError):
            _receipt()
    finally:
        bounds.REFUSAL_RECEIPT_ALLOWLIST_V1 = original


def test_a_local_refusal_never_reads_as_a_provider_failure() -> None:
    m = _measure("a" * 100)
    with pytest.raises(RequestBoundError) as caught:
        assert_request_within_bounds_v1(m, max_prompt_tokens=10)
    text = str(caught.value)
    assert "tokens" in text and "observed" in text and "limit" in text
    for word in ("provider", "upstream", "HTTP", "429", "Gemini"):
        assert word not in text
