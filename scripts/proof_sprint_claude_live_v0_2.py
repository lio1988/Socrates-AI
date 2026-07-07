"""
Proof Sprint v0.2 — Claude live capture runner.

Runs the mini proof-sprint tasks against Anthropic Messages API using local
ANTHROPIC_API_KEY from .env or the shell environment. It prints captured answers
and a deterministic Evidence Harness leaderboard. No API key is printed.

Boundary: this is prompt-only CED-lite vs direct baseline, not full CED runtime.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from backend.dialogues.learning_evidence_harness import (
    CandidateSystemKind,
    CandidateSystemOutput,
    run_evidence_harness,
)
from backend.dialogues.learning_ground_truth_checks import GroundTruthTaskKind
from tests_dialogues.test_proof_sprint_mini_evidence import mini_proof_tasks


def load_dotenv() -> None:
    path = Path(".env")
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def extract_text(response_json: dict) -> str:
    chunks = []
    for item in response_json.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(item.get("text", ""))
    text = "\n".join(chunks).strip()
    if not text:
        raise RuntimeError("Could not extract text from Anthropic response: " + json.dumps(response_json)[:1000])
    return text


def call_claude(system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
    if not api_key:
        raise SystemExit("Missing ANTHROPIC_API_KEY in .env or shell environment")

    payload = {
        "model": model,
        "max_tokens": 200,
        "temperature": 0,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return extract_text(json.loads(response.read().decode("utf-8")))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Anthropic HTTP {exc.code}:\n{body[:2000]}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Anthropic connection error: {exc}") from exc


def main() -> int:
    load_dotenv()
    tasks = [task for task in mini_proof_tasks() if task.kind != GroundTruthTaskKind.CODE_CHECK_RECORD]
    outputs = []

    baseline_system = "Answer directly. Follow the requested output format exactly."
    ced_system = (
        "You are a CED-style evidence-aware responder. Do not guess. "
        "Use only the supplied evidence. If evidence is missing, output the exact uncertainty token requested. "
        "If a claim is not supported by the supplied evidence, identify it as an unsupported_claim. "
        "For numeric or multiple-choice tasks, output only the final requested value."
    )

    for task in tasks:
        print(f"\nTASK {task.task_id}")
        baseline_answer = call_claude(baseline_system, task.prompt)
        ced_answer = call_claude(ced_system, task.prompt)
        print("baseline_live:", baseline_answer)
        print("ced_lite_live:", ced_answer)
        outputs.append(
            CandidateSystemOutput(
                system_id="baseline_live",
                system_kind=CandidateSystemKind.BASELINE,
                task_id=task.task_id,
                answer=baseline_answer,
                metadata={"capture": "live_anthropic"},
            )
        )
        outputs.append(
            CandidateSystemOutput(
                system_id="ced_lite_live",
                system_kind=CandidateSystemKind.CED,
                task_id=task.task_id,
                answer=ced_answer,
                metadata={"capture": "live_anthropic", "boundary": "prompt_only_not_full_ced"},
            )
        )

    report = run_evidence_harness(
        tasks,
        outputs,
        metadata={
            "sprint": "proof_sprint_v0.2_live",
            "provider": "anthropic",
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
            "boundary": "baseline_live_vs_ced_lite_prompt_only",
        },
    )

    print("\n=== LEADERBOARD ===")
    for row in report.leaderboard:
        print(row.model_dump(mode="json"))

    print("\n=== FULL REPORT JSON ===")
    print(report.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
