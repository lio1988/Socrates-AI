"""Pre-result locks for the bounded OpenRouter wire-source evidence plan.

The tests are local-only.  They validate frozen contracts and synthetic
receipts; they never retrieve a source or run the manifest sufficiency gate.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)
from backend.dialogues.socrates_zero import openrouter_wire_spec_source_v1 as source
from backend.dialogues.socrates_zero.openrouter_wire_spec_source_v1 import (
    FROZEN_OPENROUTER_WIRE_CANONICALIZATION_POLICY_V1,
    FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1,
    FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_RECORDS_V1,
    FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1,
    OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1,
    OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1,
    OpenRouterWireCanonicalizationPolicyV1,
    OpenRouterWireExtractFormatV1,
    OpenRouterWireRawFragmentRangeV1,
    OpenRouterWireRedirectHopV1,
    OpenRouterWireRedirectOutcomeV1,
    OpenRouterWireRetainedSourceSnapshotV1,
    OpenRouterWireRetrievalErrorCodeV1,
    OpenRouterWireRetrievalEventV1,
    OpenRouterWireRetrievalLogV1,
    OpenRouterWireRetrievalPolicyV1,
    OpenRouterWireRetrievalStatusV1,
    OpenRouterWireSourcePlanRecordV1,
    OpenRouterWireSourcePlanV1,
    build_openrouter_wire_retained_source_snapshot_v1,
    canonicalize_openrouter_wire_extract_v1,
    render_openrouter_wire_source_plan_v1,
    sha256_bytes_v1,
    verify_openrouter_wire_retained_source_bytes_v1,
)


def _identified_payload(value: object, identity_field: str) -> dict[str, object]:
    payload = value.model_dump(mode="json")  # type: ignore[attr-defined]
    payload.pop(identity_field)
    return payload


def _assert_content_id(
    value: object,
    identity_field: str,
    prefix: str,
) -> None:
    assert getattr(value, identity_field) == stable_contract_id(
        prefix,
        _identified_payload(value, identity_field),
    )


def _snapshot_for(
    record: OpenRouterWireSourcePlanRecordV1,
) -> tuple[OpenRouterWireRetainedSourceSnapshotV1, bytes, bytes]:
    sequence = next(
        index
        for index, candidate in enumerate(
            FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records,
            start=1,
        )
        if candidate.plan_record_id == record.plan_record_id
    )
    if record.extract_format is OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS:
        paths_block = (
            "paths:\n"
            "  /chat/completions:\n"
            "    post:\n"
            "      responses: {}\n"
        )
        components_block = (
            "components:\n"
            "  schemas:\n"
            "    OpenRouterMetadata: {type: object}\n"
            "    EndpointInfo: {type: object}\n"
            "    RouterAttempt: {type: object}\n"
            "    PipelineStage: {type: object}\n"
        )
        response = ("openapi: 3.1.0\n" + paths_block + components_block).encode(
            "utf-8"
        )
        paths_start = response.index(b"paths:")
        components_start = response.index(b"components:")
        raw_source_ranges = (
            (paths_start, components_start),
            (components_start, len(response)),
        )
    elif record.extract_format is OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS:
        response = (
            "# Synthetic official document\n\n"
            + "\n\n".join(
                f"## {anchor}\n\nEvidence for {anchor}."
                for anchor in record.required_anchors
            )
            + "\n"
        ).encode("utf-8")
        raw_source_ranges = ((0, len(response)),)
    elif record.extract_format is OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS:
        response = (
            "<html><body><nav>volatile navigation</nav><main>"
            + "".join(
                f"<section><h2>{anchor}</h2><p>Evidence for {anchor}.</p></section>"
                for anchor in record.required_anchors
            )
            + "</main><script>volatile analytics</script></body></html>"
        ).encode("utf-8")
        raw_source_ranges = ((0, len(response)),)
    else:
        response = json.dumps(
            {anchor: {"type": "object"} for anchor in record.required_anchors},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        raw_source_ranges = ((0, len(response)),)
    return build_openrouter_wire_retained_source_snapshot_v1(
        plan_record=record,
        retrieved_utc=f"2026-08-26T00:{sequence:02d}:01Z",
        final_resolved_locator=record.canonical_public_locator,
        redirect_chain=(),
        raw_content_type_header=(
            f"{record.expected_media_types[0]}; charset=utf-8"
        ),
        response_content=response,
        raw_source_ranges=raw_source_ranges,
    )


def _event_for(
    sequence: int,
    snapshot: OpenRouterWireRetainedSourceSnapshotV1,
) -> OpenRouterWireRetrievalEventV1:
    return OpenRouterWireRetrievalEventV1(
        sequence=sequence,
        plan_record_id=snapshot.plan_record_id,
        source_key=snapshot.source_key,
        started_utc=f"2026-08-26T00:{sequence:02d}:00Z",
        completed_utc=snapshot.retrieved_utc,
        status=OpenRouterWireRetrievalStatusV1.RETAINED,
        redirect_chain=snapshot.redirect_chain,
        http_status=200,
        final_resolved_locator=snapshot.final_resolved_locator,
        raw_content_type_header=snapshot.raw_content_type_header,
        media_type=snapshot.media_type,
        response_content_bytes=snapshot.response_content_bytes,
        retained_snapshot_id=snapshot.snapshot_id,
        response_bytes_received=snapshot.response_content_bytes,
    )


def _retained_receipts() -> tuple[
    tuple[OpenRouterWireRetrievalEventV1, ...],
    tuple[OpenRouterWireRetainedSourceSnapshotV1, ...],
]:
    snapshots = tuple(
        _snapshot_for(record)[0]
        for record in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records
    )
    events = tuple(
        _event_for(sequence, snapshot)
        for sequence, snapshot in enumerate(snapshots, start=1)
    )
    return events, snapshots


def _retrieval_log(
    events: tuple[OpenRouterWireRetrievalEventV1, ...],
    snapshots: tuple[OpenRouterWireRetainedSourceSnapshotV1, ...],
) -> OpenRouterWireRetrievalLogV1:
    failures = sum(
        event.status is not OpenRouterWireRetrievalStatusV1.RETAINED
        for event in events
    )
    return OpenRouterWireRetrievalLogV1(
        events=events,
        snapshots=snapshots,
        official_public_document_fetches=len(events),
        official_public_page_inspections=(
            FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.maximum_public_page_inspections
        ),
        redirects=sum(len(event.redirect_chain) for event in events),
        failed_documentation_fetches=failures,
        official_public_response_bytes_received=sum(
            event.response_bytes_received for event in events
        ),
        retained_raw_source_bytes=sum(
            snapshot.raw_source_byte_length for snapshot in snapshots
        ),
        retained_canonical_extract_bytes=sum(
            snapshot.canonical_extract_byte_length for snapshot in snapshots
        ),
        total_retained_evidence_bytes=sum(
            snapshot.raw_source_byte_length
            + snapshot.canonical_extract_byte_length
            for snapshot in snapshots
        ),
    )


def test_frozen_source_inventory_bounds_and_official_locators_are_exact() -> None:
    plan = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1
    policy = FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1
    records = plan.source_records

    assert records == FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_RECORDS_V1
    assert len(records) == policy.maximum_official_document_fetches
    assert policy.allowed_official_domains == ("openrouter.ai",)
    assert policy.maximum_public_page_inspections == 0
    assert policy.maximum_redirects_per_source == 1
    assert policy.redirect_policy == "SAME_ORIGIN_HTTPS_ONLY_OTHERWISE_FAIL_CLOSED"
    assert policy.maximum_response_bytes_per_source == 8_388_608
    assert policy.maximum_total_response_bytes == 20_971_520
    assert policy.total_retained_evidence_byte_cap == 1_048_576
    assert policy.retrieval_timeout_seconds == 20
    assert policy.retry_count == 0
    assert (
        policy.authenticated_requests,
        policy.credential_accesses,
        policy.provider_inference_calls,
        policy.model_executions,
        policy.paid_requests,
        policy.ced_runtime_tool_calls,
    ) == (0, 0, 0, 0, 0, 0)

    keys = tuple(record.source_key for record in records)
    locators = tuple(record.canonical_public_locator for record in records)
    assert tuple(zip(keys, locators)) == (
        ("ORWIRE-S01-OPENAPI", "https://openrouter.ai/openapi.yaml"),
        (
            "ORWIRE-S02-ROUTER-METADATA",
            "https://openrouter.ai/docs/guides/features/router-metadata.md",
        ),
        (
            "ORWIRE-S03-CHAT-REFERENCE",
            "https://openrouter.ai/docs/api/api-reference/chat/"
            "send-chat-completion-request.md",
        ),
        (
            "ORWIRE-S04-RESPONSE-CACHE",
            "https://openrouter.ai/docs/guides/features/response-caching",
        ),
        (
            "ORWIRE-S05-PROVIDER-ROUTING",
            "https://openrouter.ai/docs/guides/routing/provider-selection.md",
        ),
        (
            "ORWIRE-S06-MODEL-FALLBACKS",
            "https://openrouter.ai/docs/guides/routing/model-fallbacks",
        ),
    )
    assert len(set(keys)) == len(keys)
    assert len(set(locators)) == len(locators)
    for sequence, (key, record) in enumerate(zip(keys, records), start=1):
        assert key.startswith(f"ORWIRE-S{sequence:02d}-")
        parsed = urlsplit(record.canonical_public_locator)
        assert parsed.scheme == "https"
        assert parsed.hostname in policy.allowed_official_domains
        assert parsed.username is None and parsed.password is None
        assert parsed.port in (None, 443)
        assert parsed.query == "" and parsed.fragment == ""
        assert record.expected_media_types
        assert record.expected_evidence_scope
        assert record.required_anchors
        assert len(record.expected_media_types) == len(set(record.expected_media_types))
        assert len(record.expected_evidence_scope) == len(
            set(record.expected_evidence_scope)
        )
        assert len(record.required_anchors) == len(set(record.required_anchors))


def test_all_frozen_plan_ids_and_rendered_bytes_are_content_derived() -> None:
    _assert_content_id(
        FROZEN_OPENROUTER_WIRE_CANONICALIZATION_POLICY_V1,
        "policy_id",
        "szorwirecanonv1",
    )
    _assert_content_id(
        FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1,
        "policy_id",
        "szorwireretrievalpolicyv1",
    )
    for record in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_RECORDS_V1:
        _assert_content_id(
            record,
            "plan_record_id",
            "szorwiresourceplanrecordv1",
        )
    _assert_content_id(
        FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1,
        "source_plan_id",
        "szorwiresourceplanv1",
    )
    assert FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id == (
        "szorwiresourceplanv1_"
        "19b0fcbaab0004ab5db0b7d529f8eaf055ccbcba75b68b48a3a059c540bb98cc"
    )

    rendered = render_openrouter_wire_source_plan_v1()
    assert rendered == (
        canonical_json(
            FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.model_dump(mode="json")
        )
        + "\n"
    ).encode("utf-8")
    assert rendered.endswith(b"\n") and not rendered.endswith(b"\n\n")
    assert b"\r" not in rendered
    assert sha256_bytes_v1(rendered) == hashlib.sha256(rendered).hexdigest()


def test_materialized_source_plan_is_the_exact_canonical_frozen_render() -> None:
    persisted_path = (
        Path(__file__).resolve().parents[1]
        / OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1
    )
    persisted = persisted_path.read_bytes()
    rendered = render_openrouter_wire_source_plan_v1()

    assert persisted == rendered
    assert len(persisted) == 9_030
    assert sha256_bytes_v1(persisted) == (
        "cfaec71b93a88114e9378fe297d8cd5ec9645e6c747877eadd622003de9760a5"
    )


def test_plan_contracts_reject_forged_ids_and_unofficial_or_duplicate_sources() -> None:
    record = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_RECORDS_V1[0]
    payload = record.model_dump(mode="json")
    payload["plan_record_id"] = "szorwiresourceplanrecordv1_" + "0" * 64
    with pytest.raises(ValidationError, match="source-plan record ID mismatch"):
        OpenRouterWireSourcePlanRecordV1.model_validate(payload)

    for locator in (
        "http://openrouter.ai/openapi.yaml",
        "https://example.com/openapi.yaml",
        "https://user@openrouter.ai/openapi.yaml",
        "https://openrouter.ai/openapi.yaml?mutable=true",
        "https://openrouter.ai/openapi.yaml#fragment",
    ):
        payload = record.model_dump(mode="json")
        payload["plan_record_id"] = None
        payload["canonical_public_locator"] = locator
        with pytest.raises(ValidationError, match="allowed canonical URL"):
            OpenRouterWireSourcePlanRecordV1.model_validate(payload)

    payload = record.model_dump(mode="json")
    payload["plan_record_id"] = None
    payload["required_anchors"] = [record.required_anchors[0]] * 2
    with pytest.raises(ValidationError, match="empty or duplicated"):
        OpenRouterWireSourcePlanRecordV1.model_validate(payload)

    plan_payload = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.model_dump(mode="json")
    plan_payload["source_plan_id"] = None
    plan_payload["source_records"][-1] = plan_payload["source_records"][0]
    with pytest.raises(ValidationError, match="duplicated"):
        OpenRouterWireSourcePlanV1.model_validate(plan_payload)

    for contract, identity_field, model_type in (
        (
            FROZEN_OPENROUTER_WIRE_CANONICALIZATION_POLICY_V1,
            "policy_id",
            OpenRouterWireCanonicalizationPolicyV1,
        ),
        (
            FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1,
            "policy_id",
            OpenRouterWireRetrievalPolicyV1,
        ),
        (
            FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1,
            "source_plan_id",
            OpenRouterWireSourcePlanV1,
        ),
    ):
        payload = contract.model_dump(mode="json")
        payload[identity_field] = "forged"
        with pytest.raises(ValidationError, match="ID mismatch"):
            model_type.model_validate(payload)


def test_text_and_json_canonicalization_is_deterministic_and_type_preserving() -> None:
    decomposed = "Cafe\u0301"
    text = ("\r\n\t" + decomposed + "  \rline\t \n\n").encode("utf-8")
    canonical_text = canonicalize_openrouter_wire_extract_v1(
        text,
        OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS,
    )
    assert canonical_text == "\tCaf\u00e9  \nline\t \n".encode("utf-8")
    assert canonicalize_openrouter_wire_extract_v1(
        canonical_text,
        OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS,
    ) == canonical_text

    raw_json = b'{ "z": "1", "a": [true, 0, 0.0, null, {"b": 2}] }'
    reordered_json = b'{"a":[true,0,0.0,null,{"b":2}],"z":"1"}'
    expected = b'{"a":[true,0,0.0,null,{"b":2}],"z":"1"}\n'
    assert canonicalize_openrouter_wire_extract_v1(
        raw_json,
        OpenRouterWireExtractFormatV1.JSON,
    ) == expected
    assert canonicalize_openrouter_wire_extract_v1(
        reordered_json,
        OpenRouterWireExtractFormatV1.JSON,
    ) == expected
    assert canonicalize_openrouter_wire_extract_v1(
        expected,
        OpenRouterWireExtractFormatV1.JSON,
    ) == expected

    parsed = json.loads(expected)
    assert type(parsed["a"][0]) is bool
    assert type(parsed["a"][1]) is int
    assert type(parsed["a"][2]) is float
    assert parsed["a"][3] is None
    assert type(parsed["z"]) is str

    html = (
        b"<html><body><nav>ignore me</nav><main><h1> Visible  title </h1>"
        b"<p>Cache\t Hits</p><script>ignore me too</script>"
        b"<p>X-OpenRouter-Cache</p></main></body></html>"
    )
    canonical_html = canonicalize_openrouter_wire_extract_v1(
        html,
        OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS,
    )
    assert canonical_html == (
        b"Visible title\nCache Hits\nX-OpenRouter-Cache\n"
    )
    assert canonicalize_openrouter_wire_extract_v1(
        canonical_html,
        OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS,
    ) == canonical_html


@pytest.mark.parametrize(
    "payload",
    (
        b'{"a":1,"a":2}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
        b'{"value":1e999}',
    ),
)
def test_json_canonicalization_rejects_duplicates_and_nonfinite_values(
    payload: bytes,
) -> None:
    with pytest.raises((ContractValidationError, ValueError)):
        canonicalize_openrouter_wire_extract_v1(
            payload,
            OpenRouterWireExtractFormatV1.JSON,
        )


@pytest.mark.parametrize("payload", (b"", b"\xff", b"valid\x00invalid"))
def test_canonicalization_rejects_empty_invalid_utf8_or_nul(payload: bytes) -> None:
    with pytest.raises(ContractValidationError):
        canonicalize_openrouter_wire_extract_v1(
            payload,
            OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS,
        )


def test_retained_snapshots_bind_plan_digests_paths_and_anchor_accounting() -> None:
    for record in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records:
        snapshot, retained_raw, canonical_extract = _snapshot_for(record)
        verify_openrouter_wire_retained_source_bytes_v1(
            snapshot,
            retained_raw,
            canonical_extract,
        )
        assert snapshot.source_plan_id == FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id
        assert snapshot.plan_record_id == record.plan_record_id
        assert snapshot.source_key == record.source_key
        assert snapshot.canonical_public_locator == record.canonical_public_locator
        assert snapshot.final_resolved_locator == record.canonical_public_locator
        assert snapshot.raw_content_type_header == (
            f"{record.expected_media_types[0]}; charset=utf-8"
        )
        assert snapshot.media_type == record.expected_media_types[0]
        assert snapshot.response_content_bytes >= len(retained_raw)
        assert snapshot.raw_source_byte_length == len(retained_raw)
        assert snapshot.raw_source_sha256 == hashlib.sha256(retained_raw).hexdigest()
        assert (
            snapshot.raw_source_representation
            == "CONCATENATED_EXACT_SOURCE_BYTE_RANGES"
        )
        assert tuple(fragment.ordinal for fragment in snapshot.raw_fragment_ranges) == tuple(
            range(1, len(snapshot.raw_fragment_ranges) + 1)
        )
        retained = b""
        prior_source_end = -1
        for fragment in snapshot.raw_fragment_ranges:
            retained_slice = retained_raw[
                fragment.retained_byte_start : fragment.retained_byte_end_exclusive
            ]
            assert fragment.source_byte_start > prior_source_end
            assert fragment.source_byte_end_exclusive <= snapshot.response_content_bytes
            assert fragment.retained_byte_start == len(retained)
            assert fragment.byte_length == len(retained_slice)
            assert fragment.sha256 == hashlib.sha256(retained_slice).hexdigest()
            retained += retained_slice
            assert fragment.retained_byte_end_exclusive == len(retained)
            prior_source_end = fragment.source_byte_end_exclusive - 1
            _assert_content_id(fragment, "fragment_id", "szorwirerawfragmentv1")
        assert retained == retained_raw
        assert len(retained) == snapshot.raw_source_byte_length
        assert hashlib.sha256(retained).hexdigest() == snapshot.raw_source_sha256
        assert snapshot.canonical_extract_byte_length == len(canonical_extract)
        assert snapshot.canonical_extract_sha256 == hashlib.sha256(
            canonical_extract
        ).hexdigest()
        assert snapshot.relevant_anchors == record.required_anchors
        assert snapshot.missing_required_anchors == ()
        raw_extension = {
            OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS: "yaml",
            OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS: "md",
            OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS: "html",
            OpenRouterWireExtractFormatV1.JSON: "json",
        }[record.extract_format]
        canonical_extension = (
            "txt"
            if record.extract_format
            is OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS
            else raw_extension
        )
        directory = (
            f"{OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1}/{record.source_key}"
        )
        assert snapshot.retained_raw_evidence_path == (
            f"{directory}/raw_source_extract.{raw_extension}"
        )
        assert snapshot.retained_canonical_extract_path == (
            f"{directory}/canonical_extract.{canonical_extension}"
        )
        _assert_content_id(snapshot, "snapshot_id", "szorwiresnapshotv1")


def test_snapshot_byte_verifier_rejects_raw_canonical_fragment_and_anchor_drift() -> None:
    record = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records[0]
    snapshot, retained_raw, canonical_extract = _snapshot_for(record)

    with pytest.raises(
        ContractValidationError,
        match="retained source bytes do not match snapshot",
    ):
        verify_openrouter_wire_retained_source_bytes_v1(
            snapshot,
            b"X" + retained_raw[1:],
            canonical_extract,
        )

    tampered_canonical = b"tampered\n" + canonical_extract
    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["canonical_extract_byte_length"] = len(tampered_canonical)
    payload["canonical_extract_sha256"] = sha256_bytes_v1(tampered_canonical)
    canonical_drift_snapshot = OpenRouterWireRetainedSourceSnapshotV1.model_validate(
        payload
    )
    with pytest.raises(
        ContractValidationError,
        match="canonical extract is not reproducible",
    ):
        verify_openrouter_wire_retained_source_bytes_v1(
            canonical_drift_snapshot,
            retained_raw,
            tampered_canonical,
        )

    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["raw_fragment_ranges"][0]["fragment_id"] = None
    payload["raw_fragment_ranges"][0]["sha256"] = "0" * 64
    fragment_drift_snapshot = OpenRouterWireRetainedSourceSnapshotV1.model_validate(
        payload
    )
    with pytest.raises(
        ContractValidationError,
        match="retained raw fragment digest mismatch",
    ):
        verify_openrouter_wire_retained_source_bytes_v1(
            fragment_drift_snapshot,
            retained_raw,
            canonical_extract,
        )

    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["relevant_anchors"] = list(record.required_anchors[1:])
    payload["missing_required_anchors"] = [record.required_anchors[0]]
    anchor_drift_snapshot = OpenRouterWireRetainedSourceSnapshotV1.model_validate(
        payload
    )
    with pytest.raises(
        ContractValidationError,
        match="anchor observations are false",
    ):
        verify_openrouter_wire_retained_source_bytes_v1(
            anchor_drift_snapshot,
            retained_raw,
            canonical_extract,
        )


def test_raw_fragment_contract_rejects_forged_ids_lengths_gaps_and_overlaps() -> None:
    record = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records[0]
    snapshot, _, _ = _snapshot_for(record)
    fragment = snapshot.raw_fragment_ranges[0]

    payload = fragment.model_dump(mode="json")
    payload["fragment_id"] = "szorwirerawfragmentv1_" + "0" * 64
    with pytest.raises(ValidationError, match="raw fragment ID mismatch"):
        OpenRouterWireRawFragmentRangeV1.model_validate(payload)

    payload = fragment.model_dump(mode="json")
    payload["fragment_id"] = None
    payload["byte_length"] += 1
    with pytest.raises(ValidationError, match="raw fragment range length mismatch"):
        OpenRouterWireRawFragmentRangeV1.model_validate(payload)

    second = snapshot.raw_fragment_ranges[1]
    for mutation in (
        {"ordinal": 3},
        {
            "retained_byte_start": second.retained_byte_start + 1,
            "retained_byte_end_exclusive": second.retained_byte_end_exclusive + 1,
        },
        {
            "source_byte_start": second.source_byte_start - 1,
            "source_byte_end_exclusive": second.source_byte_end_exclusive - 1,
        },
        {
            "source_byte_start": second.source_byte_start + 1,
            "source_byte_end_exclusive": second.source_byte_end_exclusive + 1,
        },
    ):
        payload = snapshot.model_dump(mode="json")
        payload["snapshot_id"] = None
        payload["raw_fragment_ranges"][1].update(mutation)
        payload["raw_fragment_ranges"][1]["fragment_id"] = None
        with pytest.raises(
            ValidationError,
            match="ordinals are not canonical|overlap or leave a gap",
        ):
            OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)


def test_retained_snapshot_rejects_plan_drift_anchor_overlap_and_forged_content() -> None:
    record = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records[0]
    snapshot, _, _ = _snapshot_for(record)

    for field_name, value in (
        ("source_key", "ORWIRE-S99-FORGED"),
        ("canonical_public_locator", "https://openrouter.ai/changed"),
        ("media_type", "application/x-unplanned"),
        ("revalidation_trigger", "CHANGED"),
    ):
        payload = snapshot.model_dump(mode="json")
        payload["snapshot_id"] = None
        payload[field_name] = value
        with pytest.raises(
            ValidationError,
            match="source plan|predeclared|header-derived",
        ):
            OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)

    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["final_resolved_locator"] = "https://example.com/source"
    with pytest.raises(ValidationError, match="allowed canonical URL"):
        OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)

    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["missing_required_anchors"] = [snapshot.relevant_anchors[0]]
    with pytest.raises(ValidationError, match="present and missing"):
        OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)

    for field_name, value in (
        ("raw_source_sha256", "0" * 64),
        ("canonical_extract_byte_length", snapshot.canonical_extract_byte_length + 1),
    ):
        payload = snapshot.model_dump(mode="json")
        payload[field_name] = value
        with pytest.raises(ValidationError, match="snapshot ID mismatch"):
            OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)

    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["retained_raw_evidence_path"] = "changed/raw.bin"
    with pytest.raises(ValidationError, match="escapes its frozen root"):
        OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)

    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["retained_raw_evidence_path"] = (
        f"{OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1}/"
        "ORWIRE-S99-FORGED/raw.bin"
    )
    with pytest.raises(ValidationError, match="not the frozen paths"):
        OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)

    followed_redirect = OpenRouterWireRedirectHopV1(
        ordinal=1,
        source_locator=record.canonical_public_locator,
        http_status=302,
        target_locator="https://openrouter.ai/redirected-source",
    )
    assert (
        followed_redirect.outcome
        is OpenRouterWireRedirectOutcomeV1.FOLLOWED_SAME_ORIGIN_HTTPS
    )
    _assert_content_id(
        followed_redirect,
        "redirect_hop_id",
        "szorwireredirecthopv1",
    )
    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["redirect_chain"] = [followed_redirect.model_dump(mode="json")]
    with pytest.raises(ValidationError, match="final locator is unexplained"):
        OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)

    payload["final_resolved_locator"] = "https://openrouter.ai/redirected-source"
    redirected = OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)
    _assert_content_id(redirected, "snapshot_id", "szorwiresnapshotv1")

    second_redirect = OpenRouterWireRedirectHopV1(
        ordinal=2,
        source_locator=followed_redirect.target_locator,
        http_status=307,
        target_locator="https://openrouter.ai/redirect-two",
    )
    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["redirect_chain"] = [
        followed_redirect.model_dump(mode="json"),
        second_redirect.model_dump(mode="json"),
    ]
    payload["final_resolved_locator"] = second_redirect.target_locator
    with pytest.raises(ValidationError, match="redirect limit exceeded"):
        OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)

    rejected_redirect = OpenRouterWireRedirectHopV1(
        ordinal=1,
        source_locator=record.canonical_public_locator,
        http_status=302,
        target_locator="https://example.com/redirected-source",
    )
    assert (
        rejected_redirect.outcome
        is OpenRouterWireRedirectOutcomeV1.REJECTED_BY_POLICY
    )
    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = None
    payload["redirect_chain"] = [rejected_redirect.model_dump(mode="json")]
    with pytest.raises(ValidationError, match="final locator is unexplained"):
        OpenRouterWireRetainedSourceSnapshotV1.model_validate(payload)


def test_retrieval_events_and_log_ids_counters_and_sequence_are_derived() -> None:
    events, snapshots = _retained_receipts()
    assert len(events) == len(FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records)
    assert tuple(event.sequence for event in events) == tuple(
        range(1, len(events) + 1)
    )
    assert tuple(event.source_key for event in events) == tuple(
        record.source_key
        for record in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records
    )
    for event in events:
        assert "response_content_sha256" not in event.model_dump(mode="json")
        _assert_content_id(event, "event_id", "szorwirefetcheventv1")

    log = _retrieval_log(events, snapshots)
    assert log.snapshots == snapshots
    assert log.official_public_document_fetches == len(events)
    assert log.failed_documentation_fetches == sum(
        event.status is not OpenRouterWireRetrievalStatusV1.RETAINED
        for event in events
    )
    assert log.redirects == sum(len(event.redirect_chain) for event in events)
    assert log.official_public_response_bytes_received == sum(
        event.response_bytes_received for event in events
    )
    assert log.retained_raw_source_bytes == sum(
        snapshot.raw_source_byte_length for snapshot in snapshots
    )
    assert log.retained_canonical_extract_bytes == sum(
        snapshot.canonical_extract_byte_length for snapshot in snapshots
    )
    assert log.total_retained_evidence_bytes == (
        log.retained_raw_source_bytes + log.retained_canonical_extract_bytes
    )
    assert (
        log.authenticated_api_calls,
        log.credential_accesses,
        log.provider_inference_calls,
        log.model_executions,
        log.paid_requests,
        log.ced_runtime_tool_calls,
    ) == (0, 0, 0, 0, 0, 0)
    _assert_content_id(log, "retrieval_log_id", "szorwireretrievallogv1")


def test_retrieval_events_and_log_reject_incomplete_or_nonderived_evidence() -> None:
    events, snapshots = _retained_receipts()
    event = events[0]
    payload = event.model_dump(mode="json")
    payload["event_id"] = None
    payload["retained_snapshot_id"] = None
    with pytest.raises(ValidationError, match="retained retrieval event is incomplete"):
        OpenRouterWireRetrievalEventV1.model_validate(payload)

    payload = event.model_dump(mode="json")
    payload["event_id"] = None
    payload["status"] = OpenRouterWireRetrievalStatusV1.FETCH_FAILED.value
    payload["error_code"] = None
    with pytest.raises(ValidationError, match="lacks an error code"):
        OpenRouterWireRetrievalEventV1.model_validate(payload)

    payload = event.model_dump(mode="json")
    payload["event_id"] = "szorwirefetcheventv1_" + "0" * 64
    with pytest.raises(ValidationError, match="retrieval event ID mismatch"):
        OpenRouterWireRetrievalEventV1.model_validate(payload)

    payload = event.model_dump(mode="json")
    payload["event_id"] = None
    payload["response_bytes_received"] += 1
    with pytest.raises(ValidationError, match="byte count is inconsistent"):
        OpenRouterWireRetrievalEventV1.model_validate(payload)

    first_record = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records[0]
    rejected_hop = OpenRouterWireRedirectHopV1(
        ordinal=1,
        source_locator=first_record.canonical_public_locator,
        http_status=302,
        target_locator="https://example.com/cross-origin",
    )
    rejected_redirect = OpenRouterWireRetrievalEventV1(
        sequence=1,
        plan_record_id=first_record.plan_record_id or "",
        source_key=first_record.source_key,
        started_utc="2026-08-26T00:01:00Z",
        completed_utc="2026-08-26T00:01:01Z",
        status=OpenRouterWireRetrievalStatusV1.REDIRECT_REJECTED,
        redirect_chain=(rejected_hop,),
        http_status=302,
        final_resolved_locator=first_record.canonical_public_locator,
        response_bytes_received=0,
        error_code=OpenRouterWireRetrievalErrorCodeV1.REDIRECT_POLICY_REJECTED,
    )
    _assert_content_id(rejected_redirect, "event_id", "szorwirefetcheventv1")
    payload = rejected_redirect.model_dump(mode="json")
    payload["event_id"] = None
    payload["redirect_chain"] = []
    with pytest.raises(ValidationError, match="redirect evidence is inconsistent"):
        OpenRouterWireRetrievalEventV1.model_validate(payload)

    mixed_events = (rejected_redirect,) + events[1:]
    mixed_snapshots = snapshots[1:]
    mixed_log = _retrieval_log(mixed_events, mixed_snapshots)
    assert mixed_log.failed_documentation_fetches == 1
    assert mixed_log.redirects == 1
    assert mixed_log.official_public_response_bytes_received == sum(
        item.response_bytes_received for item in mixed_events
    )
    _assert_content_id(mixed_log, "retrieval_log_id", "szorwireretrievallogv1")

    log = _retrieval_log(events, snapshots)
    for field_name, value, error in (
        (
            "official_public_document_fetches",
            log.official_public_document_fetches - 1,
            "fetch count is not event-derived",
        ),
        (
            "failed_documentation_fetches",
            1,
            "activity counters are not derived",
        ),
        ("redirects", 1, "activity counters are not derived"),
        (
            "official_public_response_bytes_received",
            log.official_public_response_bytes_received + 1,
            "activity counters are not derived",
        ),
        (
            "retained_raw_source_bytes",
            log.retained_raw_source_bytes + 1,
            "activity counters are not derived",
        ),
        (
            "retained_canonical_extract_bytes",
            log.retained_canonical_extract_bytes + 1,
            "activity counters are not derived",
        ),
        (
            "total_retained_evidence_bytes",
            log.total_retained_evidence_bytes + 1,
            "activity counters are not derived",
        ),
    ):
        payload = log.model_dump(mode="json")
        payload["retrieval_log_id"] = None
        payload[field_name] = value
        with pytest.raises(ValidationError, match=error):
            OpenRouterWireRetrievalLogV1.model_validate(payload)

    payload = log.model_dump(mode="json")
    payload["retrieval_log_id"] = None
    payload["events"] = list(reversed(payload["events"]))
    with pytest.raises(ValidationError, match="canonical sequence"):
        OpenRouterWireRetrievalLogV1.model_validate(payload)

    payload = log.model_dump(mode="json")
    payload["retrieval_log_id"] = None
    payload["snapshots"] = list(reversed(payload["snapshots"]))
    with pytest.raises(ValidationError, match="snapshots do not match retained events"):
        OpenRouterWireRetrievalLogV1.model_validate(payload)

    snapshot_payload = snapshots[0].model_dump(mode="json")
    snapshot_payload["snapshot_id"] = None
    snapshot_payload["retrieved_utc"] = "2026-08-26T00:01:02Z"
    divergent_snapshot = OpenRouterWireRetainedSourceSnapshotV1.model_validate(
        snapshot_payload
    )
    event_payload = events[0].model_dump(mode="json")
    event_payload["event_id"] = None
    event_payload["retained_snapshot_id"] = divergent_snapshot.snapshot_id
    relinked_event = OpenRouterWireRetrievalEventV1.model_validate(event_payload)
    payload = log.model_dump(mode="json")
    payload["retrieval_log_id"] = None
    payload["events"][0] = relinked_event.model_dump(mode="json")
    payload["snapshots"][0] = divergent_snapshot.model_dump(mode="json")
    with pytest.raises(ValidationError, match="event and snapshot bytes diverge"):
        OpenRouterWireRetrievalLogV1.model_validate(payload)

    assert log.official_public_page_inspections == (
        FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.maximum_public_page_inspections
    )
    payload = log.model_dump(mode="json")
    payload["retrieval_log_id"] = None
    payload["official_public_page_inspections"] = 1
    with pytest.raises(ValidationError):
        OpenRouterWireRetrievalLogV1.model_validate(payload)


def test_source_contract_module_is_import_inert_and_has_no_external_seams() -> None:
    source_path = Path(source.__file__).resolve()
    text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(source_path))
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    forbidden_imports = {
        "aiohttp",
        "http.client",
        "httpx",
        "keyring",
        "openai",
        "os",
        "requests",
        "socket",
        "ssl",
        "subprocess",
        "urllib.request",
    }
    assert imports.isdisjoint(forbidden_imports)
    assert not any(
        fragment in imported
        for imported in imports
        for fragment in (
            "openrouter_provider",
            "provider_registry",
            "openrouter_route_controls_parser",
            "openrouter_route_controls_renderer",
            "openrouter_route_controls_evaluation",
            "ced",
        )
    )
    assert calls.isdisjoint(
        {
            "connect",
            "create_connection",
            "getaddrinfo",
            "getenv",
            "open",
            "read_bytes",
            "read_text",
            "request",
            "run_adapter",
            "urlopen",
            "write_bytes",
            "write_text",
        }
    )
    assert "openrouter_acquisition_cases" not in text
