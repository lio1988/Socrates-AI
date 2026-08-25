"""Static and dynamic locks for the acquisition-only authority boundary."""

from __future__ import annotations

import ast
import asyncio
import http.client
import os
import socket
import urllib.request
from pathlib import Path

import pytest

from backend.dialogues import provider_registry
from backend.dialogues.ced_canonical_successor import (
    CanonicalSuccessorEnvironmentV0,
)
from backend.dialogues.socrates_zero import acquisition_evaluation
from backend.dialogues.socrates_zero.acquisition_cases import (
    FROZEN_ACQUISITION_POSITIVE_CASES_V0,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_SOURCES = (
    REPOSITORY_ROOT
    / "backend"
    / "dialogues"
    / "socrates_zero"
    / "acquisition_contracts.py",
    REPOSITORY_ROOT
    / "backend"
    / "dialogues"
    / "socrates_zero"
    / "acquisition_cases.py",
    REPOSITORY_ROOT
    / "backend"
    / "dialogues"
    / "socrates_zero"
    / "acquisition.py",
    REPOSITORY_ROOT
    / "backend"
    / "dialogues"
    / "socrates_zero"
    / "acquisition_evaluation.py",
)

FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "anthropic",
        "aiohttp",
        "google",
        "http",
        "httpx",
        "keyring",
        "openai",
        "os",
        "random",
        "requests",
        "secrets",
        "socket",
        "ssl",
        "subprocess",
        "urllib",
        "uuid",
    }
)
FORBIDDEN_LOCAL_IMPORT_FRAGMENTS = (
    "ced_canonical_successor",
    "provider_registry",
    "offline_provider_adapter",
    "strategy",
    "puct",
    "value",
)
FORBIDDEN_CALL_NAMES = frozenset(
    {
        "apply_observation",
        "connect",
        "create_connection",
        "getaddrinfo",
        "getenv",
        "send",
        "urlopen",
    }
)


def _imports(tree: ast.AST) -> tuple[str, ...]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return tuple(names)


def _called_names(tree: ast.AST) -> tuple[str, ...]:
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name):
            names.append(function.id)
        elif isinstance(function, ast.Attribute):
            names.append(function.attr)
    return tuple(names)


def _enclosing_function_names(tree: ast.AST) -> tuple[tuple[str, str], ...]:
    file_calls: list[tuple[str, str]] = []
    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"open", "read_bytes", "read_text"}
            ):
                file_calls.append((function.name, node.func.attr))
    return tuple(file_calls)


@pytest.mark.parametrize("source_path", ACQUISITION_SOURCES, ids=lambda path: path.name)
def test_acquisition_modules_have_no_external_or_governing_imports(
    source_path: Path,
) -> None:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported = _imports(tree)
    assert not {
        name.split(".", 1)[0] for name in imported
    }.intersection(FORBIDDEN_IMPORT_ROOTS)
    assert not any(
        fragment in name
        for name in imported
        for fragment in FORBIDDEN_LOCAL_IMPORT_FRAGMENTS
    )


@pytest.mark.parametrize("source_path", ACQUISITION_SOURCES, ids=lambda path: path.name)
def test_acquisition_modules_do_not_call_external_or_canonical_seams(
    source_path: Path,
) -> None:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    assert not set(_called_names(tree)).intersection(FORBIDDEN_CALL_NAMES)


def test_acquisition_file_reads_are_limited_to_frozen_hash_and_write_once_paths() -> None:
    observed: set[tuple[str, str]] = set()
    for source_path in ACQUISITION_SOURCES:
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        )
        observed.update(_enclosing_function_names(tree))
    assert observed == {
        ("verify_frozen_historical_hashes_v0", "read_bytes"),
        ("write_once_canonical_bytes_v0", "open"),
        ("write_once_canonical_bytes_v0", "read_bytes"),
    }


def test_acquisition_is_not_imported_by_production_surfaces() -> None:
    production_sources = (
        REPOSITORY_ROOT / "backend" / "dialogues" / "provider_registry.py",
        REPOSITORY_ROOT / "backend" / "dialogues" / "ced.py",
        REPOSITORY_ROOT / "backend" / "dialogues" / "conversation.py",
        REPOSITORY_ROOT
        / "backend"
        / "dialogues"
        / "socrates_zero"
        / "__init__.py",
    )
    for source_path in production_sources:
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        )
        assert not any("acquisition" in name for name in _imports(tree))


def test_positive_canned_case_avoids_network_credentials_provider_and_ced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every forbidden dynamic seam raises while a real canned case still passes."""

    hits: list[str] = []

    def forbidden(name: str):
        def fail(*_args, **_kwargs):
            hits.append(name)
            raise AssertionError(f"forbidden acquisition boundary crossed: {name}")

        return fail

    loop = asyncio.new_event_loop()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(socket, "create_connection", forbidden("socket.create_connection"))
            patch.setattr(socket, "getaddrinfo", forbidden("socket.getaddrinfo"))
            patch.setattr(socket.socket, "connect", forbidden("socket.socket.connect"))
            patch.setattr(socket.socket, "connect_ex", forbidden("socket.socket.connect_ex"))
            patch.setattr(socket.socket, "send", forbidden("socket.socket.send"))
            patch.setattr(socket.socket, "sendall", forbidden("socket.socket.sendall"))
            patch.setattr(urllib.request, "urlopen", forbidden("urllib.request.urlopen"))
            patch.setattr(http.client.HTTPConnection, "connect", forbidden("http.connect"))
            patch.setattr(http.client.HTTPSConnection, "connect", forbidden("https.connect"))
            patch.setattr(os, "getenv", forbidden("os.getenv"))
            patch.setattr(type(os.environ), "get", forbidden("os.environ.get"))
            patch.setattr(
                type(os.environ),
                "__getitem__",
                forbidden("os.environ.__getitem__"),
            )
            patch.setattr(
                provider_registry.CouncilProviderRegistry,
                "run_adapter",
                forbidden("CouncilProviderRegistry.run_adapter"),
            )
            patch.setattr(
                provider_registry.CouncilProviderRegistry,
                "gather_council_round",
                forbidden("CouncilProviderRegistry.gather_council_round"),
            )
            patch.setattr(
                CanonicalSuccessorEnvironmentV0,
                "apply_observation",
                forbidden("CanonicalSuccessorEnvironmentV0.apply_observation"),
            )

            fixtures = acquisition_evaluation.build_frozen_acquisition_fixtures_v0()
            case = FROZEN_ACQUISITION_POSITIVE_CASES_V0[0]
            result, executions = loop.run_until_complete(
                acquisition_evaluation._evaluate_positive_case(case, fixtures)
            )

        assert result.case_passed is True
        assert result.observed_canned_invocations == 1
        assert len(executions) == 1
        assert hits == []
    finally:
        loop.close()


def test_importing_evaluator_is_runtime_inert() -> None:
    assert acquisition_evaluation.__name__.endswith("acquisition_evaluation")
    assert not any(
        "acquisition" in name
        for name in _imports(
            ast.parse(
                (REPOSITORY_ROOT / "backend" / "dialogues" / "provider_registry.py").read_text(
                    encoding="utf-8"
                )
            )
        )
    )
