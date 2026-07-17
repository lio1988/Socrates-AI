# Cursor — Socrates AI Instructions

Cursor must treat `AGENTS.md` as the repository-level working contract.

## Required reading order

Before proposing or applying any change:

1. `AGENTS.md`
2. `.agents/user/ME.md`
3. `.agents/branches/feature-openclaw-memory-ab-attestation/README.md`
4. `.agents/branches/feature-openclaw-memory-ab-attestation/PRESENT.md`
5. `.agents/branches/feature-openclaw-memory-ab-attestation/MEMORY.md`
6. `.agents/branches/feature-openclaw-memory-ab-attestation/PLANS.md`
7. every canonical document linked from the branch README
8. the actual source, tests, Git state, and live PR metadata

## Operating requirements

- Use the user profile only as collaboration and durable product context.
- Do not treat user preferences as proof of runtime behavior or repository state.
- Preserve the permanent CED, evidence, Memory, Identity, Soul, exact-model, and no-self-approval invariants in `AGENTS.md`.
- Do not infer or store personal data beyond `.agents/user/ME.md`.
- Do not describe local-only, documented, focused-tested, unretargeted, or unmerged work as shipped.
- Update the active branch `PRESENT.md` before handoff.

The `.cursor/rules/00-socrates-ai-user-context.mdc` rule points Cursor to the same canonical sources. Do not duplicate or fork the user profile inside editor-specific files.
