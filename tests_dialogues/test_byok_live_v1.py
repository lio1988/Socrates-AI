"""Offline BYOK tests: credential boundary, isolation, transport and lifecycle.

Nothing here reaches the network. The live adapter classes and the canonical
council are real; only the wire transport is a deterministic stub, and it
records which credential each dispatch carried so a test can assert whose key
paid for a call.

One distinction is load-bearing throughout: the user's key is *supposed* to be
in the body of the same-origin execute request. That is the request whose whole
purpose is to deliver it. A test that flagged it there would be testing the
wrong thing, so the leak assertions cover every surface except that one.
"""

from __future__ import annotations

import asyncio
import copy
import json
import pickle
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.dialogues import byok_live
from backend.dialogues.byok_live import (
    BYOK_RUN_MODE,
    ByokCredentialRejectedError,
    ByokLiveCouncilManager,
    ByokRateLimitedError,
    ByokRateLimiter,
    ReleasedCredentialError,
    RunScopedCredential,
    make_byok_dispatch_v1,
)
from backend.dialogues.normal_live import NormalLiveCouncilManager
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    SocratesLiveOpenRouterAdapter,
)
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    MAX_BEARER_CREDENTIAL_BYTES_V1,
    validate_bearer_credential_v1,
)
from backend.local_ced_app import MAX_REQUEST_BODY_BYTES, create_local_ced_app
from tests_dialogues.test_normal_live_lifecycle import (
    _DeterministicWireTransport,
    _receipt,
)


#: Two distinct canaries, so a cross-run leak is visible as the *wrong* value
#: rather than merely as "a key was present".
KEY_A = "sk-or-v1-CANARY-ALPHA-NOT-A-REAL-KEY-000000000000"
KEY_B = "sk-or-v1-CANARY-BRAVO-NOT-A-REAL-KEY-111111111111"
SERVER_KEY = "sk-or-v1-OPERATOR-SERVER-KEY-NOT-A-REAL-KEY-999"

QUESTION = "Does a council of models beat one model asked three times?"


class _CapturingTransport(_DeterministicWireTransport):
    """The scripted wire stub, plus a record of every credential it saw."""

    def __init__(self) -> None:
        super().__init__()
        self.credentials: list[str] = []

    def __call__(self, **kwargs):
        self.credentials.append(kwargs.pop("bearer_credential"))
        return super().__call__(**kwargs)

    @property
    def distinct_credentials(self) -> set[str]:
        return set(self.credentials)


def _manager(tmp_path: Path, transport=None, **kwargs) -> ByokLiveCouncilManager:
    return ByokLiveCouncilManager(
        source_verifier=_receipt,
        transport=transport
        or (lambda **_kw: pytest.fail("transport must remain unreachable")),
        run_root=tmp_path / "runs",
        **kwargs,
    )


def _run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------- credential boundary --


def test_run_scoped_credential_is_redacted_and_cannot_be_serialized() -> None:
    credential = RunScopedCredential(KEY_A)

    for rendering in (repr(credential), str(credential), f"{credential}", format(credential)):
        assert KEY_A not in rendering
        assert "RunScopedCredential" in rendering

    for attempt in (
        lambda: copy.copy(credential),
        lambda: copy.deepcopy(credential),
        lambda: pickle.dumps(credential),
    ):
        with pytest.raises(TypeError):
            attempt()

    assert credential.reveal() == KEY_A
    credential.release()
    assert credential.released
    with pytest.raises(ReleasedCredentialError):
        credential.reveal()
    credential.release()  # idempotent, because every cleanup path may call it


def test_released_credential_cannot_dispatch() -> None:
    credential = RunScopedCredential(KEY_A)
    seen: list[str] = []
    dispatch = make_byok_dispatch_v1(
        credential, transport=lambda **kw: seen.append(kw["bearer_credential"])
    )
    dispatch(
        body_bytes=b"{}", semantic_headers={}, bounded_timeout_seconds=1,
        process_dispatch_limit=1,
    )
    assert seen == [KEY_A]

    credential.release()
    with pytest.raises(ReleasedCredentialError):
        dispatch(
            body_bytes=b"{}", semantic_headers={}, bounded_timeout_seconds=1,
            process_dispatch_limit=1,
        )
    assert seen == [KEY_A]


