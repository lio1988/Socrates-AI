"""Static and dynamic locks for the acquisition-only authority boundary."""

from __future__ import annotations

import ast
import asyncio
import http.client
import io
import os
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from backend.dialogues import provider_registry
from backend.dialogues.ced_canonical_successor import (
    CanonicalSuccessorEnvironmentV0,
)
from backend.dialogues.socrates_zero import acquisition_evaluation
from backend.dialogues.socrates_zero.acquisition_contracts import (
    AcquisitionTripwireCounters,
)
from backend.dialogues.socrates_zero.acquisition_tripwires import (
    AcquisitionBoundaryTripwireV0,
    AcquisitionBoundaryViolation,
    active_acquisition_boundary_tripwire_v0,
    assert_acquisition_artifact_tripwires_v0,
    require_clean_acquisition_boundary_tripwire_v0,
)
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
    / "acquisition_isolation_evidence.py",
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
        "datetime",
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
        "time",
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
        ("verify_frozen_core_blob_lock_v0", "read_bytes"),
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


def test_reusable_tripwire_records_and_aborts_every_forbidden_category() -> None:
    def inactive_guard_result() -> type[BaseException] | None:
        try:
            require_clean_acquisition_boundary_tripwire_v0()
        except BaseException as exc:  # returned across the thread boundary
            return type(exc)
        return None

    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(inactive_guard_result).result() is (
            AcquisitionBoundaryViolation
        )

    def forbidden_udp_send() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.sendto(b"forbidden", ("127.0.0.1", 9))

    actions = (
        (
            "external_network_attempts",
            lambda: socket.getaddrinfo("forbidden.invalid", 443),
        ),
        (
            "external_network_attempts",
            forbidden_udp_send,
        ),
        (
            "credential_access_attempts",
            lambda: os.getenv("OPENROUTER_API_KEY"),
        ),
        (
            "live_provider_calls",
            lambda: provider_registry.CouncilProviderRegistry.run_adapter(None),
        ),
        (
            "provider_sdk_calls",
            lambda: provider_registry.BaseProviderAdapter.generate_agent_move(None),
        ),
        (
            "model_executions",
            lambda: __import__(
                "backend.dialogues.providers", fromlist=["FakeProvider"]
            ).FakeProvider.complete(None),
        ),
        (
            "tool_calls",
            lambda: __import__("subprocess").run(("forbidden-tool",)),
        ),
        (
            "canonical_application_calls",
            lambda: CanonicalSuccessorEnvironmentV0.apply_observation(None),
        ),
    )
    for category, action in actions:
        tripwire = AcquisitionBoundaryTripwireV0()
        with pytest.raises(AcquisitionBoundaryViolation):
            with tripwire:
                action()
        snapshot = tripwire.snapshot()
        assert snapshot.total_forbidden_attempts == 1
        assert getattr(snapshot, category) == 1
        assert len(snapshot.hits) == 1
        assert snapshot.hits[0].category == category


def _assert_single_credential_tripwire_abort(
    action,
    expected_seam: str | None = None,
) -> None:
    tripwire = AcquisitionBoundaryTripwireV0()
    with pytest.raises(AcquisitionBoundaryViolation):
        with tripwire:
            action()
    snapshot = tripwire.snapshot()
    assert snapshot.total_forbidden_attempts == 1
    assert snapshot.credential_access_attempts == 1
    assert len(snapshot.hits) == 1
    assert snapshot.hits[0].category == "credential_access_attempts"
    if expected_seam is not None:
        assert snapshot.hits[0].seam == expected_seam


def _assert_single_network_tripwire_abort(action, expected_seam: str) -> None:
    tripwire = AcquisitionBoundaryTripwireV0()
    with pytest.raises(AcquisitionBoundaryViolation):
        with tripwire:
            action()
    snapshot = tripwire.snapshot()
    assert snapshot.total_forbidden_attempts == 1
    assert snapshot.external_network_attempts == 1
    assert len(snapshot.hits) == 1
    assert snapshot.hits[0].category == "external_network_attempts"
    assert snapshot.hits[0].seam == expected_seam


