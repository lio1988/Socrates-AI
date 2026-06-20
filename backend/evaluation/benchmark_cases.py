"""Benchmark case schema + loader for the CED Evaluation Harness v0.1.

The on-disk benchmark is data, not code. Every file must declare
schema_version == "ced_eval_v0.1"; the loader rejects anything else so future
schema changes fail fast instead of being silently mis-read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

SCHEMA_VERSION = "ced_eval_v0.1"
DATA_PATH = Path(__file__).resolve().parent / "data" / "ced_benchmark_v0.json"


@dataclass(frozen=True)
class CaseGold:
    expected_claim_contains: str = ""
    forbidden_claim_contains: List[str] = field(default_factory=list)
    expected_elenchus_target_contains: str = ""
    revision_should_improve: bool = True
    # v0.1 addition (constraint D): reduce circularity by checking the revision
    # text against external gold, not only our own quality scorer.
    expected_revision_contains: str = ""
    forbidden_revision_contains: List[str] = field(default_factory=list)
    must_address_objection_contains: str = ""
    cbe_required_fields: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScriptedTurn:
    round: int
    model: str
    role: str  # "answer" | "revision" | "socratic"
    content: str


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    question: str
    rounds: int
    scripted_turns: List[ScriptedTurn]
    single_shot_answer: str
    gold: CaseGold

    def answer_turns(self) -> List[ScriptedTurn]:
        return [t for t in self.scripted_turns if t.role == "answer"]

    def revision_text(self) -> str:
        for t in self.scripted_turns:
            if t.role == "revision":
                return t.content
        return ""


def _parse_case(raw: dict) -> BenchmarkCase:
    return BenchmarkCase(
        id=raw["id"],
        question=raw["question"],
        rounds=int(raw["rounds"]),
        scripted_turns=[ScriptedTurn(**t) for t in raw.get("scripted_turns", [])],
        single_shot_answer=raw.get("single_shot_answer", ""),
        gold=CaseGold(**raw.get("gold", {})),
    )


def load_benchmark(path: Path | str = DATA_PATH) -> List[BenchmarkCase]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported benchmark schema_version: {version!r} "
            f"(expected {SCHEMA_VERSION!r})"
        )
    cases = [_parse_case(c) for c in data.get("cases", [])]
    # Deterministic order by id.
    return sorted(cases, key=lambda c: c.id)
