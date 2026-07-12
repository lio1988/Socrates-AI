"""Operator harness for the Micro-Socratic Kernel v1 (offline, mock adapter).

A NAMED, MANUAL act: an operator runs one bounded self-check over a task+draft
and writes the strict check plus a tamper-evident receipt.

    python scripts/openclaw_micro_socratic_check.py ^
        --agent local_apprentice_001 ^
        --mode standard ^
        --provider mock ^
        --model mock-socratic-auditor ^
        --task-file runs/micro_socratic/task.txt ^
        --draft-file runs/micro_socratic/draft.txt ^
        --output runs/micro_socratic/check.json

This command performs EXACTLY ONE mock provider call. It writes only a check
file and a receipt file. It changes no agent state, no Memory/Identity/Soul, no
proposal or evidence registry, and no governance state. It executes no tool and
opens no consultation. In v1 it wires only the deterministic mock adapter; a
live provider is never activated here and no `.env` is read.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_socratic_kernel import (        # noqa: E402
    KernelPolicy,
    MicroSocraticError,
    MicroSocraticReceiptStore,
    MicroSocraticRequest,
    MicroSocraticKernelService,
    MockKernelProvider,
    sha256_text,
)

_W = 78


def _flag(argv, name, default=""):
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return str(argv[index + 1]).strip()
    return default


def _read_text(path_str: str, *, label: str) -> str:
    path = pathlib.Path(path_str)
    if not path.is_file():
        raise MicroSocraticError(f"{label} not found: {path}")
    return path.read_text(encoding="utf-8")


def _now_iso(env) -> str:
    override = env.get("CED_MICRO_SOCRATIC_NOW")
    if override:
        return str(override).strip()
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _plus_seconds(iso: str, seconds: float) -> str:
    parsed = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    future = parsed.astimezone(_dt.timezone.utc) + _dt.timedelta(seconds=seconds)
    return future.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_request(argv, env) -> MicroSocraticRequest:
    mode = _flag(argv, "--mode", "standard")
    agent = _flag(argv, "--agent")
    provider = _flag(argv, "--provider", "mock")
    model = _flag(argv, "--model")
    purpose = _flag(argv, "--purpose",
                    "bounded pre-final self-check (recommendation only)")
    task = _read_text(_flag(argv, "--task-file"), label="task-file")
    draft = _read_text(_flag(argv, "--draft-file"), label="draft-file")

    max_tokens = int(_flag(argv, "--max-tokens", "1024"))
    timeout_seconds = float(_flag(argv, "--timeout-seconds", "60"))
    ttl_seconds = float(_flag(argv, "--ttl-seconds", "3600"))
    created_at = _now_iso(env)
    expires_at = _flag(argv, "--expires-at") or _plus_seconds(
        created_at, ttl_seconds)

    request_id = _flag(argv, "--request-id")
    if not request_id:
        # Hash first, mode last: a mode like "high_risk" must not sit right
        # before "-<16 hex>", which the secret filter reads as an "sk-..." key.
        request_id = f"kernel-{sha256_text(task + draft)[:16]}-{mode}"

    return MicroSocraticRequest(
        request_id=request_id,
        agent_id=agent,
        mode=mode,
        provider=provider,
        model=model,
        task=task,
        draft=draft,
        purpose=purpose,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        created_at=created_at,
        expires_at=expires_at,
    )


def run_check_cli(argv, env):
    request = build_request(argv, env)

    if request.provider != "mock":
        raise MicroSocraticError(
            f"v1 CLI wires only the deterministic 'mock' adapter; provider "
            f"{request.provider!r} would require explicit live configuration "
            "that is intentionally not enabled here")
    provider = MockKernelProvider(provider_id="mock")

    fixed_now = _now_iso(env)
    service = MicroSocraticKernelService(
        KernelPolicy(),
        worker_id=_flag(argv, "--worker-id", "operator-cli"),
        clock=lambda: fixed_now,
    )
    outcome = asyncio.run(service.check(request, provider, now=request.created_at))
    return request, outcome


def main(argv=None, env=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    env = os.environ if env is None else env

    print("=" * _W)
    print("  OPENCLAW MICRO-SOCRATIC CHECK - bounded self-audit (advice only)")
    print("=" * _W)

    output = _flag(argv, "--output")
    if not _flag(argv, "--task-file") or not _flag(argv, "--draft-file") \
            or not output:
        print("  usage: openclaw_micro_socratic_check.py --agent <id>")
        print("         --mode <light|standard|high_risk> --provider mock")
        print("         --model <name> --task-file <path> --draft-file <path>")
        print("         --output <check.json>")
        print("=" * _W)
        return 1

    try:
        request, outcome = run_check_cli(argv, env)
    except (MicroSocraticError, ValueError, OSError) as exc:
        print(f"  REFUSED: {exc}")
        print("=" * _W)
        return 1

    out_path = pathlib.Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        outcome.check.to_record(), ensure_ascii=False, sort_keys=True,
        indent=2) + "\n", encoding="utf-8")

    store = MicroSocraticReceiptStore(out_path.parent)
    try:
        receipt_path = store.save(outcome.receipt)
    except MicroSocraticError as exc:
        print(f"  REFUSED: {exc}")
        print("=" * _W)
        return 1

    print(f"  agent        : {request.agent_id}")
    print(f"  mode         : {request.mode}")
    print(f"  provider     : {request.provider} / {request.model}")
    print(f"  isolated     : check={outcome.check.isolated_check} "
          f"tools={outcome.check.tools_executed} "
          f"consult={outcome.check.consultation_executed} "
          f"rounds={outcome.check.inner_rounds}")
    print(f"  decision     : {outcome.check.decision}  (recommendation, not approval)")
    print(f"  request_dgst : {request.request_digest[:16]}")
    print(f"  result_dgst  : {outcome.check.response_digest[:16]}")
    print(f"  receipt_dgst : {outcome.receipt['receipt_digest'][:16]}")
    print(f"  check        : {out_path}")
    print(f"  receipt      : {receipt_path}")
    print("  Recommendation only. The agent may question itself; it may not")
    print("  certify itself. No tool, consultation, mutation, or CED change.")
    print("=" * _W)
    return 0


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
