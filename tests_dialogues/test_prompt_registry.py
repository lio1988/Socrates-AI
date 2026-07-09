"""
Prompt Registry tests (Goal 7).

Verifies:
  - strict deterministic rendering (missing/unknown variables refuse)
  - JSON braces in prompt bodies survive (double-brace placeholders)
  - the lesson slot fills and collapses cleanly
  - provider-scoped patches; default render = stable/verified ONLY
  - explicit named candidates for A/B; deprecated never renders
  - content-addressed fingerprints (tamper-evident lineage)
  - trace-ready metadata with no secrets
  - leak guard refuses key-shaped secrets in rendered text
  - runtime isolation: CED core and reasoning_prompts never import this

No provider calls, no network, no keys.
"""

import json

import pytest

from backend.dialogues.openclaw_prompts import (
    ALL_PROVIDERS,
    PromptPatch,
    PromptRegistry,
    PromptSpec,
    applied_patches,
    prompt_fingerprint,
    prompt_metadata,
    render_prompt,
)

BASE = """You are the {{role}} for phase {{phase}}.

Task: {{question}}

{{memory_lessons}}

Respond with EXACTLY one JSON object of the form
{"content": {"core_answer": "..."}, "confidence": 0.8} and nothing else."""


def _spec(patches=()):
    return PromptSpec(
        prompt_id="openclaw_test_prompt",
        version_label="v0.1",
        description="test prompt",
        base_text=BASE,
        required_variables=("role", "phase", "question"),
        patches=tuple(patches),
    )


def _patch(pid, status, providers=(ALL_PROVIDERS,), text=None):
    return PromptPatch(
        patch_id=pid, name=f"patch {pid}", status=status,
        text=text or f"**Extra instruction ({pid})**: be precise.",
        reason="test", expected_effect="tighter output", risk="low",
        target_providers=tuple(providers),
    )


_VARS = {"role": "SYNTHESIZER", "phase": "synthesis",
         "question": "What is knowledge?"}


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def test_render_fills_variables_deterministically():
    a = render_prompt(_spec(), _VARS)
    b = render_prompt(_spec(), _VARS)
    assert a == b
    assert "You are the SYNTHESIZER for phase synthesis." in a
    assert "What is knowledge?" in a


def test_missing_variable_refused():
    with pytest.raises(ValueError, match="missing"):
        render_prompt(_spec(), {"role": "X", "phase": "synthesis"})


def test_unknown_variable_refused():
    with pytest.raises(ValueError, match="unknown"):
        render_prompt(_spec(), {**_VARS, "surprise": "nope"})


def test_json_braces_survive():
    out = render_prompt(_spec(), _VARS)
    assert '{"content": {"core_answer": "..."}, "confidence": 0.8}' in out


def test_lesson_slot_fills_and_collapses():
    filled = render_prompt(_spec(), {**_VARS, "memory_lessons":
                                     "Relevant memory lessons:\n- LESSON-0001: x"})
    assert "LESSON-0001" in filled
    empty = render_prompt(_spec(), _VARS)          # slot not supplied
    assert "memory_lessons" not in empty
    assert "\n\n\n" not in empty                   # hole collapsed


# --------------------------------------------------------------------------- #
# Patches: lifecycle + provider scoping (never-auto-mutate)
# --------------------------------------------------------------------------- #

def test_default_render_applies_only_stable_and_verified():
    spec = _spec([_patch("PATCH-0001", "stable"),
                  _patch("PATCH-0002", "verified"),
                  _patch("PATCH-0003", "proposed"),
                  _patch("PATCH-0004", "tested")])
    out = render_prompt(spec, _VARS)
    assert "PATCH-0001" in out and "PATCH-0002" in out
    assert "PATCH-0003" not in out and "PATCH-0004" not in out


def test_provider_scoped_patch():
    spec = _spec([_patch("PATCH-0001", "stable", providers=("anthropic_seat0",))])
    assert "PATCH-0001" in render_prompt(spec, _VARS,
                                         provider_id="anthropic_seat0")
    assert "PATCH-0001" not in render_prompt(spec, _VARS,
                                             provider_id="other_seat")
    assert "PATCH-0001" not in render_prompt(spec, _VARS)   # no provider


