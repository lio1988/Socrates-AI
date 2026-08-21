# Branch: feature/openrouter-live-provider

## Memory

- Canonical provider integration seam: `backend/dialogues/provider_registry.py`.
- OpenRouter live use is opt-in and must not change the default offline path.
- Exact model pinning and returned-model verification are mandatory.
- Silent fallback or substitution is forbidden.
- `OPENROUTER_API_KEY` is environment-only.
- CED authority, role rotation, scoring, assembly, and ratification remain unchanged.
