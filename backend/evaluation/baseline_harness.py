"""
External-ground-truth, matched-compute baseline harness (Research Phase R1).

This is the measurement instrument the research program (`RESEARCH.md`) needs:
it scores any *answerer* against **external, verifiable ground truth** — NOT against
CED's own Socratic scorer — so the central circularity flaw named in this package's
README ("CED scoring CED") cannot inflate a result.

What it provides
----------------
- **Verifiers** (`numeric` / `exact` / `set`) — deterministic, no LLM judge.
- A provider-agnostic **`Answerer`** interface so single-model baselines,
  self-consistency, and the CED council are all scored by the *same* yardstick.
- **Controllable answerers** (`OracleAnswerer`, `SelfConsistencyAnswerer`) used to
  **validate the instrument itself** on inputs with known answers.
- Metrics: **accuracy**, **expected calibration error (ECE)**, **compute cost**
  (model-call-equivalents), and a **quality-vs-cost** comparison (the Pareto view).

Scientific discipline (do not violate)
--------------------------------------
- Offline answerers here are **stand-ins for instrument validation**. Running the
  *mock* CED council on verifiable tasks yields ~chance accuracy **by design**
  (FakeProvider cannot reason) — which is exactly how this proves the harness is
  **non-circular**: external truth, not CED internals.
- **No scientific claim about CED capability may be drawn from mock runs.** A real
  result requires real models via the Phase 9A/9B adapter seam. Every report
  carries that disclaimer.

No live API calls · no keys · no `.env` · no network.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence

SCHEMA_VERSION = "baseline_eval_v0"
DATA_PATH = Path(__file__).resolve().parent / "data" / "verifiable_v0.json"

DISCLAIMER = (
    "External-truth accuracy over a synthetic verifiable set. Offline answerers are "
    "controllable stand-ins for INSTRUMENT VALIDATION. No claim about CED capability "
    "is made here; a scientific result requires real models via the 9A/9B seam."
)


# ── deterministic pseudo-randomness (no RNG state, fully reproducible) ─────────

def _u01(*parts: Any) -> float:
    """A reproducible uniform-in-[0,1) from arbitrary keys (hash-based)."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:13], 16) / float(1 << 52)


# ── tasks + verifiers (external ground truth) ─────────────────────────────────

@dataclass(frozen=True)
class EvalTask:
    task_id: str
    question: str
    gold: str
    verifier: str            # "numeric" | "exact" | "set"
    domain: str = "synthetic"
    difficulty: str = "easy"


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def extract_final_answer(text: str) -> str:
    """Pull a candidate final answer: GSM8K-style '#### x', else 'answer: x',
    else the last number, else the last non-empty line."""
    if not text:
        return ""
    m = re.search(r"####\s*(.+)", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"(?:final answer|answer)\s*[:=]\s*(.+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip().splitlines()[0].strip()
    nums = _NUM_RE.findall(text)
    if nums:
        return nums[-1]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower()).rstrip(".")


def verify_numeric(prediction: str, gold: str, tol: float = 1e-6) -> bool:
    pm = _NUM_RE.findall(prediction or "")
    gm = _NUM_RE.findall(gold or "")
    if not pm or not gm:
        return False
    try:
        return abs(float(pm[-1]) - float(gm[-1])) <= tol
    except ValueError:
        return False


def verify_exact(prediction: str, gold: str) -> bool:
    return _norm(extract_final_answer(prediction)) == _norm(gold)


def verify_set(prediction: str, gold: str) -> bool:
    want = {_norm(x) for x in gold.split("|") if x.strip()}
    got = {_norm(x) for x in re.split(r"[,;|]", prediction or "") if x.strip()}
    return want.issubset(got)


VERIFIERS: Dict[str, Callable[[str, str], bool]] = {
    "numeric": verify_numeric,
    "exact": verify_exact,
    "set": verify_set,
}


def verify(task: EvalTask, prediction: str) -> bool:
    return VERIFIERS[task.verifier](prediction, task.gold)


# ── a small synthetic VERIFIABLE set (for instrument validation only) ─────────

