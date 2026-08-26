# SocratesZero Phase 8.5D-S — Delivery artifacts

This is a **delivery branch**, not a reconstructed source-history branch.

The recent local Phase 8.x commits and the local base commit were not present
on the remote GitHub repository. To avoid fabricating ancestry from `main`, this
branch publishes the completed work as content-addressed download artifacts.

## Download

- `Socrates-AI-OpenRouter-phase8_5ds-changed-files.zip` — all added/changed
  Phase 8.5D-S files, the complete methodology report, validation and
  revalidation artifacts, application instructions, changed-file inventory,
  completion metadata and test results.
- `SHA256SUMS.txt` — integrity checksums.

## Result

`OPENROUTER WIRE SPECIFICATION MANIFEST v1` is **FALSIFIED** for this execution.
All six predeclared official-document retrieval attempts returned
`NETWORK_ERROR`; no replacement locator, seventh source, second retrieval pass,
credential, provider inference or invented schema fact was used.

The local implementation and focused tests completed successfully:

- Phase 8.5D-S focused tests: `29 passed`
- historical artifact hashes: `12/12 exact`
- offline deterministic revalidation: passed

The negative result is evidence about source retrieval in the execution
environment, not a claim that OpenRouter's public specification is necessarily
insufficient.

## Apply on Windows

1. Download `Socrates-AI-OpenRouter-phase8_5ds-changed-files.zip`.
2. Extract it to a temporary folder.
3. Follow `_completion_diagnostics/APPLY_TO_WINDOWS.md` inside the ZIP.
4. Preserve these local protected untracked files:
   - `scripts/live_dialogue.py.bak`
   - the malformed root filename beginning `ocratic_followup_mandate`
5. Run the focused tests before committing locally.

## Full snapshot

The larger full repository snapshot is retained in the ChatGPT conversation.
The GitHub delivery uses the smaller changed-files package because the remote
repository does not contain the local commit ancestry needed to present the
snapshot as a genuine source branch.
