"""
Phase 9B — one-provider live smoke test: safety gates (NO real API calls).

These tests prove the smoke script never touches the network unless explicitly
enabled, never prints keys, and refuses unsafe config. The live SDK is never
imported here (every "live" path is monkeypatched).
"""

import importlib.util
import pathlib

import pytest

from backend.dialogues.models import (
    AgentMove, AgentRole, DialogPhase, ProviderResponse, ProviderStatus, TaskKind,
)


def _load_script():
    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "live_smoke_provider.py"
    spec = importlib.util.spec_from_file_location("live_smoke_provider_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_script()

FAKE_KEY = "sk-ant-FAKE-not-a-real-key-0000000000"


def _ok_response():
    move = AgentMove(task_id="t", agent_id="agent_0", role=AgentRole.SYNTHESIZER,
                     phase=DialogPhase.INITIAL_RESPONSE, content={"text": "water is wet"})
    return ProviderResponse(
        provider_id=mod.LIVE_PROVIDER_ID, agent_id="agent_0", status=ProviderStatus.OK,
        raw_text='{"content": {"text": "water is wet"}, "confidence": 0.7}', parsed_move=move,
    )


# ── (1) disabled by default → no live call ───────────────────────────────────

def test_disabled_by_default_makes_no_live_call(monkeypatch, capsys):
    monkeypatch.setattr(mod, "_run_live_smoke",
                        lambda *a, **k: pytest.fail("live call must not happen when disabled"))
    rc = mod.main(env={})
    assert rc == mod.EXIT_DISABLED
    out = capsys.readouterr().out
    assert "DISABLED" in out


@pytest.mark.parametrize("flag", ["", "0", "true", "yes", "2", "01"])
def test_flag_must_be_exactly_one(monkeypatch, flag):
    monkeypatch.setattr(mod, "_run_live_smoke",
                        lambda *a, **k: pytest.fail("live call must not happen"))
    rc = mod.main(env={mod.FLAG_ENV: flag, mod.KEY_ENV: FAKE_KEY})
    assert rc == mod.EXIT_DISABLED


# ── (2) enabled but no/placeholder key → no live call ────────────────────────

def test_enabled_but_missing_key_makes_no_live_call(monkeypatch, capsys):
    monkeypatch.setattr(mod, "_run_live_smoke",
                        lambda *a, **k: pytest.fail("live call must not happen without a key"))
    rc = mod.main(env={mod.FLAG_ENV: "1"})
    assert rc == mod.EXIT_NO_KEY
    assert "refusing to run" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("key", ["", "your_key_here", "changeme", "placeholder", "test"])
def test_enabled_placeholder_key_makes_no_live_call(monkeypatch, key):
    monkeypatch.setattr(mod, "_run_live_smoke",
                        lambda *a, **k: pytest.fail("live call must not happen for placeholder key"))
    rc = mod.main(env={mod.FLAG_ENV: "1", mod.KEY_ENV: key})
    assert rc == mod.EXIT_NO_KEY


# ── (3) refuses unsafe config (gate helpers) ─────────────────────────────────

def test_gate_helpers():
    assert mod.live_enabled({mod.FLAG_ENV: "1"}) is True
    assert mod.live_enabled({mod.FLAG_ENV: "0"}) is False
    assert mod.live_enabled({}) is False
    assert mod.resolve_key({mod.KEY_ENV: FAKE_KEY}) == FAKE_KEY
    assert mod.resolve_key({mod.KEY_ENV: "your_key_here"}) is None
    assert mod.resolve_key({}) is None


# ── (4) keys are never printed ───────────────────────────────────────────────

def test_summary_path_never_prints_key(monkeypatch, capsys):
    result = mod.SmokeResult(mod.LIVE_PROVIDER_ID, "Anthropic Live (claude-opus-4-8)",
                             "claude-opus-4-8", _ok_response())
    monkeypatch.setattr(mod, "_run_live_smoke", lambda *a, **k: result)
    rc = mod.main(env={mod.FLAG_ENV: "1", mod.KEY_ENV: FAKE_KEY})
    out = capsys.readouterr().out
    assert rc == mod.EXIT_OK
    assert FAKE_KEY not in out
    assert "provider_status" in out and "schema_valid" in out and "response_length" in out


def test_real_adapter_path_offline_is_key_safe(monkeypatch, capsys):
    # Patch the SEAM (_produce_raw_text) so the anthropic SDK is never imported and
    # no network is touched — the rest of the live adapter + validation runs for real.
    async def fake_produce(self, task, agent_state):
        return '{"content": {"text": "water is wet"}, "confidence": 0.66}'

    monkeypatch.setattr(mod.LiveAnthropicAdapter, "_produce_raw_text", fake_produce)
    rc = mod.main(env={mod.FLAG_ENV: "1", mod.KEY_ENV: FAKE_KEY})
    out = capsys.readouterr().out
    assert rc == mod.EXIT_OK
    assert FAKE_KEY not in out
    assert "schema_valid     : True" in out
    assert "provider_status  : ok" in out


def test_redact_masks_keys():
    assert "sk-ant" not in mod._redact("boom sk-ant-abcdef123456 boom")
    assert mod._redact("nothing here") == "nothing here"
    assert "topsecret" not in mod._redact("key=topsecret tail", key="topsecret")
    assert mod._redact(None) == ""


def test_live_error_is_redacted(monkeypatch, capsys):
    async def boom(self, task, agent_state):
        raise RuntimeError(f"failure leaking {FAKE_KEY} oops")

    monkeypatch.setattr(mod.LiveAnthropicAdapter, "_produce_raw_text", boom)
    # the adapter maps the exception to an honest ERROR status (no leak)...
    rc = mod.main(env={mod.FLAG_ENV: "1", mod.KEY_ENV: FAKE_KEY})
    out = capsys.readouterr().out
    assert FAKE_KEY not in out
    assert rc == mod.EXIT_OK            # adapter returned a ProviderResponse (status error)
    assert "provider_status  : error" in out


# ── adapter shape: live markers + no SDK import at module load ────────────────

def test_no_anthropic_import_at_module_load():
    # if the script imported anthropic at top level, the module would expose it
    assert not hasattr(mod, "anthropic")


def test_live_adapter_markers():
    assert mod.LiveAnthropicAdapter.is_live is True
    assert mod.LiveAnthropicAdapter.is_fake is False
    assert mod.LiveAnthropicAdapter.is_offline is False


def test_smoke_task_shape():
    task, state = mod.build_smoke_task()
    assert task.task_kind == TaskKind.INITIAL_RESPONSE
    assert task.role == AgentRole.SYNTHESIZER
    assert state.agent_id == "agent_0"


def test_unavailable_live_adapter_reports_missing_key():
    import asyncio
    adapter = mod.LiveAnthropicAdapter(mod.LIVE_PROVIDER_ID, "your_key_here")  # placeholder
    task, state = mod.build_smoke_task()
    resp = asyncio.run(adapter.generate_agent_move(task, state))
    assert resp.status == ProviderStatus.MISSING_KEY
    assert resp.parsed_move is None
