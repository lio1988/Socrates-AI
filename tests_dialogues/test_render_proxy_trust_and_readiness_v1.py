"""A TLS-terminating platform in front of the service, and a probe that means it.

Two gaps were reproduced against the previous authorized build. First,
``SOCRATES_TRUST_PROXY`` was parsed and validated and then consumed by nothing,
so a hosted deployment behind a proxy that terminates TLS refused every BYOK
request as insecure while the setting that looked like the fix did nothing.
Second, ``/ready`` answered 200 from a build whose source authorization could
not pass, which is the one answer a load balancer must never be given.

These tests pin both, and pin the thing that makes the first one safe: a
forwarded header is believed only where the deployment says something in front
of this process rewrites it, and even then only the value that caller could not
choose.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

import pytest
from fastapi.testclient import TestClient

from backend.dialogues.byok_live import ByokLiveCouncilManager, ByokRateLimiter
from backend.hosted_config import (
    PLATFORM_EDGE_TRUST_BASIS,
    HostedConfigError,
    load_hosted_config,
    readiness_report,
)
from backend.local_ced_app import create_local_ced_app
from socrates.source_authorization import (
    NormalLiveSourceAuthorizationError,
    VerifiedNormalLiveSourceAuthorizationV1,
    verify_production_normal_live_source_authorization_v1,
)


ORIGIN = "https://socrates.onrender.test"

HOSTED_UNTRUSTED = {"SOCRATES_PUBLIC_ORIGIN": ORIGIN}
HOSTED_TRUSTED = {
    "SOCRATES_PUBLIC_ORIGIN": ORIGIN,
    "SOCRATES_TRUST_PROXY": "true",
    "SOCRATES_TRUSTED_PROXY_HOSTS": PLATFORM_EDGE_TRUST_BASIS,
}
HOSTED_TRUSTED_PEER = {
    "SOCRATES_PUBLIC_ORIGIN": ORIGIN,
    "SOCRATES_TRUST_PROXY": "true",
    "SOCRATES_TRUSTED_PROXY_HOSTS": "10.201.0.7,10.201.0.8",
}

#: The address the platform edge presents to the service. Nothing about it is
#: special; the point is that it is not the public client's address.
EDGE_PEER = ("10.201.0.7", 44321)


def _authorized_build() -> VerifiedNormalLiveSourceAuthorizationV1:
    """An authorized build, without shelling out to Git in every test.

    A real receipt rather than a convenient stand-in: the manager checks the
    exact type before it believes a verifier, which is the property that stops
    a loose test double from ever authorizing anything in production.
    """
    return VerifiedNormalLiveSourceAuthorizationV1(
        authorization_id="normallivesourceauthv1_" + "0" * 64,
        source_set_digest="1" * 64,
        authorized_implementation_commit_sha="2" * 40,
        authorized_implementation_tree_sha="3" * 40,
        runtime_identity="socrates-normal-live-runtime/v1",
    )


def _unauthorized_build() -> VerifiedNormalLiveSourceAuthorizationV1:
    raise NormalLiveSourceAuthorizationError("Normal Live source authorization failed.")


def _byok_manager(config):
    """A real manager on a scratch run root, with the build declared authorized.

    These tests are about the transport boundary and the limiter, and the
    development checkout cannot pass real verification, so the authorization
    gate is stubbed here and exercised for real in the readiness tests below.
    """
    return ByokLiveCouncilManager(
        source_verifier=_authorized_build,
        run_root=Path(mkdtemp(prefix="byok-proxy-test-")),
        rate_limiter=ByokRateLimiter(
            max_active_per_client=config.max_active_byok_runs_per_client,
            max_active_global=config.max_active_byok_runs_global,
            max_preflights_per_client=config.byok_preflights_per_10_min,
            max_executions_per_client=config.byok_executions_per_hour,
        ),
    )


def _app(env: dict, *, source_verifier=_authorized_build):
    config = load_hosted_config(env)
    return create_local_ced_app(
        hosted_config=config,
        source_verifier=source_verifier,
        byok_live_manager=_byok_manager(config),
    )


def _client(env: dict, *, peer=EDGE_PEER, source_verifier=_authorized_build):
    return TestClient(_app(env, source_verifier=source_verifier), client=peer)


def _preflight(client: TestClient, *, origin: str = ORIGIN, **headers):
    sent = {} if origin is None else {"Origin": origin}
    sent.update(headers)
    return client.post(
        "/api/council/byok/preflight",
        json={"question": "What makes a test of an argument fair?"},
        headers=sent,
    )


# ------------------------------------------------- the configuration is real --


def test_trust_proxy_configuration_is_consumed() -> None:
    """The same request, the same headers, decided by configuration alone."""
    with _client(HOSTED_UNTRUSTED) as ignoring:
        refused = _preflight(ignoring, **{"X-Forwarded-Proto": "https"})
    with _client(HOSTED_TRUSTED) as trusting:
        accepted = _preflight(trusting, **{"X-Forwarded-Proto": "https"})

    assert refused.status_code == 400
    assert accepted.status_code != 400
    assert accepted.status_code == 200


def test_trusted_hosted_https_is_accepted() -> None:
    with _client(HOSTED_TRUSTED) as client:
        response = _preflight(client, **{"X-Forwarded-Proto": "https"})
    assert response.status_code == 200
    body = response.json()
    assert body["run_mode"] == "byok_live"
    assert body["credential_required"] is True


def test_spoofed_forwarded_proto_is_refused_when_no_proxy_is_trusted() -> None:
    """Any caller may send this header. Without a trust boundary it is noise."""
    with _client(HOSTED_UNTRUSTED) as client:
        response = _preflight(client, **{"X-Forwarded-Proto": "https"})
    assert response.status_code == 400
    assert response.json() == {
        "detail": "A secure connection is required for this request."
    }


def test_hosted_request_without_forwarded_evidence_is_refused() -> None:
    with _client(HOSTED_TRUSTED) as client:
        response = _preflight(client)
    assert response.status_code == 400


def test_untrusted_peer_cannot_use_the_peer_allowlist() -> None:
    """Trust keyed on a peer address means that address and not another."""
    with _client(HOSTED_TRUSTED_PEER, peer=("203.0.113.9", 51000)) as stranger:
        refused = _preflight(stranger, **{"X-Forwarded-Proto": "https"})
    with _client(HOSTED_TRUSTED_PEER, peer=EDGE_PEER) as edge:
        accepted = _preflight(edge, **{"X-Forwarded-Proto": "https"})
    assert refused.status_code == 400
    assert accepted.status_code == 200


def test_local_development_never_trusts_a_forwarded_scheme() -> None:
    """A developer's own machine cannot spoof its way into hosted semantics."""
    with _client({}, peer=("127.0.0.1", 50000)) as client:
        response = _preflight(client, origin=None, **{"X-Forwarded-Proto": "https"})
    # Loopback is allowed to use plain HTTP on its own merits, so this proves
    # the scheme was never rewritten rather than that the request was refused.
    assert response.status_code == 200
    assert "strict-transport-security" not in response.headers


