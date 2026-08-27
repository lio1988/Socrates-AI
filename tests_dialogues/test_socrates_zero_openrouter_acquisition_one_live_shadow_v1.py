"""Offline locks for S7B: grants, claim store, and the one-shot transport.

Named so the shared conftest wraps every test in the acquisition boundary
tripwire: zero network, credential, provider, model, tool or CED activity. The
live transport is exercised only through injected fakes here; the real dispatch
functions are never called from this file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_live_safety_closure_v1 import (
    OpenRouterLiveSafetyModeV1,
    attest_openrouter_claim_store_readiness_v1,
    consume_openrouter_one_call_authorization_v1,
    evaluate_one_live_call_preflight_v1,
    openrouter_authorization_claim_path_v1,
    openrouter_authorization_is_consumed_v1,
    openrouter_claim_store_id_v1,
)
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    FROZEN_OPENROUTER_CLAIM_STORE_THREATS_EXCLUDED_V1,
    FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1,
    OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1,
    OPENROUTER_LIVE_INFERENCE_PATH_V1,
    OpenRouterClaimStoreGrantV1,
    OpenRouterDispatchBudgetExceeded,
    OpenRouterLiveTransportRegistrationV1,
    OpenRouterOperatorPriceGrantV1,
    OpenRouterOperatorTotalSpendGrantV1,
    _DispatchLatch,
    build_openrouter_claim_store_grant_v1,
)

ROOT = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------- grants ---


def test_operator_price_grant_refuses_float_money() -> None:
    """A float is not monetary authority, at the grant boundary too."""
    with pytest.raises(ValidationError, match="float money is not authority"):
        OpenRouterOperatorPriceGrantV1(
            operator_statement="test",
            prompt_usd_per_million_tokens=0.5,
            completion_usd_per_million_tokens="2.00",
            request_usd="0",
        )


def test_operator_total_grant_refuses_float_money() -> None:
    with pytest.raises(ValidationError, match="float money is not authority"):
        OpenRouterOperatorTotalSpendGrantV1(
            operator_statement="test",
            max_total_spend_usd=0.6,
            max_spend_picodollars=600_000_000_000,
        )


def test_price_grant_identity_changes_with_every_authorized_number() -> None:
    """A grant cannot be reused to authorize different ceilings."""
    base = dict(
        operator_statement="test",
        prompt_usd_per_million_tokens="0.50",
        completion_usd_per_million_tokens="2.00",
        request_usd="0",
    )
    original = OpenRouterOperatorPriceGrantV1(**base)
    for field, other in (
        ("prompt_usd_per_million_tokens", "0.51"),
        ("completion_usd_per_million_tokens", "2.01"),
        ("request_usd", "0.01"),
    ):
        changed = OpenRouterOperatorPriceGrantV1(**{**base, field: other})
        assert changed.grant_id != original.grant_id


def test_claim_store_grant_records_its_exclusions_and_claims_no_crypto() -> None:
    """The grant must never let the store read as stronger than it is."""
    grant = build_openrouter_claim_store_grant_v1(
        Path(r"C:\Users\spirc\AppData\Local\SocratesZero\openrouter-claim-store-v1"),
        operator_statement="operator attestation",
        repository_root=ROOT,
    )
    assert grant.trust_model == OPENROUTER_CLAIM_STORE_TRUST_MODEL_V1
    assert "UNDER_DECLARED_OPERATOR_TRUST_MODEL" in grant.trust_model
    assert grant.cryptographic_anti_rollback is False
    assert "MALICIOUS_LOCAL_ADMINISTRATOR" in grant.threats_excluded
    assert "VM_OR_SNAPSHOT_ROLLBACK" in grant.threats_excluded
    assert "DELIBERATE_FILESYSTEM_ROLLBACK" in grant.threats_excluded
    assert "PROCESS_CRASH" in grant.threats_included
    assert "CONCURRENT_DUPLICATE_CONSUMPTION" in grant.threats_included
    assert grant.grant_id.startswith("szorclaimstoregrantv1_")


def test_claim_store_grant_refuses_a_repository_or_temp_location(
    tmp_path: Path,
) -> None:
    """The store must not live where the repo or the OS may discard it."""
    with pytest.raises(ValidationError, match="outside the repository"):
        build_openrouter_claim_store_grant_v1(
            ROOT / "claim-store",
            operator_statement="operator attestation",
            repository_root=ROOT,
        )
    with pytest.raises(ValidationError, match="outside the repository"):
        build_openrouter_claim_store_grant_v1(
            tmp_path / "claim-store",
            operator_statement="operator attestation",
            repository_root=ROOT,
        )


def test_a_grant_cannot_silently_drop_a_declared_threat() -> None:
    with pytest.raises(ValidationError, match="excluded threats"):
        OpenRouterClaimStoreGrantV1(
            operator_statement="test",
            claim_store_id="szorclaimstorev1_" + "0" * 64,
            threats_included=FROZEN_OPENROUTER_CLAIM_STORE_THREATS_INCLUDED_V1,
            threats_excluded=("MALICIOUS_LOCAL_ADMINISTRATOR",),
            outside_repository=True,
            outside_temporary_directory=True,
        )


# ------------------------------------------------------------- transport ---


def test_registration_refuses_the_authorization_header_as_evidence() -> None:
    with pytest.raises(ValidationError, match="never semantic evidence"):
        OpenRouterLiveTransportRegistrationV1(
            method="POST",
            path=OPENROUTER_LIVE_INFERENCE_PATH_V1,
            body_sha256="a" * 64,
            body_length=10,
            semantic_header_names=("Content-Type", "Authorization"),
            bounded_timeout_seconds=30,
        )


def test_the_dispatch_latch_permits_one_and_then_fails_closed() -> None:
    """The second attempt raises before any socket could be opened."""
    latch = _DispatchLatch()
    assert latch.count("live_inference_post") == 0
    latch.claim("live_inference_post", 1)
    assert latch.count("live_inference_post") == 1
    with pytest.raises(OpenRouterDispatchBudgetExceeded, match="new explicit"):
        latch.claim("live_inference_post", 1)
    assert latch.count("live_inference_post") == 1


def test_the_latch_keeps_metadata_and_inference_budgets_separate() -> None:
    latch = _DispatchLatch()
    latch.claim("jit_metadata_get", 1)
    # The inference budget is untouched by a metadata GET.
    assert latch.count("live_inference_post") == 0
    latch.claim("live_inference_post", 1)
    with pytest.raises(OpenRouterDispatchBudgetExceeded):
        latch.claim("jit_metadata_get", 1)


def test_the_live_module_exposes_no_reset_or_rearm_path() -> None:
    """A second call must require a human, not a function."""
    import backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    for banned in ("def reset", "def rearm", "def clear_", "def unconsume"):
        assert banned not in source
    exported = set(module.__all__)
    assert not any(
        name.startswith(("reset", "rearm", "clear", "unconsume")) for name in exported
    )


def test_the_module_never_returns_or_stores_credential_material() -> None:
    import backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    # The credential is read at exactly the points that need it and is only ever
    # interpolated into a live header, never into a record or a return value.
    # Exactly one place in the process reads the credential.
    assert source.count("os.environ.get(OPENROUTER_CREDENTIAL_VARIABLE_V1)") == 1
    assert 'headers["Authorization"] = f"Bearer {bearer_credential}"' in source
    assert "return credential" not in source
    assert "credential_sha" not in source
    assert "hashlib.sha256(credential" not in source


# ----------------------------------------------------------- claim store ---


def _synthetic_authorization_id(seed: str) -> str:
    import hashlib

    return "szoronecallauthorizationv1_" + hashlib.sha256(
        seed.encode("utf-8")
    ).hexdigest()


def test_claim_store_consumes_once_and_rejects_the_second_attempt(
    tmp_path: Path,
) -> None:
    """Exclusive creation, proven directly on the physical store.

    Uses synthetic authorization IDs: the production authorization is never
    consumed by a test.
    """
    store = tmp_path / "store"
    store.mkdir()
    auth_id = _synthetic_authorization_id("s7b-offline-a")
    path = openrouter_authorization_claim_path_v1(store, auth_id)

    assert not openrouter_authorization_is_consumed_v1(store, auth_id)
    with path.open("xb") as handle:
        handle.write(b"{}")
    assert openrouter_authorization_is_consumed_v1(store, auth_id)

    # A second exclusive create fails even though the bytes would be identical.
    with pytest.raises(FileExistsError):
        with path.open("xb") as handle:
            handle.write(b"{}")


def test_consumption_survives_reopening_the_store(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    auth_id = _synthetic_authorization_id("s7b-offline-restart")
    openrouter_authorization_claim_path_v1(store, auth_id).write_bytes(b"{}")

    # Simulate a process restart: nothing in memory, only the durable store.
    reopened = Path(str(store))
    assert openrouter_authorization_is_consumed_v1(reopened, auth_id)


def test_sibling_authorizations_are_independent(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    first = _synthetic_authorization_id("s7b-offline-first")
    second = _synthetic_authorization_id("s7b-offline-second")
    openrouter_authorization_claim_path_v1(store, first).write_bytes(b"{}")
    assert openrouter_authorization_is_consumed_v1(store, first)
    assert not openrouter_authorization_is_consumed_v1(store, second)


def test_a_different_store_does_not_inherit_consumption(tmp_path: Path) -> None:
    """Consumption is scoped to one exact store, and the ID says which."""
    first = tmp_path / "store-a"
    second = tmp_path / "store-b"
    first.mkdir()
    second.mkdir()
    auth_id = _synthetic_authorization_id("s7b-offline-scope")
    openrouter_authorization_claim_path_v1(first, auth_id).write_bytes(b"{}")
    assert openrouter_authorization_is_consumed_v1(first, auth_id)
    assert not openrouter_authorization_is_consumed_v1(second, auth_id)
    assert openrouter_claim_store_id_v1(first) != openrouter_claim_store_id_v1(second)


@pytest.mark.parametrize(
    "bad_id",
    [
        "not-an-authorization",
        "szoronecallauthorizationv1_short",
        "szoronecallauthorizationv1_" + "g" * 64,
        "szoronecallauthorizationv1_" + "0" * 63,
    ],
)
def test_an_invalid_authorization_id_fails_closed(tmp_path: Path, bad_id: str) -> None:
    with pytest.raises(ContractValidationError):
        openrouter_authorization_claim_path_v1(tmp_path, bad_id)


def test_a_corrupted_store_location_fails_closed(tmp_path: Path) -> None:
    """A file where the store directory should be is a refusal, not a bypass."""
    blocker = tmp_path / "store"
    blocker.write_bytes(b"not a directory")
    auth_id = _synthetic_authorization_id("s7b-offline-corrupt")
    path = openrouter_authorization_claim_path_v1(blocker, auth_id)
    with pytest.raises(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(b"{}")


def test_claim_store_readiness_requires_a_live_grant_in_live_mode(
    tmp_path: Path,
) -> None:
    """A synthetic fixture may not stand in for operator evidence live."""
    store = tmp_path / "store"
    store.mkdir()
    with pytest.raises(ValidationError, match="wrong authority scope"):
        attest_openrouter_claim_store_readiness_v1(
            store,
            preflight_execution_id="s7b-test",
            mode=OpenRouterLiveSafetyModeV1.LIVE_JIT,
            ready=True,
            authorization_evidence_id="szorclaimstorefixturev1_" + "0" * 64,
        )


def test_an_unready_store_cannot_carry_authorization_evidence(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store"
    store.mkdir()
    with pytest.raises(ValidationError, match="cannot carry authorization evidence"):
        attest_openrouter_claim_store_readiness_v1(
            store,
            preflight_execution_id="s7b-test",
            mode=OpenRouterLiveSafetyModeV1.LIVE_JIT,
            ready=False,
            authorization_evidence_id="szorclaimstoregrantv1_" + "0" * 64,
        )


# ------------------------------------------------- frozen predecessor use ---


def test_s7b_adds_no_predecessor_semantic_change() -> None:
    """S7B is additive: it imports the frozen contracts, never redefines them."""
    import backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    for frozen in (
        "class OpenRouterOneCallAuthorizationV1",
        "class OpenRouterWorstCaseCostBoundV1",
        "class OpenRouterP17InputBoundProofV1",
        "def consume_openrouter_one_call_authorization_v1",
        "def evaluate_one_live_call_preflight_v1",
    ):
        assert frozen not in source


# ------------------------------------------- byte preservation, no network ---


class _FakeResponse:
    status = 200

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, _limit: int) -> bytes:
        return self._body

    def getheaders(self):
        return [("Content-Type", "application/json")]


class _RecordingConnection:
    """Captures exactly what the transport would put on the wire."""

    last = {}

    def __init__(self, host, timeout=None, context=None):
        _RecordingConnection.last = {"host": host, "timeout": timeout}

    def request(self, method, path, body=None, headers=None):
        _RecordingConnection.last.update(
            {"method": method, "path": path, "body": body, "headers": dict(headers)}
        )

    def getresponse(self):
        return _FakeResponse(b'{"ok":true}')

    def close(self):
        return None


def test_the_transport_sends_exactly_the_registered_bytes(monkeypatch) -> None:
    """Registered bytes == sent bytes, proven without touching the network."""
    import backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 as module

    body = b'{"model":"openai/gpt-4.1-mini","max_tokens":256}'
    monkeypatch.setattr(module.http.client, "HTTPSConnection", _RecordingConnection)
    monkeypatch.setattr(module, "_read_bearer_credential_v1", lambda: "test-not-a-real-key")
    monkeypatch.setattr(module, "OPENROUTER_DISPATCH_LATCH_V1", module._DispatchLatch())

    result = module.dispatch_openrouter_one_live_inference_v1(
        body_bytes=body,
        semantic_headers={"Content-Type": "application/json"},
        bounded_timeout_seconds=30,
    )

    sent = _RecordingConnection.last
    # The exact same object bytes reach the wire, unmodified and unre-serialized.
    assert sent["body"] == body
    assert sent["method"] == "POST"
    assert sent["path"] == OPENROUTER_LIVE_INFERENCE_PATH_V1
    assert sent["host"] == module.OPENROUTER_LIVE_API_HOST_V1
    assert sent["timeout"] == 30
    # The credential reaches the wire and nothing else.
    assert sent["headers"]["Authorization"].startswith("Bearer ")
    assert result.completion.completed is True
    assert result.completion.local_dispatch_count == 1
    assert result.completion.retry_count == 0


def test_no_record_of_the_dispatch_contains_credential_material(monkeypatch) -> None:
    import backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 as module

    secret = "test-sentinel-" + "not-a-real-key"
    monkeypatch.setattr(module.http.client, "HTTPSConnection", _RecordingConnection)
    monkeypatch.setattr(module, "_read_bearer_credential_v1", lambda: secret)
    monkeypatch.setattr(module, "OPENROUTER_DISPATCH_LATCH_V1", module._DispatchLatch())

    result = module.dispatch_openrouter_one_live_inference_v1(
        body_bytes=b'{"a":1}',
        semantic_headers={"Content-Type": "application/json"},
        bounded_timeout_seconds=30,
    )

    serialized = json.dumps(result.completion.model_dump(mode="json"))
    assert secret not in serialized
    assert "Bearer" not in serialized
    assert "Authorization" not in serialized
    assert secret not in json.dumps(list(result.response_headers))


def test_a_transport_failure_is_evidence_and_never_a_retry(monkeypatch) -> None:
    import backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 as module

    class _Exploding(_RecordingConnection):
        def request(self, *a, **k):
            raise TimeoutError("simulated")

    monkeypatch.setattr(module.http.client, "HTTPSConnection", _Exploding)
    monkeypatch.setattr(module, "_read_bearer_credential_v1", lambda: "test-not-a-real-key")
    latch = module._DispatchLatch()
    monkeypatch.setattr(module, "OPENROUTER_DISPATCH_LATCH_V1", latch)

    result = module.dispatch_openrouter_one_live_inference_v1(
        body_bytes=b'{"a":1}',
        semantic_headers={"Content-Type": "application/json"},
        bounded_timeout_seconds=30,
    )
    assert result.completion.completed is False
    assert result.completion.failure_class == "TimeoutError"
    # The failed attempt still consumed the budget: no automatic second try.
    assert latch.count("live_inference_post") == 1
    with pytest.raises(OpenRouterDispatchBudgetExceeded):
        module.dispatch_openrouter_one_live_inference_v1(
            body_bytes=b'{"a":1}',
            semantic_headers={"Content-Type": "application/json"},
            bounded_timeout_seconds=30,
        )


def test_dispatch_refuses_without_a_credential(monkeypatch) -> None:
    import backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 as module

    monkeypatch.setattr(module, "_read_bearer_credential_v1", lambda: None)
    latch = module._DispatchLatch()
    monkeypatch.setattr(module, "OPENROUTER_DISPATCH_LATCH_V1", latch)
    with pytest.raises(ContractValidationError, match="credential absent"):
        module.dispatch_openrouter_one_live_inference_v1(
            body_bytes=b'{"a":1}',
            semantic_headers={"Content-Type": "application/json"},
            bounded_timeout_seconds=30,
        )
    # Refused before the budget was touched.
    assert latch.count("live_inference_post") == 0


# ------------------------------- end-to-end offline dry run of the live path ---


def _operator_grants():
    """The operator's actual declared ceilings, used offline only."""
    price = OpenRouterOperatorPriceGrantV1(
        operator_statement="S7B operator price ceilings for one live shadow call",
        prompt_usd_per_million_tokens="0.50",
        completion_usd_per_million_tokens="2.00",
        request_usd="0",
    )
    total = OpenRouterOperatorTotalSpendGrantV1(
        operator_statement="S7B operator total-spend ceiling for one live call",
        max_total_spend_usd="0.60",
        max_spend_picodollars=600_000_000_000,
    )
    return price, total


