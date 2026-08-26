# Phase 8.5D-S memory

## Parent decision

- Parent branch: `feature/socrates-zero-openrouter-wire-mapping-gate-v0`.
- Parent decision: `SPECIFICATION EVIDENCE MANIFEST v1 REQUIRED FIRST`.
- Base Git HEAD: `5ac106b61c9c79b9b9090b5824b967a6a435cca3`.
- This was the sole authorized manifest v1 implementation attempt.

## Permanent result

- Hypothesis: `FALSIFIED`.
- Reason: one frozen six-source retrieval pass produced six `NETWORK_ERROR`
  events and retained zero official source bytes.
- The negative result must not be restated as proof that the official docs are
  insufficient; source sufficiency was not observable in this environment.
- No second retrieval, alternate downloader, replacement locator, seventh
  source, or memory-derived mapping was used.

## Authoritative IDs

- Source plan:
  `szorwiresourceplanv1_19b0fcbaab0004ab5db0b7d529f8eaf055ccbcba75b68b48a3a059c540bb98cc`.
- Retrieval log:
  `szorwireretrievallogv1_df7bb7728564d549057a9cd135eab07cb3377315b907ef092cd74e24a72295e4`.
- Manifest:
  `szorwirespecmanifestv1_bb4919b28f1913de4484c54dadbece8f0e16876ce233aa12eaaf00eb506a3a41`.
- Validation:
  `szorwiremanifestvalidationv1_9a30a408ff6c4537319cfc8b1e3c62fec24e783f2d52db6a498612d10464fee2`.
- Revalidation:
  `szorwiremanifestrevalidationv1_436590983388bb4d412d7db3c5124c9ce56480056ff3fb7d41569a37bb9c18a3`.

## Frozen evidence rules

- Official public unauthenticated sources only.
- Used source facts require inspectable retained bytes, lengths, SHA-256 and
  exact anchors/ranges.
- Positive mappings may be only `DIRECTLY_DOCUMENTED` or
  `DERIVED_LOSSLESSLY`.
- Missing provider/model/cache/attempt/endpoint semantics remain
  `NOT_ESTABLISHED`.
- No parser/runtime/predecessor mutation.

## Frozen source boundary

- Domain: `openrouter.ai` only.
- Planned sources: exactly 6.
- Retries: 0.
- Browser inspections: 0.
- Maximum one same-origin HTTPS redirect.
- 8 MiB per source, 20 MiB total response, 1 MiB retained evidence.
- 20-second per-source timeout.

## Testing limitation

The assistant worked from a user-provided source ZIP without `.git`. Focused
Phase 8.5D-S tests pass, but historical tests that invoke `git show` cannot run
in that environment. Rerun the full suite in the user's actual Git checkout
after applying the returned patch.

## Next

`RETURN TO ARCHITECTURE DECISION`.

Wire-mapping v2, P17/P18/P19, live pilot, Experience Store, learned Value,
learned Policy, RL and production authority remain blocked.
