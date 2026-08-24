"""Emit the frozen offline SocratesZero Phase 5 benchmark artifact.

This command performs no provider, tool, network, CED orchestration, or
production action call.  Its JSON contains no timestamp or other volatile
field, so an identical repository state replays byte-for-byte.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Sequence


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.dialogues.socrates_zero import (  # noqa: E402
    SearchKernelBenchmarkArtifact,
    run_frozen_matrix,
)


DEFAULT_OUTPUT = (
    _REPO_ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-search-v0"
    / "artifacts"
    / "socrateszero_search_kernel_benchmark_v0.json"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run frozen, deterministic, offline Phase 5 evaluation."
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=DEFAULT_OUTPUT,
        help="destination for the immutable machine-readable JSON artifact",
    )
    return parser


def render_artifact(artifact: SearchKernelBenchmarkArtifact) -> str:
    return json.dumps(
        artifact.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    artifact = run_frozen_matrix()
    rendered = render_artifact(artifact)
    replay = SearchKernelBenchmarkArtifact.model_validate_json(rendered)
    if replay != artifact or replay.artifact_id != artifact.artifact_id:
        raise RuntimeError("serialized benchmark failed semantic replay")

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_text(encoding="utf-8") != rendered:
        raise RuntimeError(
            "refusing to overwrite a different frozen Phase 5 artifact"
        )
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"artifact_id={artifact.artifact_id}")
    print(f"runs={len(artifact.runs)} cases_per_run=20")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