def test_proxy_trust_cannot_be_enabled_in_local_development() -> None:
    with pytest.raises(HostedConfigError):
        load_hosted_config(
            {
                "SOCRATES_TRUST_PROXY": "true",
                "SOCRATES_TRUSTED_PROXY_HOSTS": PLATFORM_EDGE_TRUST_BASIS,
            }
        )


@pytest.mark.parametrize(
    "hosts, reason",
    [
        ("platform-edge,10.0.0.1", "two different trust bases at once"),
        ("*", "a wildcard pretending to be an allowlist"),
        ("proxy.internal", "a name this process cannot compare a peer against"),
        ("10.0.0.300", "a malformed address"),
    ],
)
def test_malformed_trust_bases_refuse_to_start(hosts, reason) -> None:
    with pytest.raises(HostedConfigError):
        load_hosted_config({**HOSTED_UNTRUSTED, "SOCRATES_TRUST_PROXY": "true",
                            "SOCRATES_TRUSTED_PROXY_HOSTS": hosts})


def test_naming_a_proxy_without_trusting_it_refuses_to_start() -> None:
    with pytest.raises(HostedConfigError):
        load_hosted_config(
            {**HOSTED_UNTRUSTED, "SOCRATES_TRUSTED_PROXY_HOSTS": "10.201.0.7"}
        )


