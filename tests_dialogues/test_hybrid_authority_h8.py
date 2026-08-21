"""H8 — the authority map is enforced, not merely declared.

An adapter is reconnected for a good reason and its output quietly starts
deciding something it was never meant to decide. These tests make that drift a
test failure instead of a later forensic exercise.

All offline: import-graph and source inspection only.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from backend.dialogues.hybrid_authority import (
    AUTHORITY_MAP,
    GOVERNING_CORE_MODULE,
    AuthorityClass,
    authority_of,
    by_authority,
)

_BACKEND = pathlib.Path(__file__).resolve().parents[1] / "backend"


def _module_path(dotted: str) -> pathlib.Path:
    rel = dotted.replace("backend.", "").replace(".", "/")
    direct = _BACKEND / f"{rel}.py"
    return direct if direct.exists() else _BACKEND / rel


def _imported_modules(path: pathlib.Path) -> set[str]:
    """Every module name imported anywhere under `path`."""
    files = [path] if path.is_file() else list(path.rglob("*.py"))
    found: set[str] = set()
    for file in files:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except SyntaxError:                      # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
                found.update(f"{node.module}.{a.name}" for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level:
                found.update(a.name for a in node.names)
    return found


def test_every_subsystem_has_exactly_one_authority_class():
    names = [s.name for s in AUTHORITY_MAP]
    assert len(names) == len(set(names)), "a subsystem is classified twice"
    for subsystem in AUTHORITY_MAP:
        assert isinstance(subsystem.authority, AuthorityClass)
        assert subsystem.role.strip(), f"{subsystem.name} has no stated role"


def test_only_the_hybrid_core_may_decide_epistemic_support():
    """Exactly one authoritative owner of support, not several."""
    governing = by_authority(AuthorityClass.AUTHORITATIVE)
    modules = {s.module for s in governing}
    assert GOVERNING_CORE_MODULE in modules
    # The other authoritative entries govern execution and storage, not support.
    support_owners = [s for s in governing if "support" in s.role or "release" in s.role]
    assert [s.module for s in support_owners] == [GOVERNING_CORE_MODULE]


def test_the_governing_core_does_not_import_advisory_or_quality_subsystems():
    """Support must not be computable from advice or from a score."""
    imported = _imported_modules(_module_path(GOVERNING_CORE_MODULE))
    forbidden_modules = {
        s.module for s in AUTHORITY_MAP
        if s.authority in (AuthorityClass.ADVISORY, AuthorityClass.QUALITY,
                           AuthorityClass.LEARNING, AuthorityClass.SEARCH,
                           AuthorityClass.LEGACY)
    }
    # ced is listed under several classes; the core must not import it at all.
    leaked = sorted(m for m in forbidden_modules
                    if any(i == m or i.startswith(m + ".") for i in imported))
    assert leaked == [], f"the governing core imports non-governing subsystems: {leaked}"


def test_no_advisory_or_legacy_subsystem_imports_the_governing_core():
    """Advisory components may be read from; they may not write authority."""
    # A module is exempt when ANY of its entries is authoritative: ced.py owns
    # execution and also hosts quality and advisory roles, and after H7 it is
    # the caller that routes the release through the core.
    governing_modules = {s.module for s in AUTHORITY_MAP
                         if s.authority is AuthorityClass.AUTHORITATIVE}
    offenders = []
    for subsystem in AUTHORITY_MAP:
        if subsystem.module in governing_modules:
            continue
        path = _module_path(subsystem.module)
        if not path.exists():
            continue
        if any(i == GOVERNING_CORE_MODULE or i.startswith(GOVERNING_CORE_MODULE + ".")
               or i.endswith("hybrid_epistemic")
               for i in _imported_modules(path)):
            offenders.append(subsystem.name)
    assert offenders == [], f"non-governing subsystems reach the core: {offenders}"


def test_the_legacy_quality_threshold_is_classified_legacy():
    assert authority_of("legacy epistemic hint") is AuthorityClass.LEGACY


def test_ratification_is_advisory_not_authoritative_over_support():
    """Acceptance is a governance act. It is not corroboration."""
    assert authority_of("council ratification") is AuthorityClass.ADVISORY


def test_consultation_is_advisory_because_a_provider_answer_is_a_model_assertion():
    assert authority_of("external consultation") is AuthorityClass.ADVISORY


def test_markers_leaderboard_and_tree_are_not_authoritative():
    assert authority_of("epistemic markers") is AuthorityClass.ADVISORY
    assert authority_of("epistemic leaderboard") is AuthorityClass.QUALITY
    assert authority_of("deliberation tree") is AuthorityClass.SEARCH


def test_live_view_and_trace_collection_are_observers():
    assert authority_of("council live view") is AuthorityClass.OBSERVER
    assert authority_of("learning trace collector") is AuthorityClass.OBSERVER


def test_learning_never_touches_present_truth():
    for subsystem in by_authority(AuthorityClass.LEARNING):
        assert "future" in subsystem.note.lower()


def test_an_unclassified_subsystem_raises_rather_than_defaulting():
    with pytest.raises(KeyError):
        authority_of("something nobody classified")