def test_candidate_patches_are_explicit_and_named():
    spec = _spec([_patch("PATCH-0003", "proposed")])
    out = render_prompt(spec, _VARS, candidate_patch_ids=["PATCH-0003"])
    assert "PATCH-0003" in out
    with pytest.raises(ValueError, match="unknown candidate"):
        render_prompt(spec, _VARS, candidate_patch_ids=["PATCH-9999"])


def test_deprecated_never_renders_even_as_candidate():
    spec = _spec([_patch("PATCH-0005", "deprecated")])
    assert "PATCH-0005" not in render_prompt(
        spec, _VARS, candidate_patch_ids=["PATCH-0005"])


def test_invalid_patch_status_refused():
    with pytest.raises(ValueError, match="invalid status"):
        _patch("PATCH-0009", "experimental")


def test_duplicate_patch_ids_refused():
    with pytest.raises(ValueError, match="duplicate"):
        _spec([_patch("PATCH-0001", "stable"), _patch("PATCH-0001", "stable")])


# --------------------------------------------------------------------------- #
# Version identity: label + content-addressed fingerprint
# --------------------------------------------------------------------------- #

def test_fingerprint_stable_and_tamper_evident():
    spec = _spec([_patch("PATCH-0001", "stable")])
    fp1 = prompt_fingerprint(spec, "seat0")
    assert fp1 == prompt_fingerprint(spec, "seat0")          # deterministic
    changed = PromptSpec(
        prompt_id=spec.prompt_id, version_label=spec.version_label,
        description=spec.description, base_text=spec.base_text + "\nEXTRA",
        required_variables=spec.required_variables, patches=spec.patches)
    assert prompt_fingerprint(changed, "seat0") != fp1       # text change
    scoped = _spec([_patch("PATCH-0001", "stable", providers=("seat0",))])
    assert (prompt_fingerprint(scoped, "seat0")
            != prompt_fingerprint(scoped, "other"))          # patch-set change


def test_metadata_is_trace_ready():
    spec = _spec([_patch("PATCH-0001", "stable"),
                  _patch("PATCH-0003", "proposed")])
    meta = prompt_metadata(spec, "seat0")
    blob = json.dumps(meta)                                  # JSON-serializable
    assert meta["prompt_id"] == "openclaw_test_prompt"
    assert meta["prompt_version"] == "v0.1"
    assert meta["applied_patches"] == ["PATCH-0001"]
    assert meta["candidate_patches"] == []
    assert len(meta["prompt_fingerprint"]) == 12
    for forbidden in ("sk-ant-", "api_key", "score"):
        assert forbidden not in blob


def test_leak_guard_refuses_key_shaped_secrets():
    bad = _spec([_patch("PATCH-0001", "stable",
                        text="Use header Bearer abc123")])
    with pytest.raises(ValueError, match="key-shaped"):
        render_prompt(bad, _VARS)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

def test_registry_register_get_and_no_overwrite():
    reg = PromptRegistry()
    reg.register(_spec())
    assert reg.get("openclaw_test_prompt").version_label == "v0.1"
    with pytest.raises(ValueError, match="duplicate"):
        reg.register(_spec())
    with pytest.raises(KeyError):
        reg.get("nope")
    assert [s.prompt_id for s in reg.all_prompts()] == ["openclaw_test_prompt"]
    assert reg.metadata_for("openclaw_test_prompt")["prompt_version"] == "v0.1"


# --------------------------------------------------------------------------- #
# Runtime isolation: lineage first, wiring later (explicitly)
# --------------------------------------------------------------------------- #

def test_ced_core_never_imports_prompt_registry():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "backend" / "dialogues"
    for name in ("ced.py", "live_providers.py", "provider_registry.py",
                 "reasoning_prompts.py", "models.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "openclaw_prompts" not in source, (
            f"{name} must not import the prompt registry — runtime "
            "activation is a later, explicit goal")