# --------------------------------------------------------- client identity ----


def _limited(env: dict, *, peer=EDGE_PEER):
    """One preflight per client, so the second one names the identity used."""
    return _client({**env, "SOCRATES_BYOK_PREFLIGHTS_PER_10_MIN": "1"}, peer=peer)


def test_two_hosted_public_clients_get_distinct_rate_limit_identities() -> None:
    with _limited(HOSTED_TRUSTED) as client:
        first = _preflight(
            client,
            **{"X-Forwarded-Proto": "https", "X-Forwarded-For": "198.51.100.4"},
        )
        second = _preflight(
            client,
            **{"X-Forwarded-Proto": "https", "X-Forwarded-For": "198.51.100.5"},
        )
    # Both succeed: one user exhausting a quota must not throttle everyone
    # behind the same platform edge.
    assert first.status_code == 200
    assert second.status_code == 200


def test_one_hosted_client_still_exhausts_its_own_quota() -> None:
    with _limited(HOSTED_TRUSTED) as client:
        first = _preflight(
            client,
            **{"X-Forwarded-Proto": "https", "X-Forwarded-For": "198.51.100.4"},
        )
        again = _preflight(
            client,
            **{"X-Forwarded-Proto": "https", "X-Forwarded-For": "198.51.100.4"},
        )
    assert first.status_code == 200
    assert again.status_code == 429


def test_a_client_cannot_mint_identities_by_prepending_forwarded_for() -> None:
    """The proxy appends what it saw, so only the last entry is evidence."""
    with _limited(HOSTED_TRUSTED) as client:
        first = _preflight(
            client,
            **{
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "1.2.3.4, 198.51.100.4",
            },
        )
        again = _preflight(
            client,
            **{
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "9.9.9.9, 198.51.100.4",
            },
        )
    assert first.status_code == 200
    assert again.status_code == 429


def test_untrusted_forwarded_client_ip_is_ignored() -> None:
    """With no trusted proxy the socket peer is the identity, headers aside."""
    with _limited({}, peer=("127.0.0.1", 50000)) as client:
        first = _preflight(client, origin=None, **{"X-Forwarded-For": "198.51.100.4"})
        again = _preflight(client, origin=None, **{"X-Forwarded-For": "198.51.100.5"})
    assert first.status_code == 200
    assert again.status_code == 429


# ------------------------------------------------------------------- HSTS -----


def test_hsts_is_emitted_for_a_trusted_hosted_https_request() -> None:
    with _client(HOSTED_TRUSTED) as client:
        response = client.get(
            "/health",
            headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "198.51.100.4"},
        )
    assert response.headers["strict-transport-security"].startswith("max-age=")


def test_hsts_is_absent_for_an_untrusted_spoofed_forwarded_proto() -> None:
    with _client(HOSTED_UNTRUSTED, peer=("203.0.113.9", 51000)) as client:
        response = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert "strict-transport-security" not in response.headers


def test_hsts_is_absent_on_local_plain_http() -> None:
    with _client({}, peer=("127.0.0.1", 50000)) as client:
        response = client.get("/health")
    assert "strict-transport-security" not in response.headers


# -------------------------------------------------------------- readiness -----


def test_ready_is_200_for_an_authorized_build() -> None:
    with _client(HOSTED_TRUSTED) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_is_503_for_an_unauthorized_build() -> None:
    with _client(HOSTED_TRUSTED, source_verifier=_unauthorized_build) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert "source_not_authorized" in body["reasons"]