def _synthetic_model_detail(context_length: int = 1_047_576) -> bytes:
    from backend.dialogues.socrates_zero.contracts import canonical_json

    return canonical_json(
        {
            "data": {
                "alias_target": None,
                "canonical_slug": "openai/gpt-4.1-mini",
                "context_length": context_length,
                "id": "openai/gpt-4.1-mini",
                "per_request_limits": None,
            }
        }
    ).encode("utf-8")


def test_the_live_path_assembles_offline_and_stays_under_the_ceiling(
    tmp_path: Path,
) -> None:
    """The exact live code path, driven by synthetic JIT bytes. No network."""
    from backend.dialogues.socrates_zero.openrouter_live_request_overlay_v2 import (
        OpenRouterOperatorScopeV1,
    )
    from backend.dialogues.socrates_zero.openrouter_one_live_shadow_runner_v1 import (
        build_s7b_preflight_v1,
        live_wire_payload_v1,
    )
    from backend.dialogues.socrates_zero.openrouter_trusted_input_bound_v1 import (
        OpenRouterInputLimitSourceScopeV1,
    )

    store = tmp_path / "store"
    store.mkdir()
    price, total = _operator_grants()
    # A synthetic run must carry fixture-scope evidence; the frozen contract
    # refuses a live grant here, which is exactly the separation we want.
    fixture_evidence = "szorclaimstorefixturev1_" + "1" * 64

    bundle = build_s7b_preflight_v1(
        model_detail_bytes=_synthetic_model_detail(),
        preflight_execution_id="s7b-offline-dry-run",
        repository_root=ROOT,
        claim_directory=store,
        price_grant=price,
        total_grant=total,
        claim_store_evidence_id=fixture_evidence,
        credential_present=True,
        mode=OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE,
        source_scope=OpenRouterInputLimitSourceScopeV1.SYNTHETIC_TEST_ONLY,
        synthetic_fixture_id="s7b-offline-dry-run-limit",
    )

    # P19 arithmetic, computed independently of the contract.
    expected = 1_047_576 * 500_000 + 256 * 2_000_000 + 0
    assert bundle.cost_bound.max_total_cost_picodollars == expected
    assert expected <= 600_000_000_000
    assert bundle.p17_proof.max_input_tokens == 1_047_576

    # Registered bytes reproduce their own digest and carry the frozen headers.
    body_bytes, headers = live_wire_payload_v1(bundle.rendered_request)
    assert len(body_bytes) == bundle.rendered_request.body_length
    assert "Authorization" not in headers
    assert headers["Content-Type"] == "application/json"

    # The request preserves every frozen control plus the operator ceilings.
    body = json.loads(bundle.rendered_request.canonical_body_json)
    assert body["model"] == "openai/gpt-4.1-mini"
    assert body["max_tokens"] == 256
    assert body["stream"] is False
    assert body["provider"]["only"] == ["azure/swedencentral"]
    assert body["provider"]["order"] == ["azure/swedencentral"]
    assert body["provider"]["allow_fallbacks"] is False
    assert body["provider"]["require_parameters"] is True
    # The renderer canonicalizes decimal money: same value, canonical form.
    from decimal import Decimal

    wire_prices = body["provider"]["max_price"]
    assert Decimal(wire_prices["prompt"]) == Decimal("0.50")
    assert Decimal(wire_prices["completion"]) == Decimal("2.00")
    assert Decimal(wire_prices["request"]) == Decimal("0")
    # And the picodollar ceilings derive from the operator's exact values.
    assert bundle.price_policy.prompt_picodollars_per_token == 500_000
    assert bundle.price_policy.completion_picodollars_per_token == 2_000_000
    assert bundle.price_policy.request_picodollars == 0