@pytest.mark.parametrize(
    "value",
    [
        "sk-with\r\nInjected: header",
        "sk-with\nnewline",
        "sk-with\rcarriage",
        "sk-with\x00nul",
        "sk-with\x7fdelete",
        "sk-with\x01control",
        "",
        "   ",
        "x" * (MAX_BEARER_CREDENTIAL_BYTES_V1 + 1),
        None,
        12345,
    ],
)
def test_credential_validation_refuses_injection_and_junk(value) -> None:
    with pytest.raises(Exception) as caught:
        validate_bearer_credential_v1(value)
    # The rejection must not quote the value, its length or any fragment.
    message = str(caught.value)
    if isinstance(value, str) and value.strip():
        assert value not in message
        assert str(len(value)) not in message


def test_credential_whitespace_policy_is_strip_then_validate() -> None:
    assert validate_bearer_credential_v1(f"  {KEY_A}\n") == KEY_A
    assert RunScopedCredential(f"\t{KEY_A}  ").reveal() == KEY_A


def test_credential_rejected_before_the_preflight_is_consumed(tmp_path: Path) -> None:
    manager = _manager(tmp_path)

    async def exercise() -> None:
        public = await manager.create_preflight(QUESTION)
        with pytest.raises(ByokCredentialRejectedError):
            await manager.start_run(public["preflight_id"], "bad\r\nkey")
        # A rejected key must not burn a one-use capability.
        record = await manager.preflight_store.inspect_pending(public["preflight_id"])
        assert record.state == "pending"

    _run(exercise())


# ------------------------------------------------------------ API contract ---


def _client(manager: ByokLiveCouncilManager, *, host: str = "127.0.0.1") -> TestClient:
    # BYOK requires loopback HTTP or genuine HTTPS, so the test client must
    # present a real client address rather than the default sentinel.
    return TestClient(
        create_local_ced_app(byok_live_manager=manager), client=(host, 50000)
    )


def test_byok_preflight_refuses_a_credential_field(tmp_path: Path) -> None:
    with _client(_manager(tmp_path)) as client:
        response = client.post(
            "/api/council/byok/preflight",
            json={"question": QUESTION, "openrouter_api_key": KEY_A},
        )
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid council request."}
    assert KEY_A not in response.text


def test_byok_execute_refuses_unknown_fields_without_echoing_the_body(
    tmp_path: Path,
) -> None:
    with _client(_manager(tmp_path)) as client:
        response = client.post(
            "/api/council/byok/execute",
            json={
                "preflight_id": "nlpf_" + "a" * 36,
                "confirmed": True,
                "openrouter_api_key": KEY_A,
                "model": "attacker/choice",
            },
        )
    assert response.status_code == 422
    assert KEY_A not in response.text
    assert "attacker/choice" not in response.text


def test_byok_execute_is_post_only(tmp_path: Path) -> None:
    with _client(_manager(tmp_path)) as client:
        # No GET route exists for it, by either refusal.
        assert client.get("/api/council/byok/execute").status_code in {404, 405}


def test_byok_refuses_cross_origin(tmp_path: Path) -> None:
    with _client(_manager(tmp_path)) as client:
        response = client.post(
            "/api/council/byok/preflight",
            json={"question": QUESTION},
            headers={"Origin": "https://attacker.example"},
        )
    assert response.status_code == 403
    assert "Cross-origin" in response.json()["detail"]


def test_byok_refuses_non_loopback_plain_http(tmp_path: Path) -> None:
    with _client(_manager(tmp_path), host="203.0.113.9") as client:
        response = client.post(
            "/api/council/byok/preflight", json={"question": QUESTION}
        )
    assert response.status_code == 400
    assert "secure connection" in response.json()["detail"].lower()


