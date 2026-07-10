"""
Prompt patch generator tests (Goal 8).

Verifies the failure->proposed-patch flow and its safety properties:
  - repeated-only gating over the SAME Goal 6 detectors (shared instrument)
  - every proposal is status="proposed" with policy audit fields filled
  - deterministic ids in the reserved PATCH-9001+ range
  - the Goal 7 registry mechanically blocks proposals from default renders
    (never-auto-mutate), while a NAMED candidate run can exercise one
  - attach_proposals is non-mutating and refuses duplicate ids
  - composes with Goal 5 TraceCapturer

No provider calls, no network, no keys.
"""

import pytest

from backend.dialogues.openclaw_memory import TraceCapturer
from backend.dialogues.openclaw_prompts import (
    PATCH_PROPOSAL_ID_START,
    PromptSpec,
    attach_proposals,
    prompt_metadata,
    propose_patches_from_capturer,
    propose_prompt_patches,
    render_prompt,
)


# --------------------------------------------------------------------------- #
# Trace builders (shape matches trace_capture.build_session_trace)
# --------------------------------------------------------------------------- #

def _ok_trace(sid):
    return {
        "session_id": sid, "question": "q",
        "moves": [{"phase": p, "role": "r", "confidence": 0.7}
                  for p in ("opening", "initial_response", "elenchus",
                            "reflection", "reconstruction", "synthesis")],
        "assembly": {"sections": [
            {"section_name": "core_answer", "source_draft_id": "draft_1"}]},
        "ratification": {"ratified": True, "ratification_status": "ratified"},
    }


def _failed_ratification_trace(sid):
    t = _ok_trace(sid)
    t["ratification"] = {"ratified": False,
                         "ratification_status": "repair_required"}
    return t


def _unresolved_section_trace(sid, section="blind_spots"):
    t = _ok_trace(sid)
    t["assembly"]["sections"].append(
        {"section_name": section, "source_draft_id": ""})
    return t


BASE = """You are the {{role}}.

Task: {{question}}

{{memory_lessons}}"""


def _spec(patches=()):
    return PromptSpec(prompt_id="p", version_label="v0.1", description="d",
                      base_text=BASE, required_variables=("role", "question"),
                      patches=tuple(patches))


_VARS = {"role": "SYNTHESIZER", "question": "q"}


# --------------------------------------------------------------------------- #
# Proposal mechanics
# --------------------------------------------------------------------------- #

def test_single_occurrence_is_not_a_proposal():
    assert propose_prompt_patches(
        [_failed_ratification_trace("s1"), _ok_trace("s2")]) == []


def test_repeated_failure_becomes_proposed_patch():
    patches = propose_prompt_patches(
        [_failed_ratification_trace("s1"), _failed_ratification_trace("s2")])
    assert len(patches) == 1
    p = patches[0]
    assert p.status == "proposed"
    assert p.patch_id == f"PATCH-{PATCH_PROPOSAL_ID_START}"
    # PROMPT_PATCH_POLICY audit fields, mechanically filled.
    assert "s1" in p.reason and "s2" in p.reason
    assert p.expected_effect.strip() and p.risk.strip() and p.text.strip()


def test_ids_deterministic_and_sorted_by_pattern():
    traces = [
        _failed_ratification_trace("s1"), _failed_ratification_trace("s2"),
        _unresolved_section_trace("s3"), _unresolved_section_trace("s4"),
    ]
    a = propose_prompt_patches(traces)
    b = propose_prompt_patches(traces)
    assert [p.patch_id for p in a] == [p.patch_id for p in b]
    assert [p.patch_id for p in a] == [f"PATCH-{PATCH_PROPOSAL_ID_START}",
                                       f"PATCH-{PATCH_PROPOSAL_ID_START + 1}"]


def test_min_occurrences_validation():
    with pytest.raises(ValueError):
        propose_prompt_patches([], min_occurrences=0)
    assert propose_prompt_patches([]) == []


def test_section_pattern_produces_section_patch():
    patches = propose_prompt_patches(
        [_unresolved_section_trace("s1"), _unresolved_section_trace("s2")])
    assert len(patches) == 1
    assert "blind_spots" in patches[0].text


# --------------------------------------------------------------------------- #
# Registry integration: the never-auto-mutate proof
# --------------------------------------------------------------------------- #

def _proposals():
    return propose_prompt_patches(
        [_failed_ratification_trace("s1"), _failed_ratification_trace("s2")])


def test_proposals_never_render_by_default():
    spec = attach_proposals(_spec(), _proposals())
    out = render_prompt(spec, _VARS)
    assert "Ratification discipline" not in out       # proposed = excluded
    meta = prompt_metadata(spec)
    assert meta["applied_patches"] == []


def test_named_candidate_run_exercises_a_proposal():
    proposals = _proposals()
    spec = attach_proposals(_spec(), proposals)
    pid = proposals[0].patch_id
    out = render_prompt(spec, _VARS, candidate_patch_ids=[pid])
    assert "Ratification discipline" in out
    meta = prompt_metadata(spec, candidate_patch_ids=[pid])
    assert meta["applied_patches"] == [pid]
    assert meta["candidate_patches"] == [pid]


def test_attach_is_non_mutating_and_refuses_duplicates():
    spec = _spec()
    proposals = _proposals()
    spec2 = attach_proposals(spec, proposals)
    assert spec.patches == ()                          # original untouched
    assert len(spec2.patches) == 1
    with pytest.raises(ValueError, match="duplicate"):
        attach_proposals(spec2, proposals)             # same ids again


# --------------------------------------------------------------------------- #
# Composes with Goal 5
# --------------------------------------------------------------------------- #

def test_propose_from_capturer():
    capturer = TraceCapturer()
    capturer.traces.extend([_failed_ratification_trace("s1"),
                            _failed_ratification_trace("s2")])
    patches = propose_patches_from_capturer(capturer)
    assert len(patches) == 1 and patches[0].status == "proposed"
    assert propose_patches_from_capturer(TraceCapturer()) == []
