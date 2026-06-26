"""
Research Phase R1 — external-ground-truth baseline harness runner (offline).

Demonstrates the measurement instrument: it scores answerers by EXTERNAL truth
(no LLM judge), detects self-consistency gains AND their compute cost, computes
calibration (ECE), and shows the mock CED council scoring ~chance on verifiable
tasks — which proves the harness is NON-CIRCULAR. It makes NO claim about CED
capability (that requires real models via the 9A/9B seam).

Run:

    python -m backend.evaluation.run_baseline_eval
"""

from __future__ import annotations

from typing import List

from backend.evaluation.baseline_harness import (
    DISCLAIMER, Answerer, CouncilAnswerer, OracleAnswerer, SelfConsistencyAnswerer,
    compare, load_verifiable_tasks, run_benchmark,
)

_W = 78


def _mock_council() -> CouncilAnswerer:
    from backend.dialogues.providers import FakeProvider
    from backend.dialogues.agent import SocraticAgent
    from backend.dialogues.ced import CEDOrchestrator
    from backend.dialogues.provider_registry import CouncilProviderRegistry, ScriptedMockProvider
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    registry.register(ScriptedMockProvider("m_a"))
    registry.register(ScriptedMockProvider("m_b"))
    return CouncilAnswerer(CEDOrchestrator(agents, provider, registry=registry))


def render_report() -> str:
    tasks = load_verifiable_tasks()
    out: List[str] = []
    out.append("=" * _W)
    out.append("  RESEARCH R1 — EXTERNAL-GROUND-TRUTH BASELINE HARNESS (OFFLINE)")
    out.append("  External truth, NOT CED's own scorer  →  circularity broken")
    out.append("=" * _W)
    out.append(f"  verifiable tasks: {len(tasks)} (synthetic, numeric ground truth)")
    out.append("")

    # Matched-compute baseline ladder (controllable stand-ins for instrument validation).
    base = OracleAnswerer(error_rate=0.4, seed="single", name="single_model(stub, err=0.40)")
    answerers: List[Answerer] = [
        OracleAnswerer(0.0, name="oracle(perfect)"),
        base,
        SelfConsistencyAnswerer(base, k=5),
        _mock_council(),
    ]

    out.append("  QUALITY vs COST (accuracy is meaningless without its compute cost):")
    out.append(f"    {'answerer':<34}{'acc':>7}{'ECE':>7}{'cost/task':>11}{'qual/cost':>11}")
    out.append("    " + "-" * (34 + 7 + 7 + 11 + 11))
    for row in compare(answerers, tasks):
        out.append(f"    {row.answerer:<34}{row.accuracy:>7}{row.ece:>7}"
                   f"{row.cost_per_task:>11}{row.quality_per_cost:>11}")
    out.append("")

    # The non-circularity proof, stated explicitly.
    council_rep = run_benchmark(_mock_council(), tasks[:8])
    out.append("  NON-CIRCULARITY CHECK:")
    out.append(f"    The MOCK council is rated 'ratified' by CED's own scorer, yet scores")
    out.append(f"    accuracy={council_rep.accuracy} on EXTERNAL truth (cost ~{council_rep.cost_per_task} moves/task).")
    out.append(f"    → the harness measures real correctness, not CED internals. BY DESIGN.")
    out.append("")
    out.append("  " + DISCLAIMER)
    out.append("=" * _W)
    out.append("  Done. Offline / mock only — no real API calls, no keys, no .env.")
    out.append("=" * _W)
    return "\n".join(out)


def main() -> int:
    print(render_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