def synthetic_tasks(n: int = 48) -> List[EvalTask]:
    """
    Deterministic arithmetic + simple-logic tasks with objective gold answers.
    This is an INSTRUMENT-VALIDATION set, NOT a benchmark — it exists to prove the
    harness measures real correctness, calibration and cost. Real studies must use
    licensed external datasets (GSM8K/MATH/MMLU-Pro/…) per RESEARCH.md.
    """
    ops = [("+", lambda a, b: a + b), ("-", lambda a, b: a - b), ("*", lambda a, b: a * b)]
    tasks: List[EvalTask] = []
    for i in range(n):
        a = 2 + (i * 7) % 19
        b = 1 + (i * 5) % 13
        sym, fn = ops[i % 3]
        tasks.append(EvalTask(
            task_id=f"arith_{i:03d}",
            question=f"What is {a} {sym} {b}? Give only the number.",
            gold=str(fn(a, b)),
            verifier="numeric",
            difficulty="easy" if i % 3 == 0 else "medium",
        ))
    return tasks


def load_verifiable_tasks(path: Optional[Path] = None) -> List[EvalTask]:
    """Load the on-disk verifiable set; rejects any unexpected schema_version."""
    doc = json.loads(Path(path or DATA_PATH).read_text(encoding="utf-8"))
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"schema_version mismatch: expected {SCHEMA_VERSION!r}, got {doc.get('schema_version')!r}")
    return [EvalTask(**{k: t[k] for k in ("task_id", "question", "gold", "verifier",
                                          "domain", "difficulty") if k in t})
            for t in doc["tasks"]]


# ── answerer contract + result ────────────────────────────────────────────────

@dataclass
class AnswerResult:
    final_answer: str
    raw_text: str = ""
    confidence: float = 0.5          # 0..1, for calibration (ECE)
    cost_units: float = 1.0          # compute proxy: model-call-equivalents
    meta: Dict[str, Any] = field(default_factory=dict)


class Answerer(Protocol):
    name: str
    def answer(self, task: EvalTask) -> AnswerResult: ...


# ── controllable baselines (offline; for instrument validation) ───────────────

class OracleAnswerer:
    """
    A controllable single-model stand-in: returns the gold answer with probability
    (1 - error_rate), else a deterministic wrong answer. Confidence is either
    'calibrated' (= P(correct)) or 'overconfident' (fixed high). One call of cost.
    Deterministic via `seed`. Used to validate accuracy/ECE measurement.
    """
    def __init__(self, error_rate: float = 0.0, seed: str = "o",
                 confidence_mode: str = "calibrated", cost_units: float = 1.0,
                 name: Optional[str] = None) -> None:
        self.error_rate = error_rate
        self.seed = seed
        self.confidence_mode = confidence_mode
        self.cost_units = cost_units
        self.name = name or f"oracle(err={error_rate})"

    def _is_correct(self, task: EvalTask, sample: int = 0) -> bool:
        return _u01(self.seed, sample, task.task_id) >= self.error_rate

    def answer(self, task: EvalTask, _sample: int = 0) -> AnswerResult:
        correct = self._is_correct(task, _sample)
        ans = task.gold if correct else _wrong_answer(task)
        if self.confidence_mode == "overconfident":
            conf = 0.95
        else:
            conf = round(1.0 - self.error_rate, 4)
        return AnswerResult(final_answer=ans, raw_text=ans, confidence=conf,
                            cost_units=self.cost_units,
                            meta={"correct_draw": correct, "sample": _sample})


def _wrong_answer(task: EvalTask) -> str:
    if task.verifier == "numeric":
        nums = _NUM_RE.findall(task.gold)
        if nums:
            base = float(nums[-1])
            off = 1 + int(_u01("wrong", task.task_id) * 5)
            val = base + off
            return str(int(val)) if val == int(val) else str(val)
    return f"not_{task.gold}"


class SelfConsistencyAnswerer:
    """
    B2 — the real competitor: draw `k` samples from a base answerer and take the
    majority vote. Confidence = winning vote share. Cost = k × base cost. This lets
    the harness *detect* ensembling gains (hypothesis H2) and their cost (H3).
    """
    def __init__(self, base: OracleAnswerer, k: int = 5, name: Optional[str] = None) -> None:
        self.base = base
        self.k = k
        self.name = name or f"self_consistency@{k}({base.name})"

    def answer(self, task: EvalTask) -> AnswerResult:
        votes: Dict[str, int] = {}
        cost = 0.0
        for s in range(self.k):
            r = self.base.answer(task, _sample=s)
            votes[r.final_answer] = votes.get(r.final_answer, 0) + 1
            cost += r.cost_units
        winner, count = max(votes.items(), key=lambda kv: (kv[1], kv[0]))
        return AnswerResult(final_answer=winner, raw_text=winner,
                            confidence=round(count / self.k, 4), cost_units=cost,
                            meta={"votes": votes, "k": self.k})