def test_ready_is_503_when_the_verifier_reports_a_bytecode_shadow() -> None:
    """The exact refusal a deployment hits if it ever starts without ``-B``.

    Named rather than ambient: the mutation gate proves the real verifier
    refuses a real bytecode shadow, and this proves what readiness does with
    that refusal. Neither depends on how the checkout it runs in happens to be
    arranged.
    """

    def _bytecode_shadowed() -> VerifiedNormalLiveSourceAuthorizationV1:
        raise NormalLiveSourceAuthorizationError("authorized_bytecode_cache_present")

    with _client(HOSTED_TRUSTED, source_verifier=_bytecode_shadowed) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert "source_not_authorized" in response.json()["reasons"]


def test_ready_follows_the_real_production_verifier_either_way() -> None:
    """Readiness tracks real authorization in whichever state this tree is in.

    An authorized checkout and an unauthorized one are both legitimate places
    to run the suite — the deployed service is the first, a development
    checkout carrying bytecode caches is the second. Asserting one of them
    would make this test a statement about the environment rather than about
    the behaviour, and it would fail on exactly the deployment it exists to
    protect.
    """
    try:
        verify_production_normal_live_source_authorization_v1()
    except Exception:
        authorized = False
    else:
        authorized = True

    with _client(
        HOSTED_TRUSTED,
        source_verifier=verify_production_normal_live_source_authorization_v1,
    ) as client:
        response = client.get("/ready")

    if authorized:
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    else:
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert "source_not_authorized" in body["reasons"]


def test_health_stays_200_while_the_service_is_not_ready() -> None:
    """Liveness and readiness answer different questions, and Render needs both."""
    with _client(HOSTED_TRUSTED, source_verifier=_unauthorized_build) as client:
        health = client.get("/health")
        ready = client.get("/ready")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 503


def test_readiness_says_nothing_private_about_the_failure() -> None:
    with _client(HOSTED_TRUSTED, source_verifier=_unauthorized_build) as client:
        response = client.get("/ready")
    blob = response.text
    assert set(response.json()) <= {"status", "mode", "reasons"}
    for forbidden in (
        "normallivesourceauthv1",
        "sha256",
        "authorization",
        "manifest",
        "C:\\",
        "/Users/",
        "Traceback",
        ORIGIN,
    ):
        assert forbidden not in blob, forbidden


def test_readiness_skips_authorization_when_no_live_mode_is_enabled() -> None:
    """A Demo-only deployment has nothing to authorize, and says so honestly."""

    def _explode() -> object:
        raise AssertionError("the verifier must not run for a Demo-only build")

    env = {
        "SOCRATES_PUBLIC_ORIGIN": ORIGIN,
        "SOCRATES_ENABLE_BYOK": "false",
        "SOCRATES_ENABLE_OPERATOR_NORMAL_LIVE": "false",
    }
    with _client(env, source_verifier=_explode) as client:
        response = client.get("/ready")
    assert response.status_code == 200


def test_readiness_report_keeps_the_worker_reason_alongside_authorization() -> None:
    config = load_hosted_config({**HOSTED_TRUSTED, "SOCRATES_WORKERS": "3"})
    status, reasons = readiness_report(config, source_authorized=False)
    assert status == "not_ready"
    assert reasons == ("source_not_authorized", "in_memory_limits_need_one_worker")


# ------------------------------------------------------------ same origin -----


def test_cross_origin_byok_is_refused_behind_the_trusted_proxy() -> None:
    with _client(HOSTED_TRUSTED) as client:
        response = client.post(
            "/api/council/byok/preflight",
            json={"question": "cross origin probe"},
            headers={
                "Origin": "https://attacker.example",
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "198.51.100.4",
            },
        )
    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-origin requests are not accepted."}


def test_exact_origin_comparison_is_not_weakened_by_a_prefix() -> None:
    with _client(HOSTED_TRUSTED) as client:
        response = _preflight(
            client,
            **{
                "Origin": ORIGIN + ".attacker.example",
                "X-Forwarded-Proto": "https",
            },
        )
    assert response.status_code == 403