@pytest.mark.parametrize(
    ("action", "expected_seam"),
    (
        pytest.param(
            lambda: socket.gethostbyname("forbidden.invalid"),
            "socket.gethostbyname",
            id="gethostbyname",
        ),
        pytest.param(
            lambda: socket.gethostbyname_ex("forbidden.invalid"),
            "socket.gethostbyname_ex",
            id="gethostbyname-ex",
        ),
        pytest.param(
            lambda: socket.gethostbyaddr("203.0.113.1"),
            "socket.gethostbyaddr",
            id="gethostbyaddr",
        ),
        pytest.param(
            lambda: socket.getnameinfo(("203.0.113.1", 443), 0),
            "socket.getnameinfo",
            id="getnameinfo",
        ),
        pytest.param(
            lambda: socket.getfqdn("forbidden.invalid"),
            "socket.getfqdn",
            id="getfqdn",
        ),
    ),
)
def test_network_tripwire_rejects_all_available_dns_resolution_seams(
    action,
    expected_seam: str,
) -> None:
    _assert_single_network_tripwire_abort(action, expected_seam)


@pytest.mark.parametrize(
    "key",
    (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "HF_TOKEN",
        "HUGGINGFACEHUB_API_TOKEN",
        "NPM_TOKEN",
    ),
)
def test_credential_tripwire_rejects_common_secret_environment_keys(
    key: str,
) -> None:
    _assert_single_credential_tripwire_abort(lambda: os.getenv(key))


@pytest.mark.parametrize(
    "action",
    (
        pytest.param(
            lambda: "OPENROUTER_API_KEY" in os.environ,
            id="contains-secret-key",
        ),
        pytest.param(lambda: iter(os.environ), id="iterate"),
        pytest.param(lambda: os.environ.keys(), id="keys"),
    ),
)
def test_credential_tripwire_rejects_environment_existence_and_enumeration(
    action,
) -> None:
    _assert_single_credential_tripwire_abort(action)


@pytest.mark.parametrize(
    ("action", "expected_seam"),
    (
        pytest.param(
            lambda: os.environ.pop("OPENROUTER_API_KEY", None),
            "os.environ.pop:OPENROUTER_API_KEY",
            id="pop-secret-key",
        ),
        pytest.param(
            lambda: os.environ.setdefault("OPENROUTER_API_KEY", "forbidden"),
            "os.environ.setdefault:OPENROUTER_API_KEY",
            id="setdefault-secret-key",
        ),
        pytest.param(
            lambda: os.environ.popitem(),
            "os.environ.popitem",
            id="popitem",
        ),
    ),
)
def test_credential_tripwire_rejects_environment_pop_seams(
    action,
    expected_seam: str,
) -> None:
    _assert_single_credential_tripwire_abort(action, expected_seam)


@pytest.mark.skipif(
    not hasattr(os, "getenvb") or not hasattr(os, "environb"),
    reason="byte environment APIs are unavailable on this platform",
)
@pytest.mark.parametrize(
    "action",
    (
        pytest.param(
            lambda: os.getenvb(b"OPENROUTER_API_KEY"),
            id="getenvb-secret-key",
        ),
        pytest.param(
            lambda: os.environb.get(b"OPENROUTER_API_KEY"),
            id="environb-get-secret-key",
        ),
        pytest.param(
            lambda: b"OPENROUTER_API_KEY" in os.environb,
            id="environb-contains-secret-key",
        ),
        pytest.param(lambda: iter(os.environb), id="environb-iterate"),
        pytest.param(lambda: os.environb.keys(), id="environb-keys"),
        pytest.param(
            lambda: os.environb.pop(b"OPENROUTER_API_KEY", None),
            id="environb-pop-secret-key",
        ),
        pytest.param(
            lambda: os.environb.setdefault(b"OPENROUTER_API_KEY", b"forbidden"),
            id="environb-setdefault-secret-key",
        ),
        pytest.param(lambda: os.environb.popitem(), id="environb-popitem"),
    ),
)
def test_credential_tripwire_rejects_byte_environment_reads(action) -> None:
    _assert_single_credential_tripwire_abort(action)


