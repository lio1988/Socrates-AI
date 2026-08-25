"""Honesty and recomputability locks for canned acquisition isolation evidence."""

from __future__ import annotations

import hashlib
import json

from backend.dialogues.socrates_zero.acquisition_isolation_evidence import (
    FROZEN_ACQUISITION_ISOLATION_EVIDENCE_MODES_V0,
    FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0,
    FROZEN_ACQUISITION_ISOLATION_RUNTIME_DIGESTS_V0,
    FROZEN_ACQUISITION_ISOLATION_SUBJECT_IDS_V0,
    acquisition_isolation_mutation_digest_v0,
)
from backend.dialogues.socrates_zero.contracts import canonical_json


def test_isolation_evidence_payloads_recompute_every_runtime_digest() -> None:
    observed = []
    for item in FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0:
        payload = json.loads(item.payload_json)
        assert canonical_json(payload) == item.payload_json
        digest = hashlib.sha256(item.payload_json.encode("utf-8")).hexdigest()
        assert digest == item.runtime_digest
        assert acquisition_isolation_mutation_digest_v0(item.scope) != digest
        observed.append((item.scope, digest))
    assert tuple(observed) == FROZEN_ACQUISITION_ISOLATION_RUNTIME_DIGESTS_V0


def test_isolation_evidence_modes_and_subjects_are_honest_sentinels() -> None:
    assert FROZEN_ACQUISITION_ISOLATION_EVIDENCE_MODES_V0 == (
        ("source", "IMMUTABLE_SOURCE_INPUT"),
        ("sibling", "TEST_OWNED_SIBLING_SENTINEL"),
        ("production", "DETACHED_PRODUCTION_SENTINEL"),
    )
    assert FROZEN_ACQUISITION_ISOLATION_SUBJECT_IDS_V0 == (
        ("source", "socrateszero-acquisition-source-input-snapshot/v0"),
        ("sibling", "socrateszero-acquisition-sibling-sentinel/v0"),
        (
            "production",
            "socrateszero-acquisition-detached-production-sentinel/v0",
        ),
    )
    production = json.loads(FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0[2].payload_json)
    assert production["production_runtime_attached"] is False
    assert production["production_authority"] == "NONE"


def test_isolation_payloads_retain_only_identity_not_prompt_or_future_outcomes() -> None:
    serialized = canonical_json(
        [json.loads(item.payload_json) for item in FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0]
    )
    assert "Is knowledge merely justified true belief?" not in serialized
    assert "Ask one concise opening Socratic question" not in serialized
    assert "expected_canonical" not in serialized
    assert "successor" not in serialized
    assert "reward" not in serialized
