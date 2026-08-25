"""Emit the frozen offline secondary BestOfN Value-v0/v1 artifact."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Sequence


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.dialogues.ced_search_value_v1_bestofn import (  # noqa: E402
    build_bestofn_artifact,
    render_bestofn_artifact,
)


DEFAULT_OUTPUT = (
    _REPO_ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-heuristic-value-v1"
    / "artifacts"
    / "socrateszero_value_v1_bestofn_v0.json"
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen secondary UniformPolicy BestOfN gate."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_bestofn_artifact()
    rendered = render_bestofn_artifact(artifact)
    replay = build_bestofn_artifact()
    replay_rendered = render_bestofn_artifact(replay)
    if replay != artifact or replay.artifact_id != artifact.artifact_id:
        raise RuntimeError("secondary artifact semantic replay mismatch")
    if replay_rendered != rendered:
        raise RuntimeError("secondary artifact byte replay mismatch")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = rendered.encode("utf-8")
    if output.exists() and output.read_bytes() != encoded:
        raise RuntimeError("refusing to overwrite a different secondary artifact")
    output.write_bytes(encoded)
    print(f"artifact_id={artifact.artifact_id}")
    print(f"decision={artifact.decision.decision}")
    print(f"v0_accuracy={artifact.decision.v0_selection_accuracy}")
    print(f"v1_accuracy={artifact.decision.v1_selection_accuracy}")
    print(f"sha256={hashlib.sha256(encoded).hexdigest()}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
