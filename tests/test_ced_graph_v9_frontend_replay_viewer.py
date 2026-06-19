"""CED Graph v9 — Frontend Replay Viewer tests."""

from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1] / "frontend.html"


def _html() -> str:
    return FRONTEND.read_text(encoding="utf-8")


def test_frontend_contains_v9_replay_panel():
    html = _html()
    assert "CED Graph v9 — Frontend Replay Viewer" in html
    assert 'id="replay-panel"' in html
    assert 'id="replayViewer"' in html


def test_frontend_contains_replay_action_buttons():
    html = _html()
    assert 'id="viewReplayBtn"' in html
    assert 'id="downloadAuditBtn"' in html
    assert 'id="downloadCanonicalBtn"' in html
    assert "View Replay" in html
    assert "Download Audit JSON" in html
    assert "Download Canonical JSON" in html


def test_frontend_uses_v8_replay_api_endpoints():
    html = _html()
    assert "/api/epistemic/replay/export/" in html
    assert "/api/epistemic/replay/audit/" in html
    assert "/canonical" in html


def test_frontend_defines_replay_viewer_functions():
    html = _html()
    for fn in (
        "function viewReplay()",
        "function downloadAuditJson()",
        "function downloadCanonicalReplay()",
        "function renderReplaySummary(replay)",
        "function updateReplayControls(status)",
    ):
        assert fn in html


def test_frontend_renders_core_replay_sections():
    html = _html()
    assert "Replay metadata" in html
    assert "Current Best Explanation" in html
    assert "Meta-Socrates process evaluation" in html
    assert "Audit checks" in html
    assert "Claim timeline" in html
    assert "Raw replay preview" in html


def test_frontend_enables_replay_after_terminal_session_state():
    html = _html()
    assert "['completed', 'stopped', 'error'].includes(status)" in html
    assert "Replay export is ready." in html
    assert "Replay export will unlock when this session finishes." in html


def test_frontend_escapes_replay_html_content():
    html = _html()
    assert "function escapeHtml(value)" in html
    assert ".replaceAll('&', '&amp;')" in html
    assert ".replaceAll('<', '&lt;')" in html
    assert "textContent = t.content" in html