def test_a_cost_over_the_operator_ceiling_refuses_the_preflight(
    tmp_path: Path,
) -> None:
    """Over the ceiling must refuse, not round down or ask to raise it."""
    from backend.dialogues.socrates_zero.openrouter_one_live_shadow_runner_v1 import (
        build_s7b_preflight_v1,
    )
    from backend.dialogues.socrates_zero.openrouter_trusted_input_bound_v1 import (
        OpenRouterInputLimitSourceScopeV1,
    )

    store = tmp_path / "store"
    store.mkdir()
    price, _ = _operator_grants()
    tiny = OpenRouterOperatorTotalSpendGrantV1(
        operator_statement="deliberately too small",
        max_total_spend_usd="0.00001",
        max_spend_picodollars=10_000_000,
    )
    # A synthetic run must carry fixture-scope evidence; the frozen contract
    # refuses a live grant here, which is exactly the separation we want.
    fixture_evidence = "szorclaimstorefixturev1_" + "1" * 64
    bundle = build_s7b_preflight_v1(
        model_detail_bytes=_synthetic_model_detail(),
        preflight_execution_id="s7b-offline-over-ceiling",
        repository_root=ROOT,
        claim_directory=store,
        price_grant=price,
        total_grant=tiny,
        claim_store_evidence_id=fixture_evidence,
        credential_present=True,
        mode=OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE,
        source_scope=OpenRouterInputLimitSourceScopeV1.SYNTHETIC_TEST_ONLY,
        synthetic_fixture_id="s7b-offline-over-ceiling-limit",
    )
    assert not bundle.authorized
