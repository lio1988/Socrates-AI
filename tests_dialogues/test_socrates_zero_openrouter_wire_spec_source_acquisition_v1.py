"""Offline tests for the one-shot OpenRouter wire-spec source retriever v1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_wire_spec_source_v1 import (
    FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1,
    OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1,
    OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1,
    OpenRouterWireExtractFormatV1,
    OpenRouterWireRetrievalLogV1,
    OpenRouterWireRetrievalStatusV1,
    render_openrouter_wire_source_plan_v1,
)
from scripts import acquire_socrates_zero_openrouter_wire_spec_sources_v1 as acquire


def _synthetic_document(record: object) -> bytes:
    extract_format = record.extract_format
    anchors = record.required_anchors
    if extract_format is OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS:
        return (
            "openapi: 3.1.0\n"
            "paths:\n"
            "  /chat/completions:\n"
            "    post:\n"
            "      responses: {}\n"
            "components:\n"
            "  schemas:\n"
            "    OpenRouterMetadata:\n"
            "      type: object\n"
            "    EndpointInfo:\n"
            "      type: object\n"
            "    RouterAttempt:\n"
            "      type: object\n"
            "    PipelineStage:\n"
            "      type: object\n"
        ).encode("utf-8")
    if extract_format is OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS:
        return (
            "# Synthetic official document\n\n"
            + "\n\n".join(
                f"## {anchor}\n\nEvidence for {anchor}." for anchor in anchors
            )
            + "\n"
        ).encode("utf-8")
    if extract_format is OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS:
        return (
            "<html><body><main>"
            + "".join(
                f"<section><h2>{anchor}</h2><p>Evidence for {anchor}.</p></section>"
                for anchor in anchors
            )
            + "</main></body></html>"
        ).encode("utf-8")
    return json.dumps(
        {anchor: {"type": "object"} for anchor in anchors},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _materialize_plan(root: Path) -> None:
    destination = root / OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(render_openrouter_wire_source_plan_v1())


def _fake_fetch(record: object, budget: object) -> acquire._FetchedDocument:
    body = _synthetic_document(record)
    budget.response_bytes += len(body)
    return acquire._FetchedDocument(
        final_locator=record.canonical_public_locator,
        redirect_chain=(),
        status=200,
        raw_content_type_header=f"{record.expected_media_types[0]}; charset=utf-8",
        media_type=record.expected_media_types[0],
        response_body=body,
    )


def test_extractors_produce_exact_ranges_that_build_frozen_snapshots(tmp_path: Path) -> None:
    for record in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records:
        body = _synthetic_document(record)
        extraction = acquire._extract_document(body, record)
        assert extraction.raw_source_ranges
        assert extraction.relevant_anchors == record.required_anchors
        fetched = acquire._FetchedDocument(
            final_locator=record.canonical_public_locator,
            redirect_chain=(),
            status=200,
            raw_content_type_header=f"{record.expected_media_types[0]}; charset=utf-8",
            media_type=record.expected_media_types[0],
            response_body=body,
        )
        bundle = acquire._build_retained_bundle(
            tmp_path,
            record,
            fetched,
            extraction,
            "2026-08-26T12:00:00Z",
        )
        assert bundle.snapshot.missing_required_anchors == ()
        assert bundle.snapshot.relevant_anchors == record.required_anchors
        assert bundle.raw_bytes
        assert bundle.canonical_bytes
        assert bundle.snapshot.response_content_bytes == len(body)


def test_one_shot_offline_acquisition_publishes_complete_derived_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _materialize_plan(tmp_path)
    monkeypatch.setattr(acquire, "_fetch_one", _fake_fetch)

    log = acquire.acquire_openrouter_wire_spec_sources_v1(tmp_path)

    assert isinstance(log, OpenRouterWireRetrievalLogV1)
    assert len(log.events) == 6
    assert len(log.snapshots) == 6
    assert all(
        event.status is OpenRouterWireRetrievalStatusV1.RETAINED
        for event in log.events
    )
    assert log.failed_documentation_fetches == 0
    assert log.official_public_document_fetches == 6
    assert log.official_public_page_inspections == 0
    assert log.authenticated_api_calls == 0
    assert log.credential_accesses == 0
    assert log.provider_inference_calls == 0
    assert log.model_executions == 0
    assert log.paid_requests == 0
    assert log.ced_runtime_tool_calls == 0

    persisted = tmp_path / OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1
    assert persisted.is_file()
    parsed = OpenRouterWireRetrievalLogV1.model_validate_json(persisted.read_text())
    assert parsed == log
    for snapshot in log.snapshots:
        assert (tmp_path / snapshot.retained_raw_evidence_path).is_file()
        assert (tmp_path / snapshot.retained_canonical_extract_path).is_file()

    with pytest.raises(ContractValidationError, match="retrieval log already exists"):
        acquire.acquire_openrouter_wire_spec_sources_v1(tmp_path)


def test_preflight_rejects_missing_or_mutated_plan(tmp_path: Path) -> None:
    with pytest.raises(ContractValidationError, match="source plan is absent"):
        acquire._preflight(tmp_path)
    _materialize_plan(tmp_path)
    plan_path = tmp_path / OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1
    plan_path.write_bytes(plan_path.read_bytes() + b" ")
    with pytest.raises(ContractValidationError, match="differs from the frozen contract"):
        acquire._preflight(tmp_path)
