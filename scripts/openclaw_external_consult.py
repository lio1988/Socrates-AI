"""Operator harness for External Self-Consultation v1 (offline, mock adapter).

A NAMED, MANUAL act: an operator submits one bounded question to an isolated
advisory model and writes the strict result plus a tamper-evident receipt.

    python scripts/openclaw_external_consult.py ^
        --mode critic ^
        --agent local_apprentice_001 ^
        --provider mock ^
        --model mock-critic ^
        --question-file runs/consultation/question.txt ^
        --draft-file runs/consultation/draft.txt ^
        --output runs/consultation/critic-result.json

    python scripts/openclaw_external_consult.py ^
        --mode independent_solver ^
        --agent local_apprentice_001 ^
        --provider mock ^
        --model mock-solver ^
        --question-file runs/consultation/question.txt ^
        --output runs/consultation/solver-result.json

    python scripts/openclaw_external_consult.py ^
        --mode judge ^
        --agent local_apprentice_001 ^
        --provider mock ^
        --model mock-judge ^
        --question-file runs/consultation/question.txt ^
        --candidate-file runs/consultation/a.txt ^
        --candidate-file runs/consultation/b.txt ^
        --output runs/consultation/judge-result.json

This command performs EXACTLY ONE mock provider call. It writes only a result
file and a receipt file. It changes no agent state, no Memory/Identity/Soul,
no proposal or evidence registry, and no governance state. In v1 it wires only
the deterministic mock adapter; a live provider is never activated here.
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

from backend.dialogues.openclaw_consultation import (          # noqa: E402
    ConsultationError,
    ConsultationPolicy,
    ConsultationReceiptStore,
    ExternalConsultationRequest,
    ExternalConsultationService,
    MockConsultationProvider,
)

_W = 78


def _flag(argv, name, default=""):
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return str(argv[index + 1]).strip()
    return default


def _flags(argv, name):
    values = []
    for index, value in enumerate(argv[:-1]):
        if value == name:
            cleaned = str(argv[index + 1]).strip()
            if cleaned:
                values.append(cleaned)
    return values


def _read_text(path_str: str, *, label: str) -> str:
    path = pathlib.Path(path_str)
    if not path.is_file():
        raise ConsultationError(f"{label} not found: {path}")
    return path.read_text(encoding="utf-8")


def _now_iso(env) -> str:
    """Fixed clock when CED_CONSULTATION_NOW is set (deterministic tests),
    otherwise real UTC now. Never reads .env; env is passed in explicitly."""
    override = env.get("CED_CONSULTATION_NOW")
    if override:
        return str(override).strip()
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _plus_seconds(iso: str, seconds: float) -> str:
    parsed = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    future = parsed.astimezone(_dt.timezone.utc) + _dt.timedelta(seconds=seconds)
    return future.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_request(argv, env) -> ExternalConsultationRequest:
    mode = _flag(argv, "--mode")
    agent = _flag(argv, "--agent")
    provider = _flag(argv, "--provider", "mock")
    model = _flag(argv, "--model")
    relation = _flag(argv, "--relation", "peer_model")
    purpose = _flag(argv, "--purpose",
                    "operator external self-consultation (advice only)")
    question = _read_text(_flag(argv, "--question-file"), label="question-file")

    draft = None
    candidates = ()
    candidate_order = ()
    if mode == "critic":
        draft = _read_text(_flag(argv, "--draft-file"), label="draft-file")
    elif mode == "judge":
        files = _flags(argv, "--candidate-file")
        if len(files) != 2:
            raise ConsultationError(
                "judge mode requires exactly two --candidate-file arguments")
        candidates = tuple(_read_text(path, label="candidate-file")
                           for path in files)
        # Deterministic presentation order, bound into the request digest.
        # "0,1" (default) shows candidate-file #1 as candidate_a; "1,0" swaps.
        raw_order = _flag(argv, "--candidate-order", "0,1")
        try:
            candidate_order = tuple(
                int(part) for part in raw_order.split(","))
        except ValueError:
            raise ConsultationError(
                "--candidate-order must be '0,1' or '1,0'")

    max_tokens = int(_flag(argv, "--max-tokens", "1024"))
    timeout_seconds = float(_flag(argv, "--timeout-seconds", "60"))
    ttl_seconds = float(_flag(argv, "--ttl-seconds", "3600"))
    created_at = _now_iso(env)
    expires_at = _flag(argv, "--expires-at") or _plus_seconds(
        created_at, ttl_seconds)

    request_id = _flag(argv, "--request-id")
    if not request_id:
        from backend.dialogues.openclaw_consultation import sha256_text
        request_id = f"consult-{mode}-{sha256_text(question)[:16]}"

    return ExternalConsultationRequest(
        request_id=request_id,
        requesting_agent_id=agent,
        mode=mode,
        consulted_provider=provider,
        consulted_model=model,
        consultation_relation=relation,
        question=question,
        purpose=purpose,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        created_at=created_at,
        expires_at=expires_at,
        draft=draft,
        candidates=candidates,
        candidate_order=candidate_order,
    )


def run_consultation_cli(argv, env):
    request = build_request(argv, env)

    provider_name = request.consulted_provider
    if provider_name != "mock":
        raise ConsultationError(
            f"v1 CLI wires only the deterministic 'mock' adapter; provider "
            f"{provider_name!r} would require explicit live configuration that "
            "is intentionally not enabled here")
    provider = MockConsultationProvider(provider_id="mock")

    # A fixed clock keeps the receipt deterministic under CED_CONSULTATION_NOW;
    # otherwise it stamps real UTC now.
    fixed_now = _now_iso(env)
    service = ExternalConsultationService(
        ConsultationPolicy(),
        worker_id=_flag(argv, "--worker-id", "operator-cli"),
        clock=lambda: fixed_now,
    )
    outcome = asyncio.run(service.consult(
        request, provider, now=request.created_at))
    return request, outcome


def main(argv=None, env=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    env = os.environ if env is None else env

    print("=" * _W)
    print("  OPENCLAW EXTERNAL CONSULT - isolated advisory call (advice only)")
    print("=" * _W)

    output = _flag(argv, "--output")
    if not _flag(argv, "--mode") or not _flag(argv, "--question-file") \
            or not output:
        print("  usage: openclaw_external_consult.py --mode <critic|"
              "independent_solver|judge>")
        print("         --agent <id> --provider mock --model <name>")
        print("         --question-file <path> [--draft-file <path>]")
        print("         [--candidate-file <path> --candidate-file <path>]")
        print("         --output <result.json>")
        print("=" * _W)
        return 1

    try:
        request, outcome = run_consultation_cli(argv, env)
    except (ConsultationError, ValueError, OSError) as exc:
        print(f"  REFUSED: {exc}")
        print("=" * _W)
        return 1

    out_path = pathlib.Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        outcome.result.to_record(), ensure_ascii=False, sort_keys=True,
        indent=2) + "\n", encoding="utf-8")

    # The tamper-evident store handles idempotency and conflict refusal.
    store = ConsultationReceiptStore(out_path.parent)
    try:
        receipt_path = store.save(outcome.receipt)
    except ConsultationError as exc:
        print(f"  REFUSED: {exc}")
        print("=" * _W)
        return 1

    print(f"  mode         : {request.mode}")
    print(f"  agent        : {request.requesting_agent_id}")
    print(f"  provider     : {request.consulted_provider} "
          f"/ {request.consulted_model} ({request.consultation_relation})")
    print(f"  isolated     : session={outcome.result.isolated_session} "
          f"tools_disabled={outcome.result.tools_disabled} "
          f"delegation_disabled={outcome.result.delegation_disabled}")
    print(f"  request_dgst : {request.request_digest[:16]}")
    print(f"  result_dgst  : {outcome.result.response_digest[:16]}")
    print(f"  receipt_dgst : {outcome.receipt['receipt_digest'][:16]}")
    print(f"  result       : {out_path}")
    print(f"  receipt      : {receipt_path}")
    print("  Advice only. Not authority, approval, or evidence by itself.")
    print("  No agent state, Memory/Identity/Soul, proposal, or CED changed.")
    print("=" * _W)
    return 0


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
