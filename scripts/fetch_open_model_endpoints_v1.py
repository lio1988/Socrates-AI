"""Fetch the authoritative per-endpoint listings for the two open-weight seats.

Two first-party GETs. The catalog's ``supported_parameters`` is the union across
a model's endpoints, so it can say a model supports ``structured_outputs`` when
the specific endpoint we would pin does not. That mismatch is what produced the
S7C routing refusal, and this is the surface that settles it.

For each family this prints every endpoint that advertises all four wire
parameters a CED seat needs, with that endpoint's own prices, so the seat can be
pinned to one endpoint whose capabilities were actually observed.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    fetch_openrouter_family_endpoints_v1,
)
from scripts.discover_open_model_seats_v1 import REQUIRED_PARAMETERS_V1, RUNS

FAMILIES_V1 = {
    "qwen3_235b": {
        "dispatch_class": "qwen3_235b_endpoints_get",
        "evidence_file": "q1_qwen3_235b_endpoints_v1.json",
    },
    "llama_4_maverick": {
        "dispatch_class": "llama_4_maverick_endpoints_get",
        "evidence_file": "q1_llama_4_maverick_endpoints_v1.json",
    },
}


def main() -> int:
    for key, spec in FAMILIES_V1.items():
        fetched = fetch_openrouter_family_endpoints_v1(
            dispatch_class=spec["dispatch_class"], bounded_timeout_seconds=30
        )
        status = fetched.completion.http_status
        raw = fetched.raw_response_body
        print(f"\n=== {key}: HTTP {status}, {len(raw)} bytes ===")
        if status != 200:
            print(f"  refused: {raw[:300]!r}")
            continue
        out = RUNS / spec["evidence_file"]
        out.write_bytes(raw)
        listing = json.loads(raw.decode("utf-8"))["data"]
        print(f"  model id : {listing.get('id')}")
        for endpoint in listing.get("endpoints", []):
            supported = set(endpoint.get("supported_parameters") or ())
            missing = [p for p in REQUIRED_PARAMETERS_V1 if p not in supported]
            pricing = endpoint.get("pricing") or {}
            prompt_m = Decimal(str(pricing.get("prompt", "0"))) * 1_000_000
            completion_m = Decimal(str(pricing.get("completion", "0"))) * 1_000_000
            request_usd = str(pricing.get("request", "0"))
            flag = "USABLE  " if not missing else "unusable"
            print(
                f"  {flag} tag={str(endpoint.get('tag')):32s} "
                f"ctx={str(endpoint.get('context_length')):>8} "
                f"maxout={str(endpoint.get('max_completion_tokens')):>6} "
                f"${prompt_m:.4f}/M in ${completion_m:.4f}/M out req={request_usd}"
            )
            if missing:
                print(f"           missing: {', '.join(missing)}")
        print(f"  retained: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
