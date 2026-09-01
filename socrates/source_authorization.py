"""Fail-closed source authorization for the Normal Live browser runtime.

The production verifier intentionally has no configuration or environment
override.  A later, artifact-only commit may add the fixed manifest that
authorizes an independently reviewed implementation commit.  Until then the
production entry point always fails closed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SCHEMA_VERSION = "normal-live-source-set/v1"
RUNTIME_IDENTITY = "normal-socrates-browser-runtime/v1"
AUTHORIZATION_ID_PREFIX = "normallivesourceauthv1_"
OPERATOR_AUTHORIZATION_STATEMENT_V1 = (
    "I explicitly authorize the exact Normal Live implementation source set "
    "identified by this manifest for normal-socrates-browser-runtime/v1."
)
PRODUCTION_MANIFEST_RELATIVE_PATH = "authorization/normal-live-source-set-v1.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_MAX_SOURCE_FILE_BYTES = 16 * 1024 * 1024
_MAX_SOURCE_SET_BYTES = 64 * 1024 * 1024
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_UTC_RFC3339 = re.compile(
    r"^(?:[0-9]{4})-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\.[0-9]+)?Z$"
)


# This tuple is the reviewed execution-source universe, not a manifest input.
# Its breadth is intentional: broad package ``__init__`` modules execute and may
# import otherwise runtime-inert modules, so those imports must also be bound.
# Tests, docs/handoffs, JUnit and generated run artifacts, raster/logo assets,
# third-party packages/interpreters, and the future authorization artifact are
# excluded.  Three immutable JSON policy/profile inputs remain bound despite
# their historical docs/runs/evidence locations because live construction reads
# them directly.
# The manifest is authority evidence, never self-authorizing executable source.
# CSS remains included because it controls whether confirmation is visible;
# ``.gitattributes`` is bound because it controls deterministic checkout bytes.
NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1: tuple[str, ...] = (
    ".gitattributes",
    "backend/__init__.py",
    "backend/api/__init__.py",
    "backend/api/routes_council.py",
    "backend/dialogues/__init__.py",
    "backend/dialogues/agent.py",
    "backend/dialogues/ced.py",
    "backend/dialogues/conversation.py",
    "backend/dialogues/council_live.py",
    "backend/dialogues/deliberation_tree.py",
    "backend/dialogues/hybrid_epistemic.py",
    "backend/dialogues/hybrid_shadow.py",
    "backend/dialogues/learning_alignment_exporter.py",
    "backend/dialogues/learning_dry_run_cli.py",
    "backend/dialogues/learning_foundation.py",
    "backend/dialogues/learning_preference_miner.py",
    "backend/dialogues/learning_process_miner.py",
    "backend/dialogues/learning_quality_gates.py",
    "backend/dialogues/learning_trace_collector.py",
    "backend/dialogues/learning_training_planner.py",
    "backend/dialogues/live_providers.py",
    "backend/dialogues/living_system.py",
    "backend/dialogues/model_identity.py",
    "backend/dialogues/models.py",
    "backend/dialogues/normal_live.py",
    "backend/dialogues/nvidia_nim_provider.py",
    "backend/dialogues/offline_provider_adapter.py",
    "backend/dialogues/openclaw_memory/__init__.py",
    "backend/dialogues/openclaw_memory/context_injection.py",
    "backend/dialogues/openclaw_memory/lesson_ab.py",
    "backend/dialogues/openclaw_memory/lesson_loader.py",
    "backend/dialogues/openclaw_memory/lesson_proposer.py",
    "backend/dialogues/openclaw_memory/lesson_retriever.py",
    "backend/dialogues/openclaw_memory/trace_capture.py",
    "backend/dialogues/openrouter_provider.py",
    "backend/dialogues/provider_registry.py",
    "backend/dialogues/providers.py",
    "backend/dialogues/reasoning_prompts.py",
    "backend/dialogues/role_assignment.py",
    "backend/dialogues/self_improvement.py",
    "backend/dialogues/semantic_floor.py",
    "backend/dialogues/socrates_zero/__init__.py",
    "backend/dialogues/socrates_zero/baseline.py",
    "backend/dialogues/socrates_zero/ced_structured_output_v1.py",
    "backend/dialogues/socrates_zero/constitution.py",
    "backend/dialogues/socrates_zero/contracts.py",
    "backend/dialogues/socrates_zero/evaluation.py",
    "backend/dialogues/socrates_zero/evaluation_cases.py",
    "backend/dialogues/socrates_zero/evaluation_harness.py",
    "backend/dialogues/socrates_zero/openrouter_live_request_overlay_v1.py",
    "backend/dialogues/socrates_zero/openrouter_live_request_overlay_v2.py",
    "backend/dialogues/socrates_zero/openrouter_live_safety_closure_v1.py",
    "backend/dialogues/socrates_zero/openrouter_live_session_adapter_v1.py",
    "backend/dialogues/socrates_zero/openrouter_live_session_v1.py",
    "backend/dialogues/socrates_zero/openrouter_one_live_shadow_runner_v1.py",
    "backend/dialogues/socrates_zero/openrouter_one_live_shadow_v1.py",
    "backend/dialogues/socrates_zero/openrouter_pre_live_integration_v1.py",
    "backend/dialogues/socrates_zero/openrouter_pre_live_safety_v1.py",
    "backend/dialogues/socrates_zero/openrouter_raw_wire_mapping_v2.py",
    "backend/dialogues/socrates_zero/openrouter_reduced_benchmark_safety_v1.py",
    "backend/dialogues/socrates_zero/openrouter_request_bounds_v1.py",
    "backend/dialogues/socrates_zero/openrouter_route_controls_contracts.py",
    "backend/dialogues/socrates_zero/openrouter_route_controls_renderer.py",
    "backend/dialogues/socrates_zero/openrouter_trusted_input_bound_v1.py",
    "backend/dialogues/socrates_zero/policy.py",
    "backend/dialogues/socrates_zero/protocol_authorization_v1.py",
    "backend/dialogues/socrates_zero/puct.py",
    "backend/dialogues/socrates_zero/reduced_benchmark_evaluation_v1.py",
    "backend/dialogues/socrates_zero/strategy.py",
    "backend/dialogues/socrates_zero/value.py",
    "backend/dialogues/socratic.py",
    "backend/dialogues/task_checker.py",
    "backend/dialogues/topic.py",
    "backend/local_ced_app.py",
    "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs/hard_logic_live_test_collection_v1.json",
    "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs/q1_gemini_3_7_flash_endpoints_v1.json",
    "docs/branches/feature-socrates-zero-openrouter-one-live-shadow-v1/evidence/s7c_model_endpoints_response_v1.json",
    "scripts/q2_ethics_question_v1.py",
    "scripts/q3_ethics_question_v1.py",
    "scripts/q4_ethics_question_v1.py",
    "scripts/q5_ethics_question_v1.py",
    "scripts/q6_ethics_question_v1.py",
    "scripts/question_bundles_v1.py",
    "scripts/run_hard_logic_live_test_v1.py",
    "scripts/run_multimodel_q1_ced_v1.py",
    "scripts/run_multimodel_q1_v1.py",
    "scripts/run_reduced_socrates_benchmark_v1.py",
    "scripts/run_socrates_live_v1.py",
    "socrates/__init__.py",
    "socrates/planning.py",
    "socrates/rendering.py",
    "socrates/runtime.py",
    "socrates/source_authorization.py",
    "web/app.js",
    "web/ced-bridge.js",
    "web/index.html",
    "web/styles.css",
)


class NormalLiveSourceAuthorizationError(RuntimeError):
    """Internal fail-closed error with deliberately non-sensitive public text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("Normal Live source authorization failed.")


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NormalLiveSourceFileV1(_FrozenModel):
    path: str
    sha256: str

    @field_validator("path")
    @classmethod
    def _path_is_normalized(cls, value: str) -> str:
        _validate_source_path(value)
        return value

    @field_validator("sha256")
    @classmethod
    def _sha_is_lower_hex(cls, value: str) -> str:
        if not _HEX64.fullmatch(value):
            raise ValueError("invalid digest")
        return value


