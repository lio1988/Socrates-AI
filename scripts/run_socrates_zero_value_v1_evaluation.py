"""Emit the first authoritative offline Value-v1 primary-gate artifact."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Sequence


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.dialogues.ced_search_value_v1_artifact import (  # noqa: E402
    build_primary_artifact,
    render_primary_artifact,
)


DEFAULT_OUTPUT = (
    _REPO_ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-heuristic-value-v1"
    / "artifacts"
    / "socrateszero_value_v1_primary_v0.json"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen deterministic offline Value-v1 primary gate."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    artifact = build_primary_artifact()
    rendered = render_primary_artifact(artifact)
    replay = build_primary_artifact()
    replay_rendered = render_primary_artifact(replay)
    if replay != artifact or replay.artifact_id != artifact.artifact_id:
        raise RuntimeError("Value-v1 artifact semantic replay mismatch")
    if replay_rendered != rendered:
        raise RuntimeError("Value-v1 artifact byte replay mismatch")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = rendered.encode("utf-8")
    if output.exists() and output.read_bytes() != encoded:
        raise RuntimeError("refusing to overwrite a different Value-v1 artifact")
    output.write_bytes(encoded)
    print(f"artifact_id={artifact.artifact_id}")
    print(f"decision={artifact.primary_decision.decision}")
    print(f"pairs={len(artifact.holdout_run.pair_results)}")
    print(f"sha256={hashlib.sha256(encoded).hexdigest()}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
