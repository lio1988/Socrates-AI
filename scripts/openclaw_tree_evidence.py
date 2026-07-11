"""Recompute strict tree-revision observations from a retained session artifact.

Read-only reporter (step 1 of the Retained Tree Evidence Operator Bridge):

    python scripts/openclaw_tree_evidence.py runs/openclaw_tree_sessions/<id>.tree_session.json

It loads one digest-verified ``openclaw_tree_session_artifact_v1`` file,
recomputes matched parent/child observations through the SAME extractor the
governed evidence layer uses, and writes one versioned report:

    openclaw_tree_evidence_report_v1

The report lists improved / neutral / regressed outcomes per agent with the
exact observation digests a later NAMED attestation may cite.

This command NEVER writes the evidence registry, never creates a proposal,
never touches Identity/Memory/Soul, and never calls a provider.

Options:
    --agent <id>              only report observations for one agent
    --effect-margin <float>   outcome threshold (default 0.5)
    --min-matched-scores <n>  minimum exact matched (judge, section) pairs
    --out <dir>               report directory
                              (default runs/openclaw_tree_evidence)
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_identity import (                      # noqa: E402
    extract_tree_revision_observations,
    summarize_tree_revision_observations,
)
from backend.dialogues.openclaw_identity.tree_revision_schema import (  # noqa: E402
    digest,
)
from backend.dialogues.openclaw_identity.tree_session_retention import (  # noqa: E402
    load_tree_session_artifact,
)

TREE_EVIDENCE_REPORT_VERSION = "openclaw_tree_evidence_report_v1"
_W = 78


def _flag(argv, name, default=""):
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return str(argv[index + 1]).strip()
    return default


def build_tree_evidence_report(
    artifact_path,
    *,
    agent_id: str = "",
    effect_margin: float = 0.5,
    min_matched_scores: int = 1,
):
    """Pure report construction (also the testable seam)."""
    retained = load_tree_session_artifact(artifact_path)
    observations = extract_tree_revision_observations(
        retained.state,
        retained.final,
        effect_margin=effect_margin,
        min_matched_scores=min_matched_scores,
    )
    if agent_id:
        observations = tuple(
            item for item in observations if item.agent_id == agent_id)

    agents = sorted({item.agent_id for item in observations})
    report = {
        "schema_version": TREE_EVIDENCE_REPORT_VERSION,
        "session_id": retained.session_id,
        "artifact": str(artifact_path),
        "parameters": {
            "agent_id": agent_id or None,
            "effect_margin": float(effect_margin),
            "min_matched_scores": int(min_matched_scores),
        },
        "observations": [item.to_record() for item in observations],
        "summaries": {
            agent: summarize_tree_revision_observations(
                [item for item in observations if item.agent_id == agent],
                agent_id=agent,
            )
            for agent in agents
        },
    }
    report["report_digest"] = digest(
        {key: value for key, value in report.items()})
    return report, observations


def main(argv=None, env=None) -> int:
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env

    print("=" * _W)
    print("  OPENCLAW TREE EVIDENCE - read-only recomputation and report")
    print("=" * _W)
    if len(argv) < 2 or argv[1].startswith("--"):
        print("  usage: openclaw_tree_evidence.py <artifact.tree_session.json>")
        print("         [--agent <id>] [--effect-margin 0.5]")
        print("         [--min-matched-scores 1] [--out <dir>]")
        return 1
    try:
        effect_margin = float(_flag(argv, "--effect-margin", "0.5"))
        min_matched = int(_flag(argv, "--min-matched-scores", "1"))
        report, observations = build_tree_evidence_report(
            argv[1],
            agent_id=_flag(argv, "--agent"),
            effect_margin=effect_margin,
            min_matched_scores=min_matched,
        )
    except (ValueError, OSError) as exc:
        print(f"  REFUSED: {exc}")
        print("=" * _W)
        return 1

    out_dir = pathlib.Path(_flag(argv, "--out") or env.get(
        "CED_TREE_EVIDENCE_DIR",
        str(_ROOT / "runs" / "openclaw_tree_evidence")))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (
        f"TREE_EVIDENCE_REPORT_{report['session_id']}.json")
    out_path.write_text(json.dumps(
        report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")

    print(f"  session      : {report['session_id']}")
    print(f"  observations : {len(observations)} "
          f"(effect_margin={effect_margin}, "
          f"min_matched_scores={min_matched})")
    for item in observations:
        print(f"    [{item.outcome:<9}] {item.agent_id} "
              f"margin={item.margin:+.4f} "
              f"matched={item.matched_score_count} "
              f"digest={item.observation_digest[:16]}")
    if not observations:
        print("    (none - no tree, no matched coverage, or filtered agent)")
    print(f"  report       : {out_path}")
    print("-" * _W)
    print("  Nothing was registered, proposed, or changed. A NAMED attestation")
    print("  (scripts/openclaw_attest_tree_evidence.py) may cite the digests")
    print("  above; governance still follows.")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
