"""Endpoint-level validation for the low-cost heterogeneous council.

Model-level `supported_parameters` is the union across a model's endpoints, and
trusting it is what produced the S7C routing refusal. This validates the exact
endpoint each seat would be pinned to, against the exact set of parameters the
CED request actually emits, and reports everything before any inference.

Two first-party GETs; the other two seats reuse listings already retained.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    fetch_openrouter_family_endpoints_v1,
)

RUNS = (
    Path(__file__).resolve().parents[1]
    / "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs"
)

#: Exactly what a CED turn puts on the wire, from the rendered bodies observed
#: in the probes: model, messages, stream, provider block, seed, the output
#: limit field, and response_format. `temperature` is deliberately absent.
EMITTED_SEMANTIC_PARAMETERS_V1 = ("seed", "response_format", "structured_outputs")

SEATS_V1: List[Dict[str, Any]] = [
    {
        "seat": "Alpha",
        "family": "GPT-5 Mini",
        "model": "openai/gpt-5-mini",
        "retained": "hard_logic_live_test_collection_v1.json",
        "selector": "openai/flex",
    },
    {
        "seat": "Beta",
        "family": "Qwen3 32B",
        "model": "qwen/qwen3-32b",
        "dispatch_class": "qwen3_32b_endpoints_get",
        "evidence_file": "q1_qwen3_32b_endpoints_v1.json",
    },
    {
        "seat": "Gamma",
        "family": "Llama 4 Scout",
        "model": "meta-llama/llama-4-scout",
        "dispatch_class": "llama_4_scout_endpoints_get",
        "evidence_file": "q1_llama_4_scout_endpoints_v1.json",
        "operator_slug": "meta-llama/llama-4-scout-17b-16e-instruct",
    },
    {
        "seat": "Delta",
        "family": "GPT-4.1 Mini",
        "model": "openai/gpt-4.1-mini",
        "evidence_path": (
            "docs/branches/feature-socrates-zero-openrouter-one-live-shadow-v1"
            "/evidence/s7c_model_endpoints_response_v1.json"
        ),
        "selector": "azure/swedencentral",
    },
]


def _per_million(pricing: Dict[str, Any], key: str) -> Decimal:
    return Decimal(str(pricing.get(key, "0"))) * 1_000_000


def describe_endpoint(endpoint: Dict[str, Any]) -> Dict[str, Any]:
    supported = set(endpoint.get("supported_parameters") or ())
    if "max_tokens" in supported:
        output_field: Optional[str] = "max_tokens"
    elif "max_completion_tokens" in supported:
        output_field = "max_completion_tokens"
    else:
        output_field = None
    pricing = endpoint.get("pricing") or {}
    missing = [p for p in EMITTED_SEMANTIC_PARAMETERS_V1 if p not in supported]
    if output_field is None:
        missing.append("max_tokens|max_completion_tokens")
    return {
        "tag": endpoint.get("tag"),
        "output_field": output_field,
        "structured_outputs": "structured_outputs" in supported,
        "response_format": "response_format" in supported,
        "seed": "seed" in supported,
        "temperature": "temperature" in supported,
        "tools": "tools" in supported,
        "context_length": endpoint.get("context_length"),
        "max_completion_tokens": endpoint.get("max_completion_tokens"),
        "prompt_per_million": _per_million(pricing, "prompt"),
        "completion_per_million": _per_million(pricing, "completion"),
        "request_usd": str(pricing.get("request", "0")),
        "missing": missing,
        "usable": not missing,
    }


def load_listing(spec: Dict[str, Any]) -> Dict[str, Any]:
    if "retained" in spec:
        return {}
    if "dispatch_class" in spec:
        fetched = fetch_openrouter_family_endpoints_v1(
            dispatch_class=spec["dispatch_class"], bounded_timeout_seconds=30
        )
        status = fetched.completion.http_status
        raw = fetched.raw_response_body
        print(f"  GET HTTP {status}, {len(raw)} bytes")
        if status != 200:
            return {}
        (RUNS / spec["evidence_file"]).write_bytes(raw)
        return json.loads(raw.decode("utf-8"))["data"]
    raw = (Path(__file__).resolve().parents[1] / spec["evidence_path"]).read_bytes()
    return json.loads(raw.decode("utf-8"))["data"]


def main() -> int:
    for spec in SEATS_V1:
        print(f"\n=== {spec['seat']}: {spec['family']} ({spec['model']}) ===")
        if "operator_slug" in spec:
            print(f"  NOTE operator slug {spec['operator_slug']} is absent from the")
            print(f"       catalog; this is the same model's canonical slug.")
        if "retained" in spec:
            stored = json.loads(
                (RUNS / spec["retained"]).read_text(encoding="utf-8")
            )["profile"]
            supported = set(stored["supported_parameters"])
            print(f"  retained profile, selector {stored['provider_selector']}")
            print(f"    output_field       {stored['output_limit_parameter']}")
            print(f"    structured_outputs {'structured_outputs' in supported}")
            print(f"    response_format    {'response_format' in supported}")
            print(f"    seed               {'seed' in supported}")
            print(f"    temperature        {'temperature' in supported}")
            print(f"    tools              {'tools' in supported}")
            continue
        listing = load_listing(spec)
        if not listing:
            print("  UNAVAILABLE")
            continue
        rows = [describe_endpoint(e) for e in listing.get("endpoints", [])]
        if "selector" in spec:
            rows = [r for r in rows if r["tag"] == spec["selector"]]
        rows.sort(key=lambda r: (not r["usable"], r["prompt_per_million"]))
        for r in rows[:8]:
            flag = "USABLE  " if r["usable"] else "unusable"
            print(
                f"  {flag} {str(r['tag']):26s} out={str(r['output_field']):22s} "
                f"so={int(r['structured_outputs'])} rf={int(r['response_format'])} "
                f"seed={int(r['seed'])} temp={int(r['temperature'])} "
                f"tools={int(r['tools'])} ctx={str(r['context_length']):>8} "
                f"maxout={str(r['max_completion_tokens']):>7} "
                f"${r['prompt_per_million']:.4f}/M in ${r['completion_per_million']:.4f}/M out "
                f"req={r['request_usd']}"
            )
            if r["missing"]:
                print(f"           missing: {', '.join(r['missing'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
