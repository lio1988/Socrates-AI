"""Discover Llama/Qwen candidates for extra CED seats from the live catalog.

One first-party GET. Nothing is pinned from a guess: a slug becomes a permitted
target only after it has been read from the provider here.

The catalog's ``supported_parameters`` is the UNION across a model's endpoints,
so a model passing the filter below is a *candidate*, not a usable seat. The
authoritative per-endpoint profile still has to come from that model's own
endpoints listing, exactly as it did for Claude and Gemini.
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

RUNS = (
    Path(__file__).resolve().parents[1]
    / "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs"
)

#: What a CED seat must be able to do on the wire. The pre-dispatch guard emits
#: all four, and ``require_parameters: true`` means an endpoint missing any one
#: of them empties the candidate set and returns a routing refusal.
REQUIRED_PARAMETERS_V1 = ("max_tokens", "seed", "response_format", "structured_outputs")

#: Families the operator asked for.
WANTED_PREFIXES_V1 = ("meta-llama/", "qwen/")

#: Per-million-token ceiling a seat has to fit under to be affordable at the
#: 400,000-token conservative input reservation.
MAX_PROMPT_USD_PER_MILLION_V1 = Decimal("0.60")


def main() -> int:
    fetched = fetch_openrouter_family_endpoints_v1(
        dispatch_class="models_catalog_get", bounded_timeout_seconds=30
    )
    status = fetched.completion.http_status
    if status != 200:
        print(f"catalog GET failed with HTTP {status}")
        return 1
    raw = fetched.raw_response_body
    out = RUNS / "open_model_catalog_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)

    catalog = json.loads(raw.decode("utf-8"))["data"]
    print(f"catalog models: {len(catalog)}  (saved {len(raw)} bytes)")

    rows = []
    for model in catalog:
        slug = str(model.get("id", ""))
        if not slug.startswith(WANTED_PREFIXES_V1):
            continue
        supported = set(model.get("supported_parameters") or ())
        missing = [p for p in REQUIRED_PARAMETERS_V1 if p not in supported]
        pricing = model.get("pricing") or {}
        try:
            prompt_per_million = Decimal(str(pricing.get("prompt", "0"))) * 1_000_000
            completion_per_million = (
                Decimal(str(pricing.get("completion", "0"))) * 1_000_000
            )
        except Exception:
            continue
        rows.append(
            {
                "slug": slug,
                "context": model.get("context_length"),
                "prompt_per_million": prompt_per_million,
                "completion_per_million": completion_per_million,
                "missing": missing,
            }
        )

    usable = [
        r
        for r in rows
        if not r["missing"]
        and r["prompt_per_million"] > 0
        and r["prompt_per_million"] <= MAX_PROMPT_USD_PER_MILLION_V1
        and (r["context"] or 0) >= 128_000
    ]
    usable.sort(key=lambda r: (r["prompt_per_million"], r["slug"]))

    print(f"\nllama/qwen models in catalog: {len(rows)}")
    print(f"passing all four required parameters, priced, >=128k context: {len(usable)}\n")
    for r in usable[:25]:
        print(
            f"  {r['slug']:52s} ctx={r['context']:>9} "
            f"prompt=${r['prompt_per_million']:.4f}/M "
            f"completion=${r['completion_per_million']:.4f}/M"
        )

    if not usable:
        print("\nNo Llama or Qwen model advertises all four required parameters.")
        rejected = sorted(rows, key=lambda r: len(r["missing"]))[:10]
        print("Closest candidates and what each lacks:")
        for r in rejected:
            print(f"  {r['slug']:52s} missing: {', '.join(r['missing']) or '-'}")
    print(f"\n  catalog retained: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
