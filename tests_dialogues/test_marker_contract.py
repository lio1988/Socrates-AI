"""The canonical epistemic-marker contract must not contradict itself.

Five deliberative task kinds once received both "include an `epistemic_marker`
field" and "EXACTLY these fields / do not add other top-level fields". Models
resolved that by dropping the marker, and live coverage sat at 7%-21%.

These tests pin the contract so the two halves cannot drift apart again: one
predicate decides who carries a marker, and every task kind's directive and
output contract must agree with it.

All offline: prompt construction only, no provider, no network.
"""

from __future__ import annotations

import pytest

from backend.dialogues.models import AgentRole, DialogPhase, TaskKind
from backend.dialogues.reasoning_prompts import (
    DEFAULT_RESPONSE_CONTRACT,
    DELIBERATIVE_RESPONSE_CONTRACT,
    EPISTEMIC_MARKER_DIRECTIVE,
    build_reasoning_system_prompt,
    is_deliberative_kind,
    marker_is_contracted,
)

# The directive's opening line, used to detect its presence without matching on
# prose that merely mentions markers.
_DIRECTIVE_HEAD = EPISTEMIC_MARKER_DIRECTIVE.splitlines()[0]

# Every phrasing anywhere in the prompt set that claims an exclusive field list.
_EXCLUSIVITY = (
    "EXACTLY these", "EXACTLY this",
    "do not add other top-level fields", "or add others",
)
_CARVE_OUT = "ONE permitted extra top-level field"


def _prompt(kind, contract=None):
    kwargs = {"model": "openai/gpt-4.1-mini"}
    if contract is not None:
        kwargs["response_contract"] = contract
    return build_reasoning_system_prompt(
        AgentRole.SYNTHESIZER, DialogPhase.SYNTHESIS, kind, **kwargs)


@pytest.mark.parametrize("kind", list(TaskKind), ids=lambda k: k.value)
def test_directive_and_contract_agree_with_the_single_predicate(kind):
    """Neither half of the contract may disagree with `marker_is_contracted`."""
    prompt = _prompt(kind)
    tail = prompt.rstrip().split("**Output**")[-1]
    expected = marker_is_contracted(kind)

    assert (_DIRECTIVE_HEAD in prompt) is expected, (
        f"{kind.value}: directive presence disagrees with the canonical predicate")
    assert ("epistemic_marker" in tail) is expected, (
        f"{kind.value}: output contract disagrees with the canonical predicate")


@pytest.mark.parametrize("kind", list(TaskKind), ids=lambda k: k.value)
def test_no_task_kind_both_requires_and_forbids_the_marker(kind):
    """The contradiction that suppressed markers in the first place."""
    prompt = _prompt(kind)
    if _DIRECTIVE_HEAD not in prompt:
        return                                   # nothing to contradict
    if not any(tok in prompt for tok in _EXCLUSIVITY):
        return                                   # no exclusive field list at all
    assert _CARVE_OUT in prompt, (
        f"{kind.value}: requires an epistemic_marker while an exclusive field "
        f"list forbids extra fields, and nothing carves the marker out")


def test_evaluative_kinds_never_carry_a_marker():
    """Scores and verdicts judge someone else's claim; a marker is meaningless."""
    for kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE,
                 TaskKind.COUNCIL_RATIFICATION, TaskKind.RATIFICATION_INITIAL,
                 TaskKind.RATIFICATION_REVISION, TaskKind.RATIFICATION_FINAL):
        assert marker_is_contracted(kind) is False
        prompt = _prompt(kind)
        assert _DIRECTIVE_HEAD not in prompt
        assert "epistemic_marker" not in prompt.rstrip().split("**Output**")[-1]


def test_marker_rule_is_derived_from_the_deliberative_classification():
    """One authority, not two independent rules that can drift."""
    for kind in TaskKind:
        assert marker_is_contracted(kind) == is_deliberative_kind(kind)
    assert marker_is_contracted(None) is False


def test_an_explicit_caller_contract_overrides_the_deliberative_default():
    custom = "Return one JSON object shaped however this caller wants."
    prompt = _prompt(TaskKind.SYNTHESIS_DRAFT, contract=custom)
    assert prompt.rstrip().endswith(custom)
    assert DELIBERATIVE_RESPONSE_CONTRACT not in prompt


def test_deliberative_contract_is_used_only_when_the_default_was_accepted():
    deliberative = _prompt(TaskKind.SYNTHESIS_DRAFT)
    evaluative = _prompt(TaskKind.MOVE_SCORE)
    assert DELIBERATIVE_RESPONSE_CONTRACT in deliberative
    assert DEFAULT_RESPONSE_CONTRACT in evaluative
    assert DELIBERATIVE_RESPONSE_CONTRACT not in evaluative


@pytest.mark.parametrize("kind", list(TaskKind), ids=lambda k: k.value)
def test_output_contract_stays_last_and_ends_as_alignment_requires(kind):
    assert _prompt(kind).rstrip().endswith("and nothing else.")


def test_marker_values_offered_are_exactly_the_canonical_vocabulary():
    """The prompt must not invent a marker the parser cannot map."""
    from backend.dialogues.models import EpistemicMarker
    for marker in EpistemicMarker:
        assert f'"{marker.value}"' in EPISTEMIC_MARKER_DIRECTIVE