class CouncilAnswerer:
    """
    Wraps the registry-backed CED council as an answerer (system-under-test).
    Extracts a candidate answer from the assembled synthesis and scores it by the
    SAME external verifier. Cost = council move count (compute proxy).

    With mock providers this scores ~chance on verifiable tasks BY DESIGN — that is
    the proof the harness is non-circular. NOTHING about CED capability is implied.
    """
    def __init__(self, orchestrator: Any, name: str = "ced_council(mock)") -> None:
        self.ced = orchestrator
        self.name = name

    def answer(self, task: EvalTask) -> AnswerResult:
        import asyncio
        final = asyncio.run(self.ced.run_registry_session(task.question, session_id=task.task_id))
        text = ""
        if final.synthesis:
            # prefer the final_verdict section, then core_answer
            for name in ("final_verdict", "core_answer"):
                blk = next((s for s in final.synthesis.sections
                            if s.section_name.value == name and not s.unresolved), None)
                if blk:
                    text = blk.content
                    break
        cost = float((final.audit_summary or {}).get("total_moves", 0) or 0) or 1.0
        return AnswerResult(final_answer=extract_final_answer(text), raw_text=text,
                            confidence=0.5, cost_units=cost,
                            meta={"ratification_status": final.ratification_status})


# ── metrics ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TaskOutcome:
    task_id: str
    correct: bool
    confidence: float
    cost_units: float
    prediction: str


@dataclass(frozen=True)
class RunReport:
    answerer: str
    n: int
    accuracy: float
    ece: float
    total_cost: float
    cost_per_task: float
    mean_confidence: float
    outcomes: List[TaskOutcome] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


def expected_calibration_error(outcomes: Sequence[TaskOutcome], n_bins: int = 10) -> float:
    """Standard ECE: weighted |accuracy - confidence| across confidence bins."""
    if not outcomes:
        return 0.0
    bins: List[List[TaskOutcome]] = [[] for _ in range(n_bins)]
    for o in outcomes:
        idx = min(n_bins - 1, max(0, int(o.confidence * n_bins)))
        bins[idx].append(o)
    total = len(outcomes)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        acc = sum(1 for o in b if o.correct) / len(b)
        conf = sum(o.confidence for o in b) / len(b)
        ece += (len(b) / total) * abs(acc - conf)
    return round(ece, 4)


def run_benchmark(answerer: Answerer, tasks: Sequence[EvalTask]) -> RunReport:
    outcomes: List[TaskOutcome] = []
    for t in tasks:
        r = answerer.answer(t)
        outcomes.append(TaskOutcome(
            task_id=t.task_id, correct=verify(t, r.final_answer),
            confidence=r.confidence, cost_units=r.cost_units, prediction=r.final_answer))
    n = len(outcomes)
    acc = round(sum(1 for o in outcomes if o.correct) / n, 4) if n else 0.0
    total_cost = round(sum(o.cost_units for o in outcomes), 3)
    return RunReport(
        answerer=getattr(answerer, "name", answerer.__class__.__name__),
        n=n, accuracy=acc, ece=expected_calibration_error(outcomes),
        total_cost=total_cost, cost_per_task=round(total_cost / n, 3) if n else 0.0,
        mean_confidence=round(sum(o.confidence for o in outcomes) / n, 4) if n else 0.0,
        outcomes=outcomes)


@dataclass(frozen=True)
class ComparisonRow:
    answerer: str
    accuracy: float
    ece: float
    cost_per_task: float
    quality_per_cost: float


def compare(answerers: Sequence[Answerer], tasks: Sequence[EvalTask]) -> List[ComparisonRow]:
    """Quality-vs-cost (Pareto) table — accuracy is meaningless without its cost."""
    rows: List[ComparisonRow] = []
    for a in answerers:
        rep = run_benchmark(a, tasks)
        qpc = round(rep.accuracy / rep.cost_per_task, 4) if rep.cost_per_task else 0.0
        rows.append(ComparisonRow(rep.answerer, rep.accuracy, rep.ece, rep.cost_per_task, qpc))
    return rows
