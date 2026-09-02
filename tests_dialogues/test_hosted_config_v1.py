"""A deployment is decided at startup, not argued for by a request.

Every earlier transport guard answered "is this safe?" per call, from the client
address and the URL scheme. That refuses a bad call and cannot refuse a bad
*deployment*: a public preview served over plain HTTP would look correct until
the first user typed a credential into it. These tests pin the startup refusals,
and pin that no header, origin or body can move the process between modes.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.hosted_config import (
    DeploymentMode,
    HostedConfigError,
    load_hosted_config,
    readiness_report,
)
from backend.local_ced_app import create_local_ced_app
from socrates.source_authorization import VerifiedNormalLiveSourceAuthorizationV1


HOSTED = {"SOCRATES_PUBLIC_ORIGIN": "https://socrates.example"}


def _authorized_build() -> VerifiedNormalLiveSourceAuthorizationV1:
    """Stand in for a verified build.

    Readiness now consults the real source verifier, which cannot pass from a
    development checkout carrying bytecode caches. These tests are about the
    deployment contract, so they declare the build authorized and leave the
    authorization behaviour itself to the tests that exist for it.
    """
    return VerifiedNormalLiveSourceAuthorizationV1(
        authorization_id="normallivesourceauthv1_" + "0" * 64,
        source_set_digest="1" * 64,
        authorized_implementation_commit_sha="2" * 40,
        authorized_implementation_tree_sha="3" * 40,
        runtime_identity="socrates-normal-live-runtime/v1",
    )


def _client(
    env: dict,
    *,
    host: str = "127.0.0.1",
    source_verifier=_authorized_build,
) -> TestClient:
    app = create_local_ced_app(
        hosted_config=load_hosted_config(env), source_verifier=source_verifier
    )
    return TestClient(app, client=(host, 50000))


# ------------------------------------------------------------- startup mode --


def test_mode_comes_from_configuration_not_from_a_request() -> None:
    assert load_hosted_config({}).mode is DeploymentMode.LOCAL_DEVELOPMENT
    assert load_hosted_config(HOSTED).mode is DeploymentMode.HOSTED_PREVIEW


@pytest.mark.parametrize(
    "env, reason",
    [
        ({"SOCRATES_PUBLIC_ORIGIN": "http://socrates.example"}, "plain http hosted BYOK"),
        ({"SOCRATES_PUBLIC_ORIGIN": "https://*.example"}, "wildcard origin"),
        ({"SOCRATES_PUBLIC_ORIGIN": "https://x.example/app"}, "origin carrying a path"),
        ({"SOCRATES_PUBLIC_ORIGIN": "https://u:p@x.example"}, "credentials in origin"),
        ({"SOCRATES_PUBLIC_ORIGIN": "ftp://x.example"}, "unsupported scheme"),
        ({"SOCRATES_PUBLIC_ORIGIN": "   "}, "blank origin"),
        ({"SOCRATES_TRUST_PROXY": "1"}, "proxy trust with no named proxy"),
        ({"SOCRATES_MAX_ACTIVE_BYOK_RUNS_PER_CLIENT": "9"}, "per-client above global"),
        ({"SOCRATES_WORKERS": "0"}, "zero workers"),
        ({"SOCRATES_WORKERS": "-2"}, "negative workers"),
        ({"SOCRATES_ENABLE_BYOK": "perhaps"}, "non-boolean flag"),
        ({"SOCRATES_BYOK_EXECUTIONS_PER_HOUR": "many"}, "non-numeric limit"),
    ],
)
def test_unsafe_configurations_refuse_to_start(env, reason) -> None:
    with pytest.raises(HostedConfigError):
        load_hosted_config(env)


def test_plain_http_hosted_is_allowed_only_when_byok_is_off() -> None:
    """The refusal is about carrying a credential, not about HTTP as such."""
    config = load_hosted_config(
        {"SOCRATES_PUBLIC_ORIGIN": "http://internal.example", "SOCRATES_ENABLE_BYOK": "0"}
    )
    assert config.is_hosted
    assert config.enable_byok is False
    assert config.may_emit_hsts is False


def test_trusted_proxy_requires_an_explicit_named_proxy() -> None:
    ok = load_hosted_config(
        {
            **HOSTED,
            "SOCRATES_TRUST_PROXY": "1",
            "SOCRATES_TRUSTED_PROXY_HOSTS": "10.0.0.7",
        }
    )
    assert ok.trust_proxy is True
    assert ok.trusted_proxy_hosts == ("10.0.0.7",)
    assert ok.may_trust_forwarded_headers is True


def test_trusted_proxy_also_requires_a_hosted_origin() -> None:
    """A loopback server has nothing in front of it to trust."""
    with pytest.raises(HostedConfigError):
        load_hosted_config(
            {"SOCRATES_TRUST_PROXY": "1", "SOCRATES_TRUSTED_PROXY_HOSTS": "10.0.0.7"}
        )


def test_readiness_reports_multiple_workers_rather_than_pretending() -> None:
    single = load_hosted_config(HOSTED)
    assert readiness_report(single) == ("ok", ())

    many = load_hosted_config({**HOSTED, "SOCRATES_WORKERS": "4"})
    status, reasons = readiness_report(many)
    assert status == "degraded"
    assert "in_memory_limits_need_one_worker" in reasons


# ------------------------------------------------------------- mode gating ---


def test_operator_live_is_absent_by_default_and_present_when_enabled() -> None:
    with _client({}) as client:
        assert client.get("/api/council/health").json()["modes"] == {
            "byok": True,
            "operator_normal_live": False,
        }
        assert client.post(
            "/api/council/live/preflight", json={"question": "q"}
        ).status_code == 404

    with _client({"SOCRATES_ENABLE_OPERATOR_NORMAL_LIVE": "1"}) as client:
        assert client.get("/api/council/health").json()["modes"][
            "operator_normal_live"
        ] is True
        # Present now, and failing closed on source authorization rather than
        # on the route being missing.
        assert client.post(
            "/api/council/live/preflight", json={"question": "q"}
        ).status_code != 404


def test_byok_routes_disappear_when_byok_is_disabled() -> None:
    with _client({"SOCRATES_ENABLE_BYOK": "0"}) as client:
        for path in ("byok/preflight", "byok/execute", "byok/cancel"):
            response = client.post(f"/api/council/{path}", json={"question": "q"})
            assert response.status_code == 404, path


# --------------------------------------------------------- transport policy --


def test_hosted_mode_refuses_plain_http_even_from_loopback() -> None:
    """Loopback is not an escape hatch once a public origin is declared."""
    with _client(HOSTED, host="127.0.0.1") as client:
        response = client.post(
            "/api/council/byok/preflight", json={"question": "q"}
        )
    assert response.status_code == 400
    assert "secure connection" in response.json()["detail"].lower()


def test_hosted_mode_accepts_its_own_origin_and_refuses_another() -> None:
    app = create_local_ced_app(hosted_config=load_hosted_config(HOSTED))
    with TestClient(
        app, base_url="https://socrates.example", client=("203.0.113.9", 50000)
    ) as client:
        same = client.post(
            "/api/council/byok/preflight",
            json={"question": "q"},
            headers={"Origin": "https://socrates.example"},
        )
        other = client.post(
            "/api/council/byok/preflight",
            json={"question": "q"},
            headers={"Origin": "https://attacker.example"},
        )
    # The same-origin call gets past transport policy and fails closed further
    # in; the cross-origin call never gets that far.
    assert same.status_code != 403
    assert other.status_code == 403


def test_forwarded_headers_do_not_change_the_verdict() -> None:
    """A caller-supplied header must not be able to buy loopback treatment."""
    with _client(HOSTED, host="203.0.113.9") as client:
        response = client.post(
            "/api/council/byok/preflight",
            json={"question": "q"},
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "127.0.0.1",
                "X-Real-IP": "127.0.0.1",
            },
        )
    assert response.status_code == 400


# --------------------------------------------------- headers, cache, probes --


def test_no_hsts_on_loopback_http() -> None:
    with _client({}) as client:
        response = client.get("/api/council/health")
    assert "strict-transport-security" not in response.headers


def test_hsts_only_under_an_explicit_https_hosted_origin() -> None:
    app = create_local_ced_app(hosted_config=load_hosted_config(HOSTED))
    with TestClient(
        app, base_url="https://socrates.example", client=("203.0.113.9", 50000)
    ) as client:
        response = client.get("/api/council/health")
    assert "strict-transport-security" in response.headers

    # A hosted origin the config says is not https never promises HSTS.
    plain = load_hosted_config(
        {"SOCRATES_PUBLIC_ORIGIN": "http://internal.example", "SOCRATES_ENABLE_BYOK": "0"}
    )
    assert plain.may_emit_hsts is False


def test_security_headers_carry_no_unsafe_directives() -> None:
    with _client({}) as client:
        headers = client.get("/api/council/health").headers
    csp = headers["content-security-policy"]
    for directive in (
        "default-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
    ):
        assert directive in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["x-content-type-options"] == "nosniff"
    assert "camera=()" in headers["permissions-policy"]


def test_api_responses_are_never_stored_and_static_is_merely_revalidated() -> None:
    with _client({}) as client:
        assert client.get("/api/council/health").headers["cache-control"] == "no-store"
        assert (
            client.post("/api/council/byok/preflight", json={"question": "q"})
            .headers["cache-control"]
            == "no-store"
        )
        assert client.get("/").headers["cache-control"] == "no-cache"


def test_health_and_readiness_say_nothing_private() -> None:
    with _client(HOSTED) as client:
        health = client.get("/health")
        ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    body = ready.json()
    assert set(body) <= {"status", "mode", "reasons"}
    assert body["status"] in {"ok", "degraded"}

    blob = health.text + ready.text
    for forbidden in (
        "normallivesourceauthv1",
        "sha256",
        "C:\\",
        "/Users/",
        "openrouter",
        "Bearer",
        "socrates.example",
    ):
        assert forbidden not in blob, forbidden


def test_readiness_degrades_rather_than_lying_about_worker_count() -> None:
    with _client({**HOSTED, "SOCRATES_WORKERS": "3"}) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["reasons"] == ["in_memory_limits_need_one_worker"]


# --------------------------------------------------------------- limits -----


def test_configured_limits_reach_the_running_limiter() -> None:
    app = create_local_ced_app(
        hosted_config=load_hosted_config(
            {
                "SOCRATES_MAX_ACTIVE_BYOK_RUNS_GLOBAL": "5",
                "SOCRATES_MAX_ACTIVE_BYOK_RUNS_PER_CLIENT": "2",
                "SOCRATES_BYOK_PREFLIGHTS_PER_10_MIN": "3",
                "SOCRATES_BYOK_EXECUTIONS_PER_HOUR": "7",
            }
        )
    )
    limiter = app.state.byok_live_council_manager.rate_limiter
    assert limiter._max_active_global == 5
    assert limiter._max_active_per_client == 2
    assert limiter._max_preflights == 3
    assert limiter._max_executions == 7


def test_preflight_rate_limit_returns_429_with_a_bounded_retry_after() -> None:
    with _client({"SOCRATES_BYOK_PREFLIGHTS_PER_10_MIN": "2"}) as client:
        seen = [
            client.post("/api/council/byok/preflight", json={"question": "q"}).status_code
            for _ in range(3)
        ]
        limited = client.post("/api/council/byok/preflight", json={"question": "q"})
    assert 429 in seen or limited.status_code == 429
    if limited.status_code == 429:
        retry_after = int(limited.headers["retry-after"])
        assert 0 < retry_after <= 601