@pytest.mark.parametrize(
    "action",
    (
        pytest.param(lambda: os.environ.copy(), id="copy"),
        pytest.param(lambda: os.environ.items(), id="items"),
        pytest.param(lambda: os.environ.values(), id="values"),
    ),
)
def test_credential_tripwire_rejects_bulk_environment_reads(action) -> None:
    _assert_single_credential_tripwire_abort(action)


@pytest.mark.parametrize(
    "action",
    (
        pytest.param(lambda: io.open(".netrc", "rb"), id="io-open-netrc"),
        pytest.param(
            lambda: os.open("credentials.json", os.O_RDONLY),
            id="os-open-credentials",
        ),
    ),
)
def test_credential_tripwire_rejects_low_level_credential_file_reads(action) -> None:
    _assert_single_credential_tripwire_abort(action)


@pytest.mark.parametrize(
    "action",
    (
        pytest.param(lambda: Path(".netrc").exists(), id="path-exists"),
        pytest.param(lambda: Path("credentials.json").stat(), id="path-stat"),
        pytest.param(lambda: Path(".ssh").lstat(), id="path-lstat"),
        pytest.param(lambda: Path("secrets.json").is_file(), id="path-is-file"),
        pytest.param(lambda: Path(".aws").is_dir(), id="path-is-dir"),
        pytest.param(lambda: os.stat(".env"), id="os-stat"),
        pytest.param(lambda: os.lstat("token.json"), id="os-lstat"),
        pytest.param(lambda: os.access("auth.json", os.F_OK), id="os-access"),
        pytest.param(lambda: os.path.exists(".netrc"), id="os-path-exists"),
        pytest.param(lambda: os.path.lexists(".env.local"), id="os-path-lexists"),
        pytest.param(
            lambda: os.path.isfile(".ssh/id_rsa"),
            id="os-path-isfile",
        ),
        pytest.param(
            lambda: os.path.isdir(".aws"),
            id="os-path-isdir",
        ),
        pytest.param(lambda: os.stat(b"credentials.json"), id="bytes-os-stat"),
    ),
)
def test_credential_tripwire_rejects_credential_file_metadata_probes(action) -> None:
    _assert_single_credential_tripwire_abort(action)


def test_credential_tripwire_preserves_noncredential_environment_and_file_checks() -> None:
    expected_path_membership = "PATH" in os.environ
    assert ("PATH" in os.environ) is expected_path_membership
    assert "SOCRATES_ZERO_TEST_MISSING" not in os.environ
    assert Path(__file__).exists()
    assert Path(__file__).is_file()
    assert os.path.exists(__file__)
    assert os.path.isfile(__file__)


def test_artifact_zero_counters_are_cross_checked_against_live_instrumentation() -> None:
    tripwire = active_acquisition_boundary_tripwire_v0()
    clean = tripwire.assert_clean()
    assert clean.total_forbidden_attempts == 0
    zero = AcquisitionTripwireCounters(
        canned_transport_invocations=1,
        external_network_attempts=0,
        credential_access_attempts=0,
        live_provider_calls=0,
        provider_sdk_calls=0,
        model_executions=0,
        tool_calls=0,
        canonical_application_calls=0,
    )
    assert_acquisition_artifact_tripwires_v0(zero)

    claimed_attempt = zero.model_copy(update={"external_network_attempts": 1})
    with pytest.raises(
        AcquisitionBoundaryViolation,
        match="differ from instrumented boundary evidence",
    ):
        assert_acquisition_artifact_tripwires_v0(claimed_attempt)
