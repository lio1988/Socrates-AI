from __future__ import annotations

import json
import os
import py_compile
import stat
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest

from backend.dialogues.socrates_zero.contracts import canonical_json
from socrates.source_authorization import OPERATOR_AUTHORIZATION_STATEMENT_V1


def _git(repository: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", message)
    return _git(repository, "rev-parse", "HEAD")


def _repository(
    tmp_path: Path,
    *,
    attributes: str = "runtime/core.py text eol=lf\nweb/app.js text eol=lf\n",
) -> tuple[Path, tuple[str, ...], str, str]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.email", "normal-live-test@example.invalid")
    _git(repository, "config", "user.name", "Normal Live Test")
    (repository / ".gitattributes").write_text(
        attributes,
        encoding="utf-8",
        newline="\n",
    )
    paths = ("runtime/core.py", "web/app.js")
    for relative, content in (
        (paths[0], "VALUE = 1\n"),
        (paths[1], "export const mode = 'normal-live';\n"),
    ):
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    commit = _commit(repository, "implementation B")
    tree = _git(repository, "show", "-s", "--format=%T", commit)
    return repository, paths, commit, tree


def _authorization_state(tmp_path: Path):
    from socrates.source_authorization import (
        build_normal_live_source_authorization_v1,
    )

    repository, paths, commit, tree = _repository(tmp_path)
    manifest = build_normal_live_source_authorization_v1(
        repository_root=repository,
        authorized_implementation_commit_sha=commit,
        authorized_implementation_tree_sha=tree,
        expected_source_paths=paths,
        operator_statement=OPERATOR_AUTHORIZATION_STATEMENT_V1,
        created_at_utc="2026-09-01T00:00:00Z",
    )
    manifest_path = repository / "authorization" / "normal-live-v1.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        canonical_json(manifest.model_dump(mode="json")),
        encoding="utf-8",
        newline="\n",
    )
    manifest_commit = _commit(repository, "artifact-only C")
    return repository, paths, commit, tree, manifest, manifest_path, manifest_commit


def _write_payload(repository: Path, manifest_path: Path, payload: dict) -> None:
    manifest_path.write_text(
        canonical_json(payload), encoding="utf-8", newline="\n"
    )
    _commit(repository, "alter authorization artifact")