class NormalLiveSourceProvenanceV1(_FrozenModel):
    authorization_basis: str = "explicit-operator-review"
    created_at_utc: str

    @field_validator("authorization_basis")
    @classmethod
    def _basis_is_fixed(cls, value: str) -> str:
        if value != "explicit-operator-review":
            raise ValueError("invalid authorization basis")
        return value

    @field_validator("created_at_utc")
    @classmethod
    def _timestamp_is_strict_utc(cls, value: str) -> str:
        if not _UTC_RFC3339.fullmatch(value):
            raise ValueError("invalid UTC timestamp")
        try:
            datetime.fromisoformat(value[:-1] + "+00:00")
        except ValueError as exc:
            raise ValueError("invalid UTC timestamp") from exc
        return value


class NormalLiveSourceAuthorizationV1(_FrozenModel):
    schema_version: str = SCHEMA_VERSION
    runtime_identity: str = RUNTIME_IDENTITY
    authorized_implementation_commit_sha: str
    authorized_implementation_tree_sha: str
    source_files: tuple[NormalLiveSourceFileV1, ...]
    source_set_digest: str
    operator_authorization_statement: str = Field(min_length=1, max_length=4096)
    provenance: NormalLiveSourceProvenanceV1
    authorization_id: str

    @field_validator("schema_version")
    @classmethod
    def _schema_is_fixed(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError("invalid schema")
        return value

    @field_validator("runtime_identity")
    @classmethod
    def _runtime_is_fixed(cls, value: str) -> str:
        if value != RUNTIME_IDENTITY:
            raise ValueError("invalid runtime")
        return value

    @field_validator(
        "authorized_implementation_commit_sha",
        "authorized_implementation_tree_sha",
    )
    @classmethod
    def _object_id_is_lower_hex(cls, value: str) -> str:
        if not _HEX40.fullmatch(value):
            raise ValueError("invalid object id")
        return value

    @field_validator("source_set_digest")
    @classmethod
    def _source_digest_is_lower_hex(cls, value: str) -> str:
        if not _HEX64.fullmatch(value):
            raise ValueError("invalid source-set digest")
        return value

    @field_validator("operator_authorization_statement")
    @classmethod
    def _statement_is_material(cls, value: str) -> str:
        if value != OPERATOR_AUTHORIZATION_STATEMENT_V1:
            raise ValueError("invalid operator statement")
        return value

    @field_validator("authorization_id")
    @classmethod
    def _authorization_id_is_content_addressed(cls, value: str) -> str:
        suffix = value.removeprefix(AUTHORIZATION_ID_PREFIX)
        if not value.startswith(AUTHORIZATION_ID_PREFIX) or not _HEX64.fullmatch(suffix):
            raise ValueError("invalid authorization id")
        return value


class VerifiedNormalLiveSourceAuthorizationV1(_FrozenModel):
    authorization_id: str
    source_set_digest: str
    authorized_implementation_commit_sha: str
    authorized_implementation_tree_sha: str
    runtime_identity: str


def _fail(code: str) -> None:
    raise NormalLiveSourceAuthorizationError(code)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_source_path(value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or "\\" in value
    ):
        raise ValueError("invalid source path")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError("invalid source path")
    if "//" in value or value.startswith("./") or value.endswith("/"):
        raise ValueError("invalid source path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("invalid source path")
    if PurePosixPath(value).as_posix() != value:
        raise ValueError("invalid source path")


def _validate_expected_paths(paths: Sequence[str]) -> tuple[str, ...]:
    if isinstance(paths, (str, bytes)):
        _fail("source_universe_invalid")
    result = tuple(paths)
    try:
        for path in result:
            _validate_source_path(path)
    except (TypeError, ValueError):
        _fail("source_universe_invalid")
    if not result or result != tuple(sorted(result)) or len(result) != len(set(result)):
        _fail("source_universe_invalid")
    return result


def _git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
    )
    return environment


def _trusted_git_executable(repository_root: Path) -> str:
    root = Path(os.path.abspath(repository_root))
    for name in ("git", "git.exe", "git.com", "git.cmd", "git.bat"):
        candidate = root / name
        try:
            os.lstat(candidate)
        except FileNotFoundError:
            continue
        except OSError:
            _fail("git_unavailable")
        else:
            _fail("git_executable_shadow")

    executable_name = "git.exe" if os.name == "nt" else "git"
    path_value = os.environ.get("PATH")
    if not path_value:
        _fail("git_unavailable")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError:
        _fail("git_unavailable")
    for raw_entry in path_value.split(os.pathsep):
        entry = raw_entry.strip().strip('"')
        if not entry:
            continue
        directory = Path(entry)
        if not directory.is_absolute():
            continue
        candidate = directory / executable_name
        try:
            resolved = candidate.resolve(strict=True)
            info = os.stat(resolved)
        except FileNotFoundError:
            continue
        except OSError:
            _fail("git_unavailable")
        if not stat.S_ISREG(info.st_mode) or not resolved.is_absolute():
            _fail("git_unavailable")
        try:
            resolved.relative_to(resolved_root)
        except ValueError:
            return os.fspath(resolved)
        _fail("git_executable_shadow")
    _fail("git_unavailable")


def _git(
    repository_root: Path,
    *args: str,
    check: bool = True,
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    try:
        input_options: dict[str, Any]
        if input_data is None:
            input_options = {"stdin": subprocess.DEVNULL}
        else:
            input_options = {"input": input_data}
        completed = subprocess.run(
            [
                _trusted_git_executable(repository_root),
                "--no-pager",
                "--no-replace-objects",
                "--literal-pathspecs",
                "-c",
                f"safe.directory={repository_root.as_posix()}",
                "-C",
                os.fspath(repository_root),
                "-c",
                "core.fsmonitor=false",
                "-c",
                f"core.attributesFile={os.devnull}",
                "-c",
                f"core.excludesFile={os.devnull}",
                *args,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_git_environment(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=10.0,
            **input_options,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        _fail("git_unavailable")
    if completed.returncode == 0 and completed.stderr:
        _fail("git_verification_failed")
    if check and completed.returncode != 0:
        _fail("git_verification_failed")
    return completed


def _git_text(repository_root: Path, *args: str) -> str:
    raw = _git(repository_root, *args).stdout
    try:
        return raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        _fail("git_verification_failed")


def _deterministic_checkout_attributes(
    repository_root: Path, relative_paths: Sequence[str]
) -> dict[str, tuple[str, str]]:
    paths = tuple(relative_paths)
    if not paths:
        return {}
    expected_attributes = {
        "text",
        "eol",
        "filter",
        "working-tree-encoding",
        "ident",
    }
    fields = _git(
        repository_root,
        "check-attr",
        "-z",
        "text",
        "eol",
        "filter",
        "working-tree-encoding",
        "ident",
        "--",
        *paths,
    ).stdout.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) != len(paths) * len(expected_attributes) * 3:
        _fail("checkout_filter_unsupported")
    expected_paths = set(paths)
    values_by_path: dict[str, dict[str, str]] = {}
    try:
        for index in range(0, len(fields), 3):
            path, attribute, value = (
                item.decode("utf-8", errors="strict")
                for item in fields[index:index + 3]
            )
            if path not in expected_paths or attribute not in expected_attributes:
                _fail("checkout_filter_unsupported")
            values = values_by_path.setdefault(path, {})
            if attribute in values:
                _fail("checkout_filter_unsupported")
            values[attribute] = value
    except UnicodeDecodeError:
        _fail("checkout_filter_unsupported")

    result: dict[str, tuple[str, str]] = {}
    for path in paths:
        values = values_by_path.get(path)
        if values is None or set(values) != expected_attributes:
            _fail("checkout_filter_unsupported")
        text_value = values["text"]
        eol_value = values["eol"]
        if not (
            (text_value == "set" and eol_value in {"lf", "crlf"})
            or (text_value == "unset" and eol_value == "unspecified")
        ):
            _fail("checkout_filter_unsupported")
        if any(
            values[attribute] != "unspecified"
            for attribute in ("filter", "working-tree-encoding", "ident")
        ):
            _fail("checkout_filter_unsupported")
        result[path] = (text_value, eol_value)
    return result


def _require_deterministic_checkout_attributes(
    repository_root: Path, relative_path: str
) -> None:
    _deterministic_checkout_attributes(repository_root, (relative_path,))


def _parse_tree_entries(
    raw: bytes, relative_paths: Sequence[str]
) -> dict[str, tuple[str, str, int]]:
    expected_paths = set(relative_paths)
    entries: dict[str, tuple[str, str, int]] = {}
    aggregate_size = 0
    records = tuple(item for item in raw.split(b"\0") if item)
    for record in records:
        try:
            header, path_bytes = record.split(b"\t", 1)
            mode_raw, type_raw, object_id_raw, size_raw = header.split(b" ", 3)
            mode = mode_raw.decode("ascii", errors="strict")
            object_type = type_raw.decode("ascii", errors="strict")
            object_id = object_id_raw.decode("ascii", errors="strict")
            size_text = size_raw.decode("ascii", errors="strict")
            path = path_bytes.decode("utf-8", errors="strict")
            size = int(size_text)
        except (UnicodeDecodeError, ValueError):
            _fail("git_verification_failed")
        if (
            path not in expected_paths
            or path in entries
            or object_type != "blob"
            or mode not in {"100644", "100755"}
            or not _HEX40.fullmatch(object_id)
            or size < 0
            or size > _MAX_SOURCE_FILE_BYTES
        ):
            _fail("source_missing_from_commit")
        aggregate_size += size
        if aggregate_size > _MAX_SOURCE_SET_BYTES:
            _fail("source_set_too_large")
        entries[path] = (mode, object_id, size)
    if set(entries) != expected_paths:
        _fail("source_missing_from_commit")
    return entries


def _tree_entries(
    repository_root: Path, commit: str, relative_paths: Sequence[str]
) -> dict[str, tuple[str, str, int]]:
    return _parse_tree_entries(
        _git(
            repository_root,
            "ls-tree",
            "-lrz",
            commit,
            "--",
            *tuple(relative_paths),
        ).stdout,
        relative_paths,
    )


def _parse_batch_blobs(
    raw: bytes,
    requests: Sequence[tuple[str, str, int]],
) -> dict[str, bytes]:
    position = 0
    result: dict[str, bytes] = {}
    for path, expected_object_id, expected_size in requests:
        line_end = raw.find(b"\n", position)
        if line_end < position or line_end - position > 160:
            _fail("git_verification_failed")
        try:
            object_id_raw, object_type_raw, size_raw = raw[position:line_end].split(
                b" ", 2
            )
            object_id = object_id_raw.decode("ascii", errors="strict")
            object_type = object_type_raw.decode("ascii", errors="strict")
            declared_size = int(size_raw.decode("ascii", errors="strict"))
        except (UnicodeDecodeError, ValueError):
            _fail("git_verification_failed")
        if (
            object_id != expected_object_id
            or object_type != "blob"
            or declared_size != expected_size
            or declared_size < 0
            or declared_size > _MAX_SOURCE_FILE_BYTES
        ):
            _fail("git_verification_failed")
        start = line_end + 1
        end = start + declared_size
        if end >= len(raw) or raw[end:end + 1] != b"\n":
            _fail("git_verification_failed")
        result[path] = raw[start:end]
        position = end + 1
    if position != len(raw) or len(result) != len(requests):
        _fail("git_verification_failed")
    return result


def _batch_commit_blobs(
    repository_root: Path,
    entries: Mapping[str, tuple[str, str, int]],
    relative_paths: Sequence[str],
) -> dict[str, bytes]:
    requests = tuple(
        (path, entries[path][1], entries[path][2]) for path in relative_paths
    )
    input_data = b"".join(
        object_id.encode("ascii") + b"\n"
        for _path, object_id, _size in requests
    )
    raw = _git(
        repository_root,
        "cat-file",
        "--batch",
        input_data=input_data,
    ).stdout
    return _parse_batch_blobs(raw, requests)


def _materialize_checkout_bytes(
    blob: bytes, attributes: tuple[str, str]
) -> bytes:
    text_value, eol_value = attributes
    if text_value == "unset" and eol_value == "unspecified":
        return blob
    if (
        text_value != "set"
        or eol_value not in {"lf", "crlf"}
        or b"\r" in blob
        or b"\0" in blob
    ):
        _fail("checkout_filter_unsupported")
    return blob if eol_value == "lf" else blob.replace(b"\n", b"\r\n")


def _path_is_redirected(path: Path, *, stop_at: Path | None = None) -> bool:
    current = path
    while True:
        try:
            info = os.lstat(current)
        except OSError:
            return True
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or (
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            return True
        if stop_at is not None and current == stop_at:
            return False
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _ensure_regular_unredirected(
    path: Path, missing_code: str, *, repository_root: Path
) -> None:
    try:
        info = os.lstat(path)
    except OSError:
        _fail(missing_code)
    if _path_is_redirected(
        path, stop_at=repository_root
    ) or not stat.S_ISREG(info.st_mode):
        _fail("source_path_redirected")


def _reject_authorized_bytecode_caches(
    repository_root: Path, paths: Sequence[str]
) -> None:
    for relative in paths:
        if not relative.lower().endswith(".py"):
            continue
        source = repository_root.joinpath(*relative.split("/"))
        legacy = source.with_suffix(".pyc")
        try:
            os.lstat(legacy)
        except FileNotFoundError:
            pass
        except OSError:
            _fail("authorized_bytecode_cache_indeterminate")
        else:
            _fail("authorized_bytecode_cache_present")

        cache_directory = source.parent / "__pycache__"
        try:
            entries = tuple(os.scandir(cache_directory))
        except FileNotFoundError:
            continue
        except OSError:
            _fail("authorized_bytecode_cache_indeterminate")
        prefix = source.stem.lower() + "."
        if any(
            entry.name.lower().startswith(prefix)
            and entry.name.lower().endswith(".pyc")
            for entry in entries
        ):
            _fail("authorized_bytecode_cache_present")


def _reject_ignored_executable_shadows(repository_root: Path) -> None:
    raw = _git(
        repository_root,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "-z",
        "--",
    ).stdout
    try:
        paths = tuple(
            item.decode("utf-8", errors="strict")
            for item in raw.split(b"\0")
            if item
        )
    except UnicodeDecodeError:
        _fail("ignored_executable_shadow")
    executable_suffixes = {
        ".bat",
        ".cmd",
        ".com",
        ".exe",
        ".py",
        ".pyw",
        ".ps1",
        ".pth",
        ".pyd",
        ".so",
        ".dll",
    }
    for relative in paths:
        candidate = repository_root.joinpath(*PurePosixPath(relative).parts)
        try:
            info = os.lstat(candidate)
        except OSError:
            _fail("ignored_executable_shadow")
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or (
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            _fail("ignored_executable_shadow")
        lowered = relative.lower()
        suffix = Path(lowered).suffix
        components = PurePosixPath(lowered).parts
        legacy_bytecode = (
            suffix in {".pyc", ".pyo"} and "__pycache__" not in components
        )
        if suffix in executable_suffixes or legacy_bytecode:
            _fail("ignored_executable_shadow")


def _repository_relative_path(root: Path, path: Path) -> str:
    root_absolute = Path(os.path.abspath(root))
    path_absolute = Path(os.path.abspath(path))
    try:
        relative = path_absolute.relative_to(root_absolute).as_posix()
    except ValueError:
        _fail("manifest_path_invalid")
    try:
        _validate_source_path(relative)
    except ValueError:
        _fail("manifest_path_invalid")
    return relative


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _strict_manifest_shape(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("manifest must be an object")
    exact = {
        "schema_version",
        "runtime_identity",
        "authorized_implementation_commit_sha",
        "authorized_implementation_tree_sha",
        "source_files",
        "source_set_digest",
        "operator_authorization_statement",
        "provenance",
        "authorization_id",
    }
    if set(payload) != exact:
        raise ValueError("manifest fields differ")
    string_fields = exact - {"source_files", "provenance"}
    if any(type(payload[field]) is not str for field in string_fields):
        raise ValueError("manifest scalar type differs")
    files = payload["source_files"]
    if type(files) is not list or not files:
        raise ValueError("source files must be a nonempty array")
    for item in files:
        if type(item) is not dict or set(item) != {"path", "sha256"}:
            raise ValueError("source file fields differ")
        if type(item["path"]) is not str or type(item["sha256"]) is not str:
            raise ValueError("source file scalar type differs")
    provenance = payload["provenance"]
    if type(provenance) is not dict or set(provenance) != {
        "authorization_basis",
        "created_at_utc",
    }:
        raise ValueError("provenance fields differ")
    if any(type(value) is not str for value in provenance.values()):
        raise ValueError("provenance scalar type differs")


def _manifest_source_basis(manifest: NormalLiveSourceAuthorizationV1) -> dict[str, Any]:
    return {
        "schema_version": manifest.schema_version,
        "runtime_identity": manifest.runtime_identity,
        "authorized_implementation_commit_sha": (
            manifest.authorized_implementation_commit_sha
        ),
        "authorized_implementation_tree_sha": manifest.authorized_implementation_tree_sha,
        "source_files": [
            source.model_dump(mode="json") for source in manifest.source_files
        ],
    }


def _source_set_digest(manifest: NormalLiveSourceAuthorizationV1) -> str:
    return _sha256(_canonical_json_bytes(_manifest_source_basis(manifest)))


def _authorization_id(manifest: NormalLiveSourceAuthorizationV1) -> str:
    payload = manifest.model_dump(mode="json")
    payload.pop("authorization_id", None)
    return AUTHORIZATION_ID_PREFIX + _sha256(_canonical_json_bytes(payload))


def _commit_blob(repository_root: Path, commit: str, path: str) -> bytes:
    result = _git(repository_root, "cat-file", "blob", f"{commit}:{path}", check=False)
    if result.returncode != 0:
        _fail("source_missing_from_commit")
    return result.stdout


def _tree_mode(repository_root: Path, commit: str, path: str) -> str | None:
    result = _git(repository_root, "ls-tree", "-z", commit, "--", path, check=False)
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        header, returned_path = result.stdout.rstrip(b"\x00").split(b"\t", 1)
        mode, object_type, _object_id = header.decode("ascii").split(" ", 2)
        decoded_path = returned_path.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        _fail("git_verification_failed")
    if decoded_path != path or object_type != "blob":
        return None
    return mode


def _scoped_dirty(repository_root: Path, paths: Iterable[str]) -> bool:
    result = _git(
        repository_root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        *tuple(paths),
    )
    return bool(result.stdout)


def build_normal_live_source_authorization_v1(
    *,
    repository_root: Path,
    authorized_implementation_commit_sha: str,
    authorized_implementation_tree_sha: str,
    expected_source_paths: Sequence[str],
    operator_statement: str,
    created_at_utc: str,
) -> NormalLiveSourceAuthorizationV1:
    """Build an in-memory authorization fixture; never writes an artifact."""

    root = Path(repository_root)
    paths = _validate_expected_paths(expected_source_paths)
    if not _HEX40.fullmatch(authorized_implementation_commit_sha):
        _fail("commit_invalid")
    if not _HEX40.fullmatch(authorized_implementation_tree_sha):
        _fail("tree_invalid")
    files = tuple(
        NormalLiveSourceFileV1(
            path=path,
            sha256=_sha256(
                _commit_blob(root, authorized_implementation_commit_sha, path)
            ),
        )
        for path in paths
    )
    provisional = NormalLiveSourceAuthorizationV1(
        authorized_implementation_commit_sha=authorized_implementation_commit_sha,
        authorized_implementation_tree_sha=authorized_implementation_tree_sha,
        source_files=files,
        source_set_digest="0" * 64,
        operator_authorization_statement=operator_statement,
        provenance=NormalLiveSourceProvenanceV1(created_at_utc=created_at_utc),
        authorization_id=AUTHORIZATION_ID_PREFIX + "0" * 64,
    )
    with_source_digest = provisional.model_copy(
        update={"source_set_digest": _source_set_digest(provisional)}
    )
    return with_source_digest.model_copy(
        update={"authorization_id": _authorization_id(with_source_digest)}
    )


def verify_normal_live_source_authorization_v1(
    *,
    repository_root: Path,
    manifest_path: Path,
    expected_source_paths: Sequence[str],
) -> VerifiedNormalLiveSourceAuthorizationV1:
    """Verify a fixed source universe against a separate authorization commit."""

    root = Path(repository_root)
    paths = _validate_expected_paths(expected_source_paths)
    try:
        root_absolute = Path(os.path.abspath(root))
        if not root_absolute.is_dir() or _path_is_redirected(
            root_absolute, stop_at=root_absolute
        ):
            _fail("repository_invalid")
        actual_root = Path(_git_text(root_absolute, "rev-parse", "--show-toplevel"))
        if actual_root.resolve(strict=True) != root_absolute.resolve(strict=True):
            _fail("repository_mismatch")
        checked_head = _git_text(
            root_absolute, "rev-parse", "--verify", "HEAD^{commit}"
        )
        if not _HEX40.fullmatch(checked_head):
            _fail("repository_invalid")
        info_attributes = Path(
            _git_text(root_absolute, "rev-parse", "--git-path", "info/attributes")
        )
        if not info_attributes.is_absolute():
            info_attributes = root_absolute / info_attributes
        try:
            os.lstat(info_attributes)
        except FileNotFoundError:
            pass
        except OSError:
            _fail("repository_invalid")
        else:
            _fail("attribute_override_present")
    except NormalLiveSourceAuthorizationError:
        raise
    except (OSError, RuntimeError):
        _fail("repository_invalid")

    manifest = Path(manifest_path)
    manifest_relative = _repository_relative_path(root_absolute, manifest)
    if manifest_relative in paths:
        _fail("manifest_self_authorizing")
    if not manifest.exists():
        _fail("manifest_absent")
    _ensure_regular_unredirected(
        manifest, "manifest_absent", repository_root=root_absolute
    )
    try:
        if os.lstat(manifest).st_size > _MAX_MANIFEST_BYTES:
            _fail("manifest_invalid")
        with manifest.open("rb") as handle:
            raw = handle.read(_MAX_MANIFEST_BYTES + 1)
    except OSError:
        _fail("manifest_absent")
    if not raw or len(raw) > _MAX_MANIFEST_BYTES:
        _fail("manifest_invalid")
    try:
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non-finite JSON value")
            ),
        )
        _strict_manifest_shape(payload)
        if _canonical_json_bytes(payload) != raw:
            raise ValueError("manifest is not canonical JSON")
        parsed = NormalLiveSourceAuthorizationV1.model_validate(payload)
    except (
        UnicodeDecodeError,
        ValueError,
        TypeError,
        ValidationError,
        RecursionError,
    ):
        _fail("manifest_invalid")

    manifest_paths = tuple(source.path for source in parsed.source_files)
    try:
        for source_path in manifest_paths:
            _validate_source_path(source_path)
    except ValueError:
        _fail("source_path_invalid")
    if len(manifest_paths) != len(set(manifest_paths)):
        _fail("source_universe_mismatch")
    if manifest_paths != paths:
        _fail("source_universe_mismatch")

    commit = parsed.authorized_implementation_commit_sha
    commit_type = _git(root_absolute, "cat-file", "-t", commit, check=False)
    if commit_type.returncode != 0 or commit_type.stdout.strip() != b"commit":
        _fail("commit_missing")
    ancestor = _git(
        root_absolute,
        "merge-base",
        "--is-ancestor",
        commit,
        checked_head,
        check=False,
    )
    if ancestor.returncode != 0:
        _fail("commit_not_ancestor")
    actual_tree = _git_text(root_absolute, "show", "-s", "--format=%T", commit)
    if not hmac.compare_digest(actual_tree, parsed.authorized_implementation_tree_sha):
        _fail("tree_mismatch")

    if _tree_mode(root_absolute, commit, manifest_relative) is not None:
        _fail("manifest_self_authorizing")
    manifest_head_mode = _tree_mode(root_absolute, checked_head, manifest_relative)
    if manifest_head_mode != "100644":
        _fail("manifest_not_committed")
    if _scoped_dirty(root_absolute, (manifest_relative,)):
        _fail("manifest_dirty")
    try:
        manifest_head = _commit_blob(root_absolute, checked_head, manifest_relative)
    except NormalLiveSourceAuthorizationError:
        _fail("manifest_not_committed")
    if not hmac.compare_digest(manifest_head, raw):
        _fail("manifest_dirty")

    if _scoped_dirty(root_absolute, paths):
        _fail("authorized_path_dirty")
    authorized_entries = _tree_entries(root_absolute, commit, paths)
    checked_entries = _tree_entries(root_absolute, checked_head, paths)
    checkout_attributes = _deterministic_checkout_attributes(
        root_absolute, paths
    )
    authorized_blobs = _batch_commit_blobs(
        root_absolute, authorized_entries, paths
    )
    for expected, source in zip(paths, parsed.source_files, strict=True):
        mode, object_id, size = authorized_entries[expected]
        checked_mode, checked_object_id, checked_size = checked_entries[expected]
        if checked_mode != mode:
            _fail("source_mode_mismatch")
        if checked_object_id != object_id or checked_size != size:
            _fail("source_digest_mismatch")
        authorized_bytes = authorized_blobs[expected]
        if not hmac.compare_digest(_sha256(authorized_bytes), source.sha256):
            _fail("source_digest_mismatch")
        current = root_absolute.joinpath(*expected.split("/"))
        _ensure_regular_unredirected(
            current, "source_file_missing", repository_root=root_absolute
        )
        try:
            current_bytes = current.read_bytes()
        except OSError:
            _fail("source_file_missing")
        expected_checkout_bytes = _materialize_checkout_bytes(
            authorized_bytes, checkout_attributes[expected]
        )
        if not hmac.compare_digest(current_bytes, expected_checkout_bytes):
            _fail("source_digest_mismatch")

    computed_source_digest = _source_set_digest(parsed)
    if not hmac.compare_digest(computed_source_digest, parsed.source_set_digest):
        _fail("source_set_digest_mismatch")
    computed_authorization_id = _authorization_id(parsed)
    if not hmac.compare_digest(computed_authorization_id, parsed.authorization_id):
        _fail("authorization_id_mismatch")

    commit_line = _git_text(
        root_absolute,
        "rev-list",
        "--parents",
        "-n",
        "1",
        checked_head,
    ).split()
    if commit_line != [checked_head, commit]:
        _fail("authorization_commit_not_artifact_only")

    artifact_delta = _git(
        root_absolute,
        "diff",
        "--name-only",
        "-z",
        commit,
        checked_head,
        "--",
    ).stdout
    try:
        delta_paths = tuple(
            item.decode("utf-8", errors="strict")
            for item in artifact_delta.split(b"\0")
            if item
        )
    except UnicodeDecodeError:
        _fail("authorization_commit_not_artifact_only")
    if delta_paths != (manifest_relative,):
        _fail("authorization_commit_not_artifact_only")

    whole_status = _git(
        root_absolute,
        "status",
        "--porcelain=v2",
        "-z",
        "--untracked-files=all",
        "--",
    ).stdout
    if whole_status:
        _fail("repository_dirty")
    _reject_ignored_executable_shadows(root_absolute)
    _reject_authorized_bytecode_caches(root_absolute, paths)
    if not hmac.compare_digest(
        _git_text(root_absolute, "rev-parse", "--verify", "HEAD^{commit}"),
        checked_head,
    ):
        _fail("repository_head_changed")

    return VerifiedNormalLiveSourceAuthorizationV1(
        authorization_id=parsed.authorization_id,
        source_set_digest=parsed.source_set_digest,
        authorized_implementation_commit_sha=commit,
        authorized_implementation_tree_sha=parsed.authorized_implementation_tree_sha,
        runtime_identity=parsed.runtime_identity,
    )


def verify_production_normal_live_source_authorization_v1(
) -> VerifiedNormalLiveSourceAuthorizationV1:
    """Verify the fixed production artifact, with no runtime override surface."""

    return verify_normal_live_source_authorization_v1(
        repository_root=REPOSITORY_ROOT,
        manifest_path=REPOSITORY_ROOT / PRODUCTION_MANIFEST_RELATIVE_PATH,
        expected_source_paths=NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1,
    )


__all__ = [
    "AUTHORIZATION_ID_PREFIX",
    "NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1",
    "OPERATOR_AUTHORIZATION_STATEMENT_V1",
    "NormalLiveSourceAuthorizationError",
    "NormalLiveSourceAuthorizationV1",
    "VerifiedNormalLiveSourceAuthorizationV1",
    "build_normal_live_source_authorization_v1",
    "verify_normal_live_source_authorization_v1",
    "verify_production_normal_live_source_authorization_v1",
]
