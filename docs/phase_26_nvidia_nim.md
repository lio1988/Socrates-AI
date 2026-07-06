# Phase 26 — NVIDIA NIM provider adapter

This branch adds an additive NVIDIA NIM provider adapter for the Socrates AI / CED
registry path. The CED core is unchanged: scoring, ratification, assembly,
minimal-awareness, no-fabrication, quorum, and audit semantics remain the same.

## What changed

- `backend/dialogues/nvidia_nim_provider.py`
  - `LiveNvidiaNIMAdapter`
  - `NvidiaNIMRequest`
  - OpenAI-compatible `/chat/completions` request shape
  - secret-safe error redaction
  - honest status mapping: missing key, timeout, rate-limit, auth/error,
    invalid JSON, schema error
  - no network call at construction/import time

- `backend/dialogues/live_providers.py`
  - Keeps legacy Anthropic behavior unchanged when `CED_PROVIDER_FAMILIES` is absent.
  - Adds optional mixed provider seats via `CED_PROVIDER_FAMILIES`.
  - Supports `anthropic`, `nvidia`, and `mock` seats.

- `tests_dialogues/test_nvidia_nim_provider.py`
  - Offline contract tests for adapter parsing, failure statuses, no build-time
    calls, legacy behavior, and mixed registry wiring.

## Environment variables

Legacy Anthropic path remains:

```powershell
$env:CED_ENABLE_LIVE_PROVIDERS = "1"
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Mixed provider mode:

```powershell
$env:CED_ENABLE_LIVE_PROVIDERS = "1"
$env:CED_PROVIDER_FAMILIES = "anthropic,nvidia,nvidia,mock"
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:NVIDIA_API_KEY = "nvapi-..."
$env:CED_NVIDIA_MODELS = "nvidia/llama-3.1-nemotron-70b-instruct,nvidia/llama-3.1-nemotron-70b-instruct"
```

Optional NVIDIA-compatible base URL:

```powershell
$env:CED_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
```

Optional shared live settings:

```powershell
$env:CED_LIVE_MAX_TOKENS = "8192"
$env:CED_LIVE_TIMEOUT = "180"
$env:CED_LIVE_RETRIES = "1"
```

## Example usage

```python
import asyncio
from backend.dialogues.live_providers import build_council

ced, mode = build_council()
print(mode)  # mock, live, or mixed

final = asyncio.run(ced.run_registry_session(
    "Is knowledge merely justified true belief?",
    session_id="phase26_smoke",
))
print(final.ratified, final.epistemic_status)
```

## Safety / architecture notes

- No API key is read from or written to `.env` by the provider modules.
- Keys are passed through environment variables by the caller only.
- A provider failure never creates a fake `AgentMove`.
- The NVIDIA adapter reuses `parse_and_validate_move`, so JSON/schema validation
  stays centralized in `provider_registry.py`.
- NVIDIA request `routing` metadata is local-only and never sent to the provider.
- Hidden audit/scoring data is not inserted into the provider request.

## Recommended next phases

- Phase 26C: add NVIDIA embeddings/rerank evidence retrieval as a public evidence
  brief before council execution.
- Phase 26D: add record/replay runs comparing mixed council vs single provider and
  self-consistency at matched compute.
- Phase 27: optional local GPU deployment adapter (TensorRT-LLM / local NIM) after
  the API adapter is validated.