def test_two_commit_authorization_verifies_exact_implementation(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, commit, tree, manifest, manifest_path, manifest_commit = (
        _authorization_state(tmp_path)
    )
    verified = verify_normal_live_source_authorization_v1(
        repository_root=repository,
        manifest_path=manifest_path,
        expected_source_paths=paths,
    )

    assert manifest_commit != commit
    assert verified.authorization_id == manifest.authorization_id
    assert verified.source_set_digest == manifest.source_set_digest
    assert verified.authorized_implementation_commit_sha == commit
    assert verified.authorized_implementation_tree_sha == tree
    assert verified.runtime_identity == "normal-socrates-browser-runtime/v1"


def test_missing_production_manifest_fails_closed(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, _commit_sha, _tree = _repository(tmp_path)
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=repository / "authorization" / "missing.json",
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_absent"


def test_oversized_manifest_is_rejected_before_unbounded_read(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _manifest_commit = (
        _authorization_state(tmp_path)
    )
    manifest_path.write_bytes(b"x" * (4 * 1024 * 1024 + 1))
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_invalid"


@pytest.mark.parametrize("mutation", ["working", "staged"])
def test_working_tree_mutation_of_authorized_source_fails(
    tmp_path: Path, mutation: str
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _manifest_commit = (
        _authorization_state(tmp_path)
    )
    target = repository / paths[0]
    changed = bytearray(target.read_bytes())
    changed[0] ^= 1
    target.write_bytes(changed)
    if mutation == "staged":
        _git(repository, "add", "--", paths[0])

    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code in {"authorized_path_dirty", "source_digest_mismatch"}


def test_missing_authorized_file_fails(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _manifest_commit = (
        _authorization_state(tmp_path)
    )
    (repository / paths[0]).unlink()
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code in {"authorized_path_dirty", "source_file_missing"}


def test_manifest_cannot_select_a_smaller_or_extra_universe(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        build_normal_live_source_authorization_v1,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, commit, tree, _manifest, manifest_path, _manifest_commit = (
        _authorization_state(tmp_path)
    )
    for chosen in ((paths[0],), tuple(sorted((*paths, "other.py")))):
        if "other.py" in chosen:
            (repository / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
            _commit(repository, "unrelated source")
            commit = _git(repository, "rev-parse", "HEAD")
            tree = _git(repository, "show", "-s", "--format=%T", commit)
        replacement = build_normal_live_source_authorization_v1(
            repository_root=repository,
            authorized_implementation_commit_sha=commit,
            authorized_implementation_tree_sha=tree,
            expected_source_paths=chosen,
            operator_statement=OPERATOR_AUTHORIZATION_STATEMENT_V1,
            created_at_utc="2026-09-01T00:00:00Z",
        )
        _write_payload(repository, manifest_path, replacement.model_dump(mode="json"))
        with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
            verify_normal_live_source_authorization_v1(
                repository_root=repository,
                manifest_path=manifest_path,
                expected_source_paths=paths,
            )
        assert raised.value.code == "source_universe_mismatch"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("authorized_implementation_commit_sha", "f" * 40, "commit_missing"),
        ("authorized_implementation_tree_sha", "e" * 40, "tree_mismatch"),
        ("source_set_digest", "d" * 64, "source_set_digest_mismatch"),
        (
            "authorization_id",
            "normallivesourceauthv1_" + "c" * 64,
            "authorization_id_mismatch",
        ),
    ),
)
def test_wrong_authority_identity_fails(
    tmp_path: Path, field: str, value: str, code: str
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, _authorized_commit, _tree, manifest, manifest_path, _manifest_commit = (
        _authorization_state(tmp_path)
    )
    payload = manifest.model_dump(mode="json")
    payload[field] = value
    _write_payload(repository, manifest_path, payload)
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == code


@pytest.mark.parametrize(
    "invalid_path",
    (
        "../escape.py",
        "/absolute.py",
        "C:/absolute.py",
        "web\\app.js",
        "./app.py",
        "web/app.js\nother.py",
        "web/app.js\tother.py",
    ),
)
def test_non_normalized_manifest_paths_are_refused(
    tmp_path: Path, invalid_path: str
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, _commit, _tree, manifest, manifest_path, _manifest_commit = (
        _authorization_state(tmp_path)
    )
    payload = manifest.model_dump(mode="json")
    payload["source_files"][0]["path"] = invalid_path
    _write_payload(repository, manifest_path, payload)
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code in {
        "manifest_invalid",
        "source_path_invalid",
        "source_set_digest_mismatch",
    }


def test_unknown_and_duplicate_json_fields_are_refused(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, _authorized_commit, _tree, manifest, manifest_path, _manifest_commit = (
        _authorization_state(tmp_path)
    )
    payload = manifest.model_dump(mode="json")
    payload["unexpected"] = "not-authority"
    _write_payload(repository, manifest_path, payload)
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_invalid"

    raw = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        raw[:-1] + ',"schema_version":"normal-live-source-set/v1"}',
        encoding="utf-8",
    )
    _commit(repository, "duplicate manifest key")
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_invalid"


def test_symlink_substitution_is_refused_where_supported(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _manifest_commit = (
        _authorization_state(tmp_path)
    )
    target = repository / paths[0]
    external = tmp_path / "external.py"
    external.write_bytes(target.read_bytes())
    target.unlink()
    try:
        os.symlink(external, target)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem does not permit a test symlink")
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code in {"authorized_path_dirty", "source_path_redirected"}


def test_indeterminate_ancestor_metadata_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    import socrates.source_authorization as source_authorization

    repository = tmp_path / "repository"
    target = repository / "runtime" / "core.py"
    target.parent.mkdir(parents=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")
    real_lstat = source_authorization.os.lstat

    def guarded_lstat(path):
        if Path(path) == target.parent:
            raise PermissionError("test-only inaccessible ancestor")
        return real_lstat(path)

    monkeypatch.setattr(source_authorization.os, "lstat", guarded_lstat)
    with pytest.raises(
        source_authorization.NormalLiveSourceAuthorizationError
    ) as raised:
        source_authorization._ensure_regular_unredirected(
            target,
            "source_file_missing",
            repository_root=repository,
        )
    assert raised.value.code == "source_path_redirected"


def test_fixed_production_universe_is_sorted_unique_and_material() -> None:
    from socrates.source_authorization import (
        NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1,
        REPOSITORY_ROOT,
        _deterministic_checkout_attributes,
    )

    assert tuple(sorted(NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1)) == (
        NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1
    )
    assert len(set(NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1)) == len(
        NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1
    )
    assert len(NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1) == 98
    for source_path in NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1:
        assert (REPOSITORY_ROOT / source_path).is_file()
    assert set(
        _deterministic_checkout_attributes(
            REPOSITORY_ROOT, NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1
        )
    ) == set(NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1)
    for required in (
        ".gitattributes",
        "socrates/runtime.py",
        "socrates/source_authorization.py",
        "backend/dialogues/ced.py",
        "backend/dialogues/normal_live.py",
        "backend/api/routes_council.py",
        "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs/hard_logic_live_test_collection_v1.json",
        "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs/q1_gemini_3_7_flash_endpoints_v1.json",
        "docs/branches/feature-socrates-zero-openrouter-one-live-shadow-v1/evidence/s7c_model_endpoints_response_v1.json",
        "web/app.js",
        "web/ced-bridge.js",
        "web/index.html",
        "web/styles.css",
    ):
        assert required in NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1


def test_current_98_path_universe_round_trips_in_a_fresh_checkout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import socrates.source_authorization as source_authorization

    from socrates.source_authorization import (
        NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1,
        REPOSITORY_ROOT,
        build_normal_live_source_authorization_v1,
        verify_normal_live_source_authorization_v1,
    )

    repository = tmp_path / "implementation"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.email", "normal-live-test@example.invalid")
    _git(repository, "config", "user.name", "Normal Live Test")
    for relative in NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1:
        source = REPOSITORY_ROOT.joinpath(*relative.split("/"))
        target = repository.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    commit = _commit(repository, "implementation B with full source universe")
    tree = _git(repository, "show", "-s", "--format=%T", commit)
    manifest = build_normal_live_source_authorization_v1(
        repository_root=repository,
        authorized_implementation_commit_sha=commit,
        authorized_implementation_tree_sha=tree,
        expected_source_paths=NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1,
        operator_statement=OPERATOR_AUTHORIZATION_STATEMENT_V1,
        created_at_utc="2026-09-01T00:00:00Z",
    )
    manifest_path = repository / "authorization" / "normal-live-source-set-v1.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        canonical_json(manifest.model_dump(mode="json")),
        encoding="utf-8",
        newline="\n",
    )
    _commit(repository, "artifact-only C")

    fresh = tmp_path / "fresh-checkout"
    _git(tmp_path, "clone", "--quiet", str(repository), str(fresh))
    real_git = source_authorization._git
    git_calls = 0

    def counted_git(*args, **kwargs):
        nonlocal git_calls
        git_calls += 1
        return real_git(*args, **kwargs)

    monkeypatch.setattr(source_authorization, "_git", counted_git)
    verified = verify_normal_live_source_authorization_v1(
        repository_root=fresh,
        manifest_path=fresh / manifest_path.relative_to(repository),
        expected_source_paths=NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1,
    )
    assert len(NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1) == 98
    assert git_calls <= 24
    assert verified.authorization_id == manifest.authorization_id


def test_unspecified_checkout_eol_policy_fails_closed(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        build_normal_live_source_authorization_v1,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, commit, tree = _repository(tmp_path, attributes="")
    manifest = build_normal_live_source_authorization_v1(
        repository_root=repository,
        authorized_implementation_commit_sha=commit,
        authorized_implementation_tree_sha=tree,
        expected_source_paths=paths,
        operator_statement=OPERATOR_AUTHORIZATION_STATEMENT_V1,
        created_at_utc="2026-09-01T00:00:00Z",
    )
    manifest_path = repository / "authorization" / "normal-live-v1.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        canonical_json(manifest.model_dump(mode="json")),
        encoding="utf-8",
        newline="\n",
    )
    _commit(repository, "artifact-only C")

    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "checkout_filter_unsupported"


def test_batched_tree_and_blob_parsers_are_strict_and_bounded() -> None:
    import socrates.source_authorization as source_authorization

    object_id = "a" * 40
    path = "runtime/core.py"
    tree_record = f"100644 blob {object_id} 3\t{path}\0".encode()
    assert source_authorization._parse_tree_entries(tree_record, (path,)) == {
        path: ("100644", object_id, 3)
    }
    blob_record = f"{object_id} blob 3\n".encode() + b"abc\n"
    assert source_authorization._parse_batch_blobs(
        blob_record, ((path, object_id, 3),)
    ) == {path: b"abc"}

    malformed_trees = (
        b"",
        tree_record + tree_record,
        f"100644 tree {object_id} 3\t{path}\0".encode(),
        f"100644 blob {object_id} 16777217\t{path}\0".encode(),
    )
    for raw in malformed_trees:
        with pytest.raises(source_authorization.NormalLiveSourceAuthorizationError):
            source_authorization._parse_tree_entries(raw, (path,))

    malformed_blobs = (
        b"",
        f"{'b' * 40} blob 3\nabc\n".encode(),
        f"{object_id} tree 3\nabc\n".encode(),
        f"{object_id} blob 4\nabc\n".encode(),
        blob_record + b"trailing",
    )
    for raw in malformed_blobs:
        with pytest.raises(source_authorization.NormalLiveSourceAuthorizationError):
            source_authorization._parse_batch_blobs(
                raw, ((path, object_id, 3),)
            )

    aggregate_paths = tuple(f"runtime/file-{index}.py" for index in range(5))
    aggregate_tree = b"".join(
        f"100644 blob {index:040x} 16777216\t{aggregate_path}\0".encode()
        for index, aggregate_path in enumerate(aggregate_paths, start=1)
    )
    with pytest.raises(source_authorization.NormalLiveSourceAuthorizationError) as raised:
        source_authorization._parse_tree_entries(
            aggregate_tree, aggregate_paths
        )
    assert raised.value.code == "source_set_too_large"


def test_text_checkout_materialization_rejects_noncanonical_blob_bytes() -> None:
    import socrates.source_authorization as source_authorization

    assert source_authorization._materialize_checkout_bytes(
        b"line one\nline two\n", ("set", "crlf")
    ) == b"line one\r\nline two\r\n"
    assert source_authorization._materialize_checkout_bytes(
        b"binary\r\nbytes", ("unset", "unspecified")
    ) == b"binary\r\nbytes"
    for invalid in (b"text\r\n", b"text\0payload"):
        with pytest.raises(source_authorization.NormalLiveSourceAuthorizationError):
            source_authorization._materialize_checkout_bytes(
                invalid, ("set", "lf")
            )


def test_operator_statement_is_fixed_affirmative_authority(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, _commit_sha, _tree, manifest, manifest_path, _head = (
        _authorization_state(tmp_path)
    )
    payload = manifest.model_dump(mode="json")
    payload["operator_authorization_statement"] = "NO"
    _write_payload(repository, manifest_path, payload)
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_invalid"


def test_wrong_per_file_digest_and_duplicate_path_fail(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, _commit_sha, _tree, manifest, manifest_path, _head = (
        _authorization_state(tmp_path)
    )
    wrong_digest = manifest.model_dump(mode="json")
    wrong_digest["source_files"][0]["sha256"] = "f" * 64
    _write_payload(repository, manifest_path, wrong_digest)
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "source_digest_mismatch"

    duplicate = manifest.model_dump(mode="json")
    duplicate["source_files"][1] = dict(duplicate["source_files"][0])
    _write_payload(repository, manifest_path, duplicate)
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "source_universe_mismatch"


@pytest.mark.parametrize("staged", (False, True))
def test_clean_committed_manifest_cannot_be_substituted(
    tmp_path: Path, staged: bool
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        build_normal_live_source_authorization_v1,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, commit, tree, _manifest, manifest_path, _head = (
        _authorization_state(tmp_path)
    )
    replacement = build_normal_live_source_authorization_v1(
        repository_root=repository,
        authorized_implementation_commit_sha=commit,
        authorized_implementation_tree_sha=tree,
        expected_source_paths=paths,
        operator_statement=OPERATOR_AUTHORIZATION_STATEMENT_V1,
        created_at_utc="2026-09-01T00:00:01Z",
    )
    manifest_path.write_text(
        canonical_json(replacement.model_dump(mode="json")), encoding="utf-8"
    )
    if staged:
        _git(repository, "add", "--", manifest_path.relative_to(repository).as_posix())
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_dirty"


def test_authorized_commit_must_be_ancestor_and_cannot_contain_manifest(
    tmp_path: Path,
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        build_normal_live_source_authorization_v1,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, _commit_sha, _tree, _manifest, manifest_path, head = (
        _authorization_state(tmp_path)
    )
    head_tree = _git(repository, "show", "-s", "--format=%T", head)
    self_containing = build_normal_live_source_authorization_v1(
        repository_root=repository,
        authorized_implementation_commit_sha=head,
        authorized_implementation_tree_sha=head_tree,
        expected_source_paths=paths,
        operator_statement=OPERATOR_AUTHORIZATION_STATEMENT_V1,
        created_at_utc="2026-09-01T00:00:01Z",
    )
    _write_payload(repository, manifest_path, self_containing.model_dump(mode="json"))
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_self_authorizing"

    source_tree = _git(repository, "show", "-s", "--format=%T", head)
    orphan = _git(repository, "commit-tree", source_tree, "-m", "unrelated B")
    unrelated = build_normal_live_source_authorization_v1(
        repository_root=repository,
        authorized_implementation_commit_sha=orphan,
        authorized_implementation_tree_sha=source_tree,
        expected_source_paths=paths,
        operator_statement=OPERATOR_AUTHORIZATION_STATEMENT_V1,
        created_at_utc="2026-09-01T00:00:02Z",
    )
    _write_payload(repository, manifest_path, unrelated.model_dump(mode="json"))
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "commit_not_ancestor"


@pytest.mark.parametrize("drift", ("content", "mode"))
def test_clean_descendant_source_drift_after_b_fails(
    tmp_path: Path, drift: str
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    if drift == "content":
        target = repository / paths[0]
        changed = bytearray(target.read_bytes())
        changed[-1] ^= 1
        target.write_bytes(changed)
        _commit(repository, "clean committed content drift")
    else:
        _git(repository, "update-index", "--chmod=+x", "--", paths[0])
        _git(repository, "commit", "-m", "clean committed mode drift")

    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code in {"source_digest_mismatch", "source_mode_mismatch"}


@pytest.mark.parametrize("state", ("untracked", "committed"))
def test_extra_shadowing_source_after_b_fails_closed(
    tmp_path: Path, state: str
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    shadow = repository / (
        "pydantic.py" if state == "untracked" else "sitecustomize.py"
    )
    shadow.write_text("raise RuntimeError('shadow executed')\n", encoding="utf-8")
    if state == "committed":
        _commit(repository, "forbidden executable descendant")

    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == (
        "repository_dirty"
        if state == "untracked"
        else "authorization_commit_not_artifact_only"
    )


def test_ignored_startup_shadow_fails_closed(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    exclude = repository / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("\n/sitecustomize.py\n")
    (repository / "sitecustomize.py").write_text(
        "raise RuntimeError('ignored startup shadow')\n", encoding="utf-8"
    )

    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "ignored_executable_shadow"


def test_ignored_extensionless_redirect_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    import socrates.source_authorization as source_authorization

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    shadow = repository / "pydantic"
    shadow.write_text("ignored extensionless shadow\n", encoding="utf-8")
    exclude = repository / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("\n/pydantic\n")
    real_lstat = source_authorization.os.lstat

    def redirected_lstat(path):
        if Path(path) == shadow:
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
        return real_lstat(path)

    monkeypatch.setattr(source_authorization.os, "lstat", redirected_lstat)
    with pytest.raises(
        source_authorization.NormalLiveSourceAuthorizationError
    ) as raised:
        source_authorization.verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "ignored_executable_shadow"


def test_successful_git_warning_fails_closed(tmp_path: Path, monkeypatch) -> None:
    import socrates.source_authorization as source_authorization

    repository, _paths, _commit_sha, _tree = _repository(tmp_path)
    real_run = source_authorization.subprocess.run

    def warning_run(*args, **kwargs):
        completed = real_run(*args, **kwargs)
        if completed.returncode == 0:
            return subprocess.CompletedProcess(
                args=completed.args,
                returncode=0,
                stdout=completed.stdout,
                stderr=b"warning: skipped unreadable directory\n",
            )
        return completed

    monkeypatch.setattr(source_authorization.subprocess, "run", warning_run)
    with pytest.raises(
        source_authorization.NormalLiveSourceAuthorizationError
    ) as raised:
        source_authorization._git(repository, "status", "--porcelain=v2")
    assert raised.value.code == "git_verification_failed"


def test_git_process_uses_an_absolute_executable_outside_repository(
    tmp_path: Path, monkeypatch
) -> None:
    import socrates.source_authorization as source_authorization

    repository, _paths, _commit_sha, _tree = _repository(tmp_path)
    real_run = source_authorization.subprocess.run
    executable_paths: list[Path] = []

    def capture_run(args, *positional, **kwargs):
        executable_paths.append(Path(args[0]))
        return real_run(args, *positional, **kwargs)

    monkeypatch.setattr(source_authorization.subprocess, "run", capture_run)
    source_authorization._git(repository, "status", "--porcelain=v2")
    assert len(executable_paths) == 1
    executable = executable_paths[0]
    assert executable.is_absolute()
    with pytest.raises(ValueError):
        executable.resolve(strict=True).relative_to(repository.resolve(strict=True))


def test_repository_root_git_shim_is_rejected_before_process_launch(
    tmp_path: Path, monkeypatch
) -> None:
    import socrates.source_authorization as source_authorization

    repository, _paths, _commit_sha, _tree = _repository(tmp_path)
    shim = repository / "git.exe"
    shim.write_bytes(b"not an executable")
    exclude = repository / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("\n/git.exe\n")

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("repository Git shim must never be launched")

    monkeypatch.setattr(source_authorization.subprocess, "run", forbidden_run)
    with pytest.raises(
        source_authorization.NormalLiveSourceAuthorizationError
    ) as raised:
        source_authorization._git(repository, "status", "--porcelain=v2")
    assert raised.value.code == "git_executable_shadow"


def test_ignored_legacy_import_bytecode_fails_closed(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    shadow_source = tmp_path / "pydantic.py"
    shadow_source.write_text("SHADOW = True\n", encoding="utf-8")
    shadow = repository / "pydantic.pyc"
    py_compile.compile(
        str(shadow_source),
        cfile=str(shadow),
        doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )
    exclude = repository / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("\n/pydantic.pyc\n")

    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "ignored_executable_shadow"


def test_ignored_unchecked_hash_cache_for_authorized_source_fails_closed(
    tmp_path: Path,
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    target = repository / paths[0]
    cache = target.parent / "__pycache__" / f"{target.stem}.test.pyc"
    cache.parent.mkdir()
    py_compile.compile(
        str(target),
        cfile=str(cache),
        doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )
    exclude = repository / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("\n__pycache__/\n")

    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "authorized_bytecode_cache_present"


def test_explicit_crlf_checkout_materialization_verifies(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        build_normal_live_source_authorization_v1,
        verify_normal_live_source_authorization_v1,
    )

    repository = tmp_path / "crlf-repository"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.email", "normal-live-test@example.invalid")
    _git(repository, "config", "user.name", "Normal Live Test")
    (repository / ".gitattributes").write_text(
        "*.py text eol=crlf\n", encoding="utf-8", newline="\n"
    )
    target = repository / "runtime" / "core.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8", newline="\n")
    (repository / ".gitattributes").write_text(
        "runtime/core.py text eol=crlf\n",
        encoding="utf-8",
        newline="\n",
    )
    paths = ("runtime/core.py",)
    commit = _commit(repository, "implementation B with CRLF checkout")
    tree = _git(repository, "show", "-s", "--format=%T", commit)
    manifest = build_normal_live_source_authorization_v1(
        repository_root=repository,
        authorized_implementation_commit_sha=commit,
        authorized_implementation_tree_sha=tree,
        expected_source_paths=paths,
        operator_statement=OPERATOR_AUTHORIZATION_STATEMENT_V1,
        created_at_utc="2026-09-01T00:00:00Z",
    )
    manifest_path = repository / "authorization" / "normal-live-v1.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        canonical_json(manifest.model_dump(mode="json")),
        encoding="utf-8",
        newline="\n",
    )
    _commit(repository, "artifact-only C")

    fresh = tmp_path / "fresh-windows-checkout"
    _git(
        tmp_path,
        "-c",
        "core.autocrlf=true",
        "clone",
        "--quiet",
        str(repository),
        str(fresh),
    )
    fresh_target = fresh / paths[0]
    assert b"\r\n" in fresh_target.read_bytes()
    _git(fresh, "config", "core.autocrlf", "true")
    _git(fresh, "update-index", "--refresh")
    assert _git(
        fresh,
        "status",
        "--porcelain=v2",
        "--untracked-files=all",
    ) == ""

    verified = verify_normal_live_source_authorization_v1(
        repository_root=fresh,
        manifest_path=fresh / manifest_path.relative_to(repository),
        expected_source_paths=paths,
    )
    assert verified.authorization_id == manifest.authorization_id


def test_git_info_attribute_override_is_refused(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    attributes = repository / ".git" / "info" / "attributes"
    attributes.write_text(
        "runtime/core.py filter=untrusted\n", encoding="utf-8"
    )
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "attribute_override_present"


def test_head_change_during_verification_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    import socrates.source_authorization as source_authorization

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    real_git_text = source_authorization._git_text
    snapshots = 0

    def changing_git_text(root, *args):
        nonlocal snapshots
        value = real_git_text(root, *args)
        if args == ("rev-parse", "--verify", "HEAD^{commit}"):
            snapshots += 1
            if snapshots == 2:
                return "f" * 40
        return value

    monkeypatch.setattr(source_authorization, "_git_text", changing_git_text)
    with pytest.raises(
        source_authorization.NormalLiveSourceAuthorizationError
    ) as raised:
        source_authorization.verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "repository_head_changed"


def test_second_verification_fails_after_exact_one_byte_mutation(tmp_path: Path) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    verified = verify_normal_live_source_authorization_v1(
        repository_root=repository,
        manifest_path=manifest_path,
        expected_source_paths=paths,
    )
    assert verified.authorization_id
    target = repository / paths[0]
    changed = bytearray(target.read_bytes())
    changed[0] ^= 1
    target.write_bytes(changed)
    with pytest.raises(NormalLiveSourceAuthorizationError):
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )


def test_noncanonical_invalid_utf8_and_nested_unknown_manifest_fail(
    tmp_path: Path,
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, _commit_sha, _tree, manifest, manifest_path, _head = (
        _authorization_state(tmp_path)
    )
    nested = manifest.model_dump(mode="json")
    nested["provenance"]["unexpected"] = "authority"
    _write_payload(repository, manifest_path, nested)
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_invalid"

    manifest_path.write_bytes(b"\xff\xfe")
    _commit(repository, "invalid utf8 manifest")
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_invalid"

    manifest_path.write_text(
        canonical_json(manifest.model_dump(mode="json")) + "\n",
        encoding="utf-8",
    )
    _commit(repository, "noncanonical manifest")
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "manifest_invalid"


def test_authorization_commit_must_be_the_direct_artifact_only_child(
    tmp_path: Path,
) -> None:
    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_normal_live_source_authorization_v1,
    )

    repository, paths, *_rest, manifest_path, _head = _authorization_state(tmp_path)
    _git(repository, "commit", "--allow-empty", "-m", "unexpected descendant")
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_normal_live_source_authorization_v1(
            repository_root=repository,
            manifest_path=manifest_path,
            expected_source_paths=paths,
        )
    assert raised.value.code == "authorization_commit_not_artifact_only"


def test_production_verifier_has_no_override_and_missing_artifact_is_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import inspect
    import socrates.source_authorization as source_authorization

    from socrates.source_authorization import (
        NormalLiveSourceAuthorizationError,
        verify_production_normal_live_source_authorization_v1,
    )

    assert list(
        inspect.signature(
            verify_production_normal_live_source_authorization_v1
        ).parameters
    ) == []
    repository, paths, _commit_sha, _tree = _repository(tmp_path)
    monkeypatch.setattr(source_authorization, "REPOSITORY_ROOT", repository)
    monkeypatch.setattr(
        source_authorization,
        "NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1",
        paths,
    )
    monkeypatch.setattr(
        source_authorization,
        "PRODUCTION_MANIFEST_RELATIVE_PATH",
        "authorization/missing-normal-live-source-set-v1.json",
    )
    with pytest.raises(NormalLiveSourceAuthorizationError) as raised:
        verify_production_normal_live_source_authorization_v1()
    assert raised.value.code == "manifest_absent"
    assert "manifest" not in str(raised.value).lower()
    assert "authorization/" not in repr(raised.value).lower()
