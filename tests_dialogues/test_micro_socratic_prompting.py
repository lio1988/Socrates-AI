"""Micro-Socratic Kernel v1 — prompt construction (isolation + purity)."""

import json

from backend.dialogues.openclaw_socratic_kernel import MicroSocraticRequest
from backend.dialogues.openclaw_socratic_kernel.prompting import (
    build_system_prompt,
    build_user_prompt,
)

_DRAFT_MARKER = "PRIVATE_DRAFT_SENTINEL_77"


def _request(mode="standard", **overrides):
    base = dict(
        request_id="kernel-prompt",
        agent_id="local_apprentice_001",
        mode=mode,
        provider="mock",
        model="mock-auditor",
        task="Evaluate whether the claim holds.",
        draft=f"My draft. {_DRAFT_MARKER}",
        purpose="pre-final self-check",
        max_tokens=1024,
        timeout_seconds=60.0,
        created_at="2026-07-11T00:00:00Z",
        expires_at="2026-07-11T01:00:00Z",
    )
    base.update(overrides)
    return MicroSocraticRequest(**base)


def test_system_prompt_states_all_boundaries():
    directive = build_system_prompt(_request()).lower()
    assert "bounded micro-socratic auditor" in directive
    assert "do not reveal chain-of-thought" in directive
    assert "do not use tools" in directive
    assert "do not open another consultation" in directive
    assert "certify" in directive           # no self-certification
    assert "untrusted" in directive
    assert "openclaw_micro_socratic_mode:standard" in directive


def test_user_prompt_carries_only_task_draft_purpose():
    prompt = build_user_prompt(_request())
    parsed = json.loads(prompt)
    assert set(parsed) == {"purpose", "task", "draft_under_review"}
    # The draft IS shown to the auditor (it reviews the agent's own draft).
    assert _DRAFT_MARKER in parsed["draft_under_review"]


def test_prompt_has_no_memory_identity_soul_or_history():
    blob = (build_system_prompt(_request()) + build_user_prompt(_request())).lower()
    for forbidden in ("memory profile", "identity profile", "soul profile",
                      "previous check", "chat history", "leaderboard",
                      "scratchpad", "sk-ant"):
        assert forbidden not in blob


def test_prompt_is_pure_function_of_request():
    r = _request()
    assert build_system_prompt(r) == build_system_prompt(r)
    assert build_user_prompt(r) == build_user_prompt(r)


def test_mode_marker_matches_mode():
    for mode in ("light", "standard", "high_risk"):
        assert f"OPENCLAW_MICRO_SOCRATIC_MODE:{mode}" in \
            build_system_prompt(_request(mode=mode))
