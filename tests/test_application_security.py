import asyncio
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient

from backend.app import create_app
from socrates_ai import DialogConfig, DialogManager
from backend.orchestrator.session import DialogSessionManager
from fastapi import HTTPException
from types import SimpleNamespace


@pytest.fixture
def local_client(monkeypatch):
    monkeypatch.delenv("SOCRATES_ACCESS_PASSWORD", raising=False)
    monkeypatch.delenv("SOCRATES_ALLOWED_HOSTS", raising=False)
    return TestClient(create_app(), base_url="http://localhost", client=("127.0.0.1", 50000))


def test_local_access_and_private_files(local_client):
    assert local_client.get("/health").status_code == 200
    for path in ("/.env", "/.git/config", "/backend/app.py"):
        assert local_client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/", "/health", "/dialog/list/active", "/docs", "/openapi.json"])
def test_remote_access_refused_without_password(monkeypatch, path):
    monkeypatch.delenv("SOCRATES_ACCESS_PASSWORD", raising=False)
    monkeypatch.delenv("SOCRATES_ALLOWED_HOSTS", raising=False)
    client = TestClient(create_app(), base_url="http://localhost", client=("198.51.100.4", 50000))
    assert client.get(path, headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403


def test_foreign_host_and_origin_refused(local_client):
    assert local_client.get("/health", headers={"Host": "attacker.example"}).status_code == 400
    for origin in ("https://attacker.example", "null", "http://localhost:9999"):
        response = local_client.post("/dialog/start", headers={"Origin": origin}, json={"topic": "test"})
        assert response.status_code == 403
        assert "access-control-allow-origin" not in response.headers
    assert local_client.get("/health", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_same_origin_allowed_and_security_headers(local_client):
    response = local_client.get("/health", headers={"Origin": "http://localhost"})
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"


def test_password_protects_all_routes(monkeypatch):
    password = "test-only-access-password-with-32-characters"
    monkeypatch.setenv("SOCRATES_ACCESS_PASSWORD", password)
    monkeypatch.setenv("SOCRATES_ALLOWED_HOSTS", "council.example")
    client = TestClient(create_app(), base_url="https://council.example", client=("198.51.100.4", 50000))
    for path in ("/", "/health", "/docs", "/dialog/list/active"):
        assert client.get(path).status_code == 401
        assert client.get(path, auth=("socrates", "wrong")).status_code == 401
        assert client.get(path, auth=("socrates", password)).status_code == 200
    assert client.post("/dialog/start", json={"topic": "test"}).status_code == 401
    assert client.get("http://council.example/health", auth=("socrates", password)).status_code == 403


def test_oversized_body_is_refused(local_client):
    assert local_client.post("/dialog/start", content=b"x" * 65537).status_code == 413


def test_chunked_body_limit(local_client):
    response = local_client.post("/dialog/start", content=iter([b"x" * 32768, b"x" * 32769]))
    assert response.status_code == 413


@pytest.mark.parametrize("authorization", ["Basic !!!!", "Bearer test", "Basic", "Basic /w=="])
def test_malformed_authentication_fails_closed(monkeypatch, authorization):
    monkeypatch.setenv("SOCRATES_ACCESS_PASSWORD", "synthetic-test-password-32-characters")
    monkeypatch.delenv("SOCRATES_ALLOWED_HOSTS", raising=False)
    client = TestClient(create_app(), base_url="http://localhost", client=("127.0.0.1", 50000))
    assert client.get("/health", headers={"Authorization": authorization}).status_code == 401


def test_unsafe_configuration_refused(monkeypatch):
    monkeypatch.delenv("SOCRATES_ACCESS_PASSWORD", raising=False)
    monkeypatch.setenv("SOCRATES_ALLOWED_HOSTS", "public.example")
    with pytest.raises(ValueError):
        create_app()
    monkeypatch.setenv("SOCRATES_ALLOWED_HOSTS", "*")
    with pytest.raises(ValueError):
        create_app()
    monkeypatch.setenv("SOCRATES_ALLOWED_HOSTS", "localhost")
    monkeypatch.setenv("SOCRATES_ACCESS_PASSWORD", "changeme")
    with pytest.raises(ValueError):
        create_app()


def test_dialog_capacity_and_deletion_cannot_bypass_active_limit():
    manager = DialogSessionManager()
    manager._sessions = {"first": SimpleNamespace(status="running"), "second": SimpleNamespace(status="initialized")}
    with pytest.raises(HTTPException) as error:
        manager.create("third", DialogConfig(topic="test"), {})
    assert error.value.status_code == 429
    with pytest.raises(HTTPException) as error:
        manager.delete("first")
    assert error.value.status_code == 409
    manager._sessions["first"].status = "completed"
    assert manager.delete("first")
    manager._sessions = {str(index): SimpleNamespace(status="completed") for index in range(100)}
    with pytest.raises(HTTPException) as error:
        manager.create("extra", DialogConfig(topic="test"), {})
    assert error.value.status_code == 429


@pytest.mark.parametrize("method,provider", [("_call_gemini", "gemini"), ("_call_grok", "grok"), ("_call_openai", "chatgpt")])
def test_provider_failures_do_not_expose_keys(monkeypatch, method, provider):
    secret = "synthetic-sensitive-value"
    request = Mock(side_effect=requests.HTTPError("upstream error?key=" + secret))
    monkeypatch.setattr("socrates_ai.requests.post", request)
    manager = DialogManager(DialogConfig(topic="security test"), {"gemini": secret, "grok": secret, "chatgpt": secret})
    with pytest.raises(Exception) as error:
        asyncio.run(getattr(manager, method)("test"))
    assert secret not in str(error.value)
    assert request.call_args.kwargs["timeout"] == (10, 60)
    assert request.call_args.kwargs["allow_redirects"] is False
    if provider == "gemini":
        assert "params" not in request.call_args.kwargs
        assert request.call_args.kwargs["headers"]["x-goog-api-key"] == secret
