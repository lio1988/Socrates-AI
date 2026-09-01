"""Static fail-closed contract checks for the additive Normal Live UI."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
BRIDGE = (ROOT / "web" / "ced-bridge.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")


def test_normal_live_controls_exist_once_and_confirmation_starts_hidden() -> None:
    required_ids = (
        "normal-live-mode-button",
        "live-confirmation-panel",
        "live-confirmation-title",
        "live-source-status",
        "live-seat-count",
        "live-maximum-calls",
        "live-maximum-cost",
        "live-confirmation-description",
        "live-cancel-button",
        "live-confirm-button",
        "seat-topology-title",
    )
    for identifier in required_ids:
        assert len(re.findall(fr'id="{re.escape(identifier)}"', HTML)) == 1
    assert len(re.findall(r'class="mode-option(?: is-selected)?"', HTML)) == 3
    panel = re.search(
        r'<section class="live-confirmation"[^>]*id="live-confirmation-panel"[^>]*>',
        HTML,
    )
    assert panel and " hidden" in panel.group(0)
    for identifier in ("live-seat-count", "live-maximum-calls", "live-maximum-cost"):
        assert re.search(fr'id="{identifier}">—</', HTML)


def test_documented_local_launcher_disables_bytecode_cache_writes() -> None:
    assert "python -B -m uvicorn backend.local_ced_app:app" in HTML
    assert "python -m uvicorn backend.local_ced_app:app" not in HTML


def test_browser_has_no_source_or_execution_authority_surface() -> None:
    lower_html = HTML.lower()
    assert 'type="password"' not in lower_html
    for forbidden in (
        "openrouter_api_key",
        "byok",
        "authorization_id",
        "source_set_digest",
        "provider_id",
        "model_id",
        "artifact_root",
    ):
        assert forbidden not in lower_html
    combined_js = (APP + BRIDGE).lower()
    assert "localstorage" not in combined_js
    assert "sessionstorage" not in combined_js
    assert 'json.stringify({ question })' in combined_js
    assert 'json.stringify({ confirmed: true })' in combined_js
    assert 'json.stringify({})' in combined_js
    assert "maximum_calls: 135" not in BRIDGE
    assert "provider_count: 3" not in BRIDGE


def test_live_projection_is_strict_and_seat_count_is_server_driven() -> None:
    assert "EXACT_PREFLIGHT_KEYS" in BRIDGE
    assert "hasExactKeys(payload, EXACT_PREFLIGHT_KEYS)" in BRIDGE
    assert "payload.maximum_calls !== payload.base_calls + payload.retry_calls" in BRIDGE
    assert "seen.has(seat.seat_id)" in BRIDGE
    assert "renderPublicSeatTopology(preflight.seats)" in BRIDGE
    assert "defaultSeatTemplates[index].cloneNode(true)" in APP
    assert 'style.setProperty("--seat-count"' in APP
    assert "repeat(var(--seat-count, 4), minmax(0, 1fr))" in CSS


def test_demo_and_local_restoration_and_normal_reset_are_explicit() -> None:
    assert BRIDGE.count("restoreDefaultSeatTopology()") >= 2
    assert "clearSeatTopology();" in BRIDGE
    assert "function resetNormalView()" in BRIDGE
    assert "cancelNormalPreflight();" in BRIDGE
    assert "closeLocalTransport();" in BRIDGE
    assert "localState.generation += 1;" in BRIDGE
