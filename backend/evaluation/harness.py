"""CED Evaluation Harness v0.1 -- scripted mode runner.

Drives the REAL CED machinery (claim extraction, Elenchus target selection,
revision, Current Best Explanation) over fixed scripted cases, then scores it
with deterministic metrics. Performs NO live model calls: the session's manager
is a ScriptedModel and the async dialogue pipeline is never invoked.

HARNESS_DISCLAIMER (constraint C): the scores here are a deterministic
regression / baseline signal over scripted cases. They do NOT establish that
CED is globally better; they report whether CED improved on each scripted case
according to these deterministic metrics.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import List

from socrates_ai import DialogConfig, DialogMode, DialogSpeed, SummaryMode
from backend.orchestrator.session import EnhancedDialogSession
from backend.orchestrator.live_epistemics import (
    ensure_live_epistemics,
    record_epistemic_claim,
    apply_elenchus_to_claim,
    apply_revision_to_claim,
    produce_current_best_explanation,
)
from backend.reasoning.claim_targeting import select_elenchus_target
from backend.reasoning.socratic_pressure import evaluate_answer_pressure

from backend.evaluation import HARNESS_VERSION
from backend.evaluation.scripted_model import ScriptedModel
from backend.evaluation.benchmark_cases import (
    SCHEMA_VERSION,
    BenchmarkCase,
    load_benchmark,
)
from backend.evaluation import metrics as M

HARNESS_DISCLAIMER = (
    "run_score is a deterministic regression/baseline metric over scripted cases. "
    "It does NOT prove CED is globally better; it reports whether CED improved on "
    "each scripted case according to these deterministic metrics."
)

# The final answer is scored at the strictest gate (final_gate / round 5).
_FINAL_GATE_ROUND = 5


def _build_session(case: BenchmarkCase):
    cfg = DialogConfig(
        topic=case.question,
        rounds=case.rounds,
        mode=DialogMode.SOCRATIC,
        speed=DialogSpeed.NORMAL,
        summary_mode=SummaryMode.NONE,
    )
    session = EnhancedDialogSession(
        f"eval_{case.id}", cfg, {"claude": "x", "chatgpt": "y"}
    )
    # Non-live model stand-in; never called in v0.1 (engine is driven directly).
    session.manager = ScriptedModel({case.question: case.single_shot_answer})
    session.enforced_rounds = case.rounds
    ensure_live_epistemics(session)
    return session


def _practical_answer_text(cbe_dict: dict) -> str:
    practical = cbe_dict.get("practical_answer", {}) or {}
    return " ".join(
        str(practical.get(key, ""))
        for key in (
            "direct_answer",
            "plain_explanation",
            "practical_example",
            "strongest_objection",
            "uncertainty",
        )
    )


def run_case(case: BenchmarkCase) -> M.CaseResult:
    session = _build_session(case)
    graph = session.epistemic_graph

    # 1. Feed answer turns as claims (exercises claim extraction).
    for turn in case.answer_turns():
        record_epistemic_claim(session, turn.model, turn.content, turn.round)
    stored_texts = [c.text for c in graph.claims.values()]
    claim_extraction = M.score_claim_extraction(case.gold, stored_texts)

    # 2. Elenchus target selection.
    selection = select_elenchus_target(session, case.rounds)
    elenchus_target = M.score_elenchus_target(case.gold, selection)

    target_id = selection.claim_id
    pre_text = graph.claims[target_id].text if target_id in graph.claims else ""
    pre_report = evaluate_answer_pressure(case.question, pre_text, _FINAL_GATE_ROUND)

    # 3. Apply Elenchus + revision to the targeted claim.
    revision_text = case.revision_text()
    if target_id and target_id in graph.claims:
        elenchus = SimpleNamespace(
            target_claim_id=target_id,
            challenger_model="grok",
            round=case.rounds,
            falsification_successful=True,
            challenged_assumptions=["assumes the premise holds"],
            logic_gaps=[],
            evidence_issues=[],
            conclusion_issues=[],
        )
        apply_elenchus_to_claim(session, elenchus)
        if revision_text:
            apply_revision_to_claim(session, target_id, revision_text, actor="claude")

    post_text = graph.claims[target_id].text if target_id in graph.claims else pre_text
    post_report = evaluate_answer_pressure(case.question, post_text, _FINAL_GATE_ROUND)
    revision_detail = M.score_revision_usefulness(
        case.gold, pre_report, post_report, post_text
    )

    # 4. Current Best Explanation.
    cbe_dict = produce_current_best_explanation(session).to_dict()
    cbe_quality = M.score_cbe_quality(case.gold, cbe_dict)

    # 5. Single-shot vs CED final answer (same deterministic scorer).
    ss_report = evaluate_answer_pressure(case.question, case.single_shot_answer, _FINAL_GATE_ROUND)
    ced_report = evaluate_answer_pressure(case.question, _practical_answer_text(cbe_dict), _FINAL_GATE_ROUND)
    ss_vs_ced = M.score_single_shot_vs_ced(ss_report, ced_report)

    run_score = M.case_run_score(
        claim_extraction,
        elenchus_target,
        revision_detail["score"],
        ss_vs_ced["score"],
        cbe_quality,
    )

    return M.CaseResult(
        case_id=case.id,
        claim_extraction=claim_extraction,
        elenchus_target=elenchus_target,
        revision_usefulness=revision_detail["score"],
        revision_detail=revision_detail,
        single_shot_vs_ced=ss_vs_ced,
        cbe_quality=cbe_quality,
        run_score=run_score,
    )


def run_benchmark(cases: List[BenchmarkCase] | None = None) -> M.RunReport:
    cases = cases if cases is not None else load_benchmark()
    results = [run_case(c) for c in cases]
    aggregate = (
        round(sum(r.run_score for r in results) / len(results), 3) if results else 0.0
    )
    return M.RunReport(
        harness_version=HARNESS_VERSION,
        schema_version=SCHEMA_VERSION,
        case_count=len(results),
        aggregate_run_score=aggregate,
        cases=[r.to_dict() for r in results],
        disclaimer=HARNESS_DISCLAIMER,
    )