def test_oversized_request_body_is_refused(tmp_path: Path) -> None:
    with _client(_manager(tmp_path)) as client:
        response = client.post(
            "/api/council/byok/execute",
            content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413


def test_security_headers_are_present_and_have_no_unsafe_inline(
    tmp_path: Path,
) -> None:
    with _client(_manager(tmp_path)) as client:
        response = client.get("/api/council/health")
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "camera=()" in response.headers["permissions-policy"]
    # HSTS is a promise only a TLS origin can keep.
    assert "strict-transport-security" not in response.headers


# --------------------------------------------------------- no key fallback ---


def test_byok_never_uses_the_server_environment_credential(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", SERVER_KEY)
    transport = _CapturingTransport()
    manager = _manager(tmp_path, transport=transport)

    async def exercise() -> None:
        public = await manager.create_preflight(QUESTION)
        run = await manager.start_run(public["preflight_id"], KEY_A)
        await run.task

    _run(exercise())

    assert transport.credentials, "the council made no dispatch"
    assert transport.distinct_credentials == {KEY_A}
    assert SERVER_KEY not in transport.credentials


def test_absent_credential_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", SERVER_KEY)
    manager = _manager(tmp_path)

    async def exercise() -> None:
        public = await manager.create_preflight(QUESTION)
        with pytest.raises(ByokCredentialRejectedError):
            await manager.start_run(public["preflight_id"], "")

    _run(exercise())


def test_operator_normal_live_still_reads_the_environment(tmp_path: Path) -> None:
    """The operator path must be untouched: it takes no credential argument."""
    import inspect

    normal = inspect.signature(NormalLiveCouncilManager.start_run)
    byok = inspect.signature(ByokLiveCouncilManager.start_run)
    assert list(normal.parameters) == ["self", "preflight_id"]
    assert "credential_value" in byok.parameters


# --------------------------------------------------------------- isolation ---


def test_two_concurrent_runs_use_only_their_own_key(tmp_path: Path) -> None:
    transport_a = _CapturingTransport()
    transport_b = _CapturingTransport()
    manager_a = _manager(tmp_path / "a", transport=transport_a)
    manager_b = _manager(tmp_path / "b", transport=transport_b)

    async def exercise() -> None:
        public_a = await manager_a.create_preflight(QUESTION)
        public_b = await manager_b.create_preflight(QUESTION)
        run_a = await manager_a.start_run(public_a["preflight_id"], KEY_A)
        run_b = await manager_b.start_run(public_b["preflight_id"], KEY_B)
        await asyncio.gather(run_a.task, run_b.task)

    _run(exercise())

    assert transport_a.distinct_credentials == {KEY_A}
    assert transport_b.distinct_credentials == {KEY_B}
    assert KEY_B not in transport_a.credentials
    assert KEY_A not in transport_b.credentials


def test_a_consumed_preflight_cannot_be_replayed_with_another_key(
    tmp_path: Path,
) -> None:
    transport = _CapturingTransport()
    manager = _manager(tmp_path, transport=transport)

    async def exercise() -> None:
        public = await manager.create_preflight(QUESTION)
        run = await manager.start_run(public["preflight_id"], KEY_A)
        await run.task
        with pytest.raises(Exception):
            await manager.start_run(public["preflight_id"], KEY_B)

    _run(exercise())
    assert KEY_B not in transport.credentials


# --------------------------------------------------------------- lifecycle ---


def test_credential_is_released_after_a_completed_run(tmp_path: Path) -> None:
    transport = _CapturingTransport()
    manager = _manager(tmp_path, transport=transport)
    held: list[RunScopedCredential] = []
    original = byok_live.RunScopedCredential

    class _Observed(original):  # type: ignore[misc, valid-type]
        def __init__(self, value: str) -> None:
            super().__init__(value)
            held.append(self)

    byok_live.RunScopedCredential = _Observed
    try:

        async def exercise() -> None:
            public = await manager.create_preflight(QUESTION)
            run = await manager.start_run(public["preflight_id"], KEY_A)
            await run.task

        _run(exercise())
    finally:
        byok_live.RunScopedCredential = original

    assert held, "no credential was constructed"
    assert all(credential.released for credential in held)


def test_credential_is_released_when_the_run_fails(tmp_path: Path) -> None:
    def exploding(**_kwargs):
        raise RuntimeError("provider unavailable")

    manager = _manager(tmp_path, transport=exploding)
    held: list[RunScopedCredential] = []
    original = byok_live.RunScopedCredential

    class _Observed(original):  # type: ignore[misc, valid-type]
        def __init__(self, value: str) -> None:
            super().__init__(value)
            held.append(self)

    byok_live.RunScopedCredential = _Observed
    try:

        async def exercise() -> None:
            public = await manager.create_preflight(QUESTION)
            run = await manager.start_run(public["preflight_id"], KEY_A)
            await run.task

        _run(exercise())
    finally:
        byok_live.RunScopedCredential = original

    assert held
    assert all(credential.released for credential in held)


# ------------------------------------------------------------ rate limiting --


def test_preflight_rate_limit_is_bounded_and_reports_retry_after() -> None:
    now = [1000.0]
    limiter = ByokRateLimiter(
        max_preflights_per_client=2,
        preflight_window_seconds=600.0,
        monotonic_clock=lambda: now[0],
    )
    limiter.check_preflight("client")
    limiter.check_preflight("client")
    with pytest.raises(ByokRateLimitedError) as caught:
        limiter.check_preflight("client")
    assert caught.value.retry_after_seconds > 0
    # A different client is unaffected, and the window really expires.
    limiter.check_preflight("other")
    now[0] += 601.0
    limiter.check_preflight("client")


def test_active_run_caps_are_per_client_and_global() -> None:
    limiter = ByokRateLimiter(
        max_active_per_client=1,
        max_active_global=2,
        max_executions_per_client=99,
    )
    limiter.check_execution("a")
    limiter.enter_run("a")
    with pytest.raises(ByokRateLimitedError):
        limiter.check_execution("a")
    limiter.check_execution("b")
    limiter.enter_run("b")
    with pytest.raises(ByokRateLimitedError):
        limiter.check_execution("c")
    limiter.exit_run("a")
    limiter.exit_run("b")
    assert limiter.active_total == 0


def test_limiter_never_stores_a_credential() -> None:
    limiter = ByokRateLimiter()
    limiter.check_preflight("client")
    limiter.check_execution("client")
    limiter.enter_run("client")
    blob = repr(limiter.__dict__)
    assert KEY_A not in blob
    assert "sk-" not in blob


def test_limiter_evicts_rather_than_growing_without_bound() -> None:
    limiter = ByokRateLimiter(max_tracked_clients=8, max_preflights_per_client=99)
    for index in range(64):
        limiter.check_preflight(f"client-{index}")
    assert len(limiter._preflights) <= 9


# ------------------------------------------------------- end-to-end offline --


def test_byok_offline_end_to_end_uses_the_real_runtime_ced_and_live_adapters(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", SERVER_KEY)
    transport = _CapturingTransport()
    manager = _manager(tmp_path, transport=transport)
    observed: dict = {}

    async def exercise() -> None:
        public = await manager.create_preflight(QUESTION)
        assert public["run_mode"] == BYOK_RUN_MODE
        assert public["credential_required"] is True
        assert "approval_reference" not in public
        observed["public"] = public
        run = await manager.start_run(public["preflight_id"], KEY_A)
        await run.task
        observed["run"] = run
        observed["snapshot"] = run.public_snapshot()
        observed["events"] = list(run._store.events)

    _run(exercise())

    run = observed["run"]
    assert run.status in {"completed", "blocked"}
    # Real canonical council, real live adapter class, stub wire only.
    assert transport.calls > 0
    assert transport.distinct_credentials == {KEY_A}
    assert run.ced is not None
    adapters = run.ced.registry.all_adapters()
    assert len(adapters) == 3
    assert all(
        isinstance(adapter, SocratesLiveOpenRouterAdapter) for adapter in adapters
    )

    # Every public surface, and every artifact on disk.
    surfaces = [
        json.dumps(observed["public"], ensure_ascii=False),
        json.dumps(observed["snapshot"], ensure_ascii=False),
        json.dumps(observed["events"], ensure_ascii=False, default=str),
    ]
    run_root = tmp_path / "runs"
    artifacts = [
        path.read_text(encoding="utf-8")
        for path in run_root.rglob("*")
        if path.is_file()
    ]
    assert artifacts, "the run wrote no artifacts"
    for blob in surfaces + artifacts:
        assert KEY_A not in blob
        assert SERVER_KEY not in blob
        assert "openrouter_api_key" not in blob
        assert "Authorization" not in blob


def test_public_surfaces_carry_no_credential_after_an_http_round_trip(
    tmp_path: Path,
) -> None:
    transport = _CapturingTransport()
    manager = _manager(tmp_path, transport=transport)
    app = create_local_ced_app(byok_live_manager=manager)

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        preflight = client.post(
            "/api/council/byok/preflight", json={"question": QUESTION}
        )
        assert preflight.status_code == 200
        assert KEY_A not in preflight.text
        body = preflight.json()

        execute = client.post(
            "/api/council/byok/execute",
            json={
                "preflight_id": body["preflight_id"],
                "confirmed": True,
                "openrouter_api_key": KEY_A,
            },
        )
        assert execute.status_code == 202
        # The response acknowledges a run, never the credential.
        assert set(execute.json()) == {"run_id", "status"}
        assert KEY_A not in execute.text
        run_id = execute.json()["run_id"]

        assert manager.get_run(run_id) is not None
        status = client.get(f"/api/council/{run_id}")
        assert status.status_code == 200
        assert KEY_A not in status.text
        assert status.headers["cache-control"] == "no-store"
