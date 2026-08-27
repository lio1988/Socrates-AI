# MEMORY — feature/socrates-zero-openrouter-raw-wire-mapping-v2

Stable context. Not an action log.

## Source checkpoint

- Source branch: `feature/socrates-zero-openrouter-wire-mapping-v2-authorization-gate`
- Source HEAD: `8c6a524b469c7cb6d4b9e9145157fc8123e8d4cf` (published)
- S3 checkpoint: `ae8b3ec17810deb0c8523c78a541d032994fb408`
- v2r1 checkpoint: `0d09822048d4f7c34cf234342ec4c36ef3db0ead`

## Non-negotiable invariants

1. **The retained v2r1 snapshot is the evidence boundary.** No second official
   retrieval, no browsing current OpenRouter docs, no model memory filling a
   schema gap. If the retained sources do not say it, the mapper does not know it.
2. **Exact endpoint response identity is a firewall.** Emit
   `UNAVAILABLE_BY_DOCUMENTED_CONTRACT` with value `None`. Never synthesize it
   from the provider display label, `provider.only`, `provider.order`, a selected
   candidate, model, region, an attempt record, or any combination. The contract
   type pins the value to `None`.
3. **Cache authority is header-borne.** `X-OpenRouter-Cache-Status` decides
   HIT/MISS. Metadata absence never proves a hit, though a hit does imply
   metadata absence — the implication runs one way only.
4. **Requested model never substitutes for actual served model.** `$.model` is
   the only source of `actual_served_model`. String equality between them is a
   coincidence, never a derivation.
5. **Provider granularity is `HUMAN_DISPLAY_NAME`.** The normalized field is
   named `provider_display_name` so the granularity cannot be lost. It is never
   compared against request-side provider slugs.
6. **Unknown/additive fields are preserved without authority.** They may never
   override a mapped field.
7. **No runtime authority.** S5 output is offline scientific evidence. It is not
   wired into the production adapter, does not replace the Route Controls parser
   v1, and is not consumed by CED.

## Two findings that shaped the implementation

**Error-envelope metadata is a loose object.** The retained OpenAPI binds
`openrouter_metadata` to the strict `OpenRouterMetadata` ref in success schemas,
but declares it `additionalProperties: {}` / `type: [object, null]` in the
documented error schemas. That is why the documented 404 example legitimately
omits `region`, `summary` and `is_byok`. The mapper therefore enforces the seven
required fields on SUCCESS only. Enforcing them on ERROR would reject an
officially documented response.

**Two enums, two policies.** `RoutingStrategy` is closed — an undocumented value
fails closed. `PipelineStageType` is documented as growing ("The list grows over
time. Treat unknown stage types as opaque"), so an unknown stage type is
preserved opaquely and never rejected. The additive statement covers new optional
fields and new pipeline stage types; it does not extend to strategy values.

## Documented vocabulary

`RoutingStrategy`: direct, auto, free, latest, alias, fallback, pareto,
bodybuilder, fusion.

`PipelineStageType` (open/growing): guardrail, plugin, server_tools,
response_healing, context_compression.

`OpenRouterMetadata` required (success): requested, strategy, region, summary,
attempt, is_byok, endpoints. Optional: attempts, params, pipeline.

`attempt`: success is one-indexed (>= 1); on error 0 means no provider reached,
>= 1 means attempted providers failed. No maximum is documented, so none is
imposed.

Cache headers: `X-OpenRouter-Cache-Status` (HIT|MISS), `-Age` (HIT only),
`-TTL` (remaining on HIT, full on MISS), `-Source-Id` (HIT only),
`X-Generation-Id` (every response).

## Two traps for a future session

`importlib.reload` on any of these modules rebinds every contract class, so
`type(x) is Contract` fails everywhere afterwards. To prove import inertness,
execute the module body into a throwaway package-qualified namespace instead.

A static scanner that looks for marker literals must not contain those literals
in its own source if it scans itself. Assemble them from fragments.

## Environment

- Repository: `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish`
- Interpreter: `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe`
- `PYTHONPATH` must point at the repository root.
- `.gitignore` ignores `*.md` and `*.json` wholesale; use `git add -f`.

See [PLAN.md](PLAN.md) and [PRESENT.md](PRESENT.md).
