# PLAN — OpenRouter Wire Specification Evidence v2r1

## Completed

1. Recover exactly six official sources from the interrupted Spark worktree.
2. Verify SHA-256, byte length and Git blob identity for every source.
3. Build one canonical Python schema with content-addressed IDs.
4. Create directly documented/lossless facts and mappings only.
5. Generate one authoritative manifest and validation artifact.
6. Run one offline revalidation without a new source retrieval.
7. Verify persisted artifacts byte-for-byte.
8. Run sealed v1 + v2r1 tests and Route Controls focused regression surface.

## Next

Create `feature/socrates-zero-openrouter-provenance-boundary-v1` from a verified checkpoint. Close the inherited raw historical-path inventory dependency using version-aware immutable provenance; do not weaken the static inventory test and do not rewrite sealed Route Controls v1.

After that passes, rerun a read-only OpenRouter wire-mapping v2 authorization gate.
