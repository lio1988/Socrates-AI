# Branch: feature/socrates-zero-canonical-successor-env-v0

## Success criterion

Achieve 100% semantic parity on every frozen authoritative opening case with
zero source/sibling/production mutation, zero identity/projection/receipt/
resource mismatch, zero fabricated observations, deterministic byte replay,
and no change to frozen Phase 5/7 artifacts or search components.

## Ordered work

1. [done] Verify the exact Phase 7.5 checkpoint, protected state, and frozen
   artifact hashes.
2. [done] Audit the actual CED transition path and select exactly one action
   family.
3. [done] Freeze architecture, IDs, capsule/pending/observation/result/receipt
   designs, parity fields, corpus sources, and failure taxonomy.
4. [done] Preserve and invalidate the rebound v0 corpus; capture and freeze the
   observation-bound manifest and authoritative corpus v1.
5. [done] Extract the existing canonical CED task/response application seam
   without changing production behavior.
6. [done] Implement capsule capture, `prepare_transition`, recorded-
   observation injection, `apply_observation`, isolation, projection, and
   resource receipts.
7. [done] Add mandatory contract, rejection, isolation, leakage, budget,
   delegation, idempotence, order, and compatibility tests.
8. [stopped] The frozen evaluator was run exactly once. It produced a
   `FALSIFIED` artifact: supported parity 5/5, unavailable negatives 13/14,
   with one `wrong-provider` failure-reason mismatch. No replay lock was run.
9. [not run] The complete post-result expansion gate is not used to promote a
   falsified hypothesis. Pre-result production and frozen-artifact gates remain
   green and the immutable result is preserved.
10. [in progress] Finalize the durable falsification checkpoint and stop.

## Stop conditions

Stop and falsify the hypothesis if parity requires copied CED rules, if any
canonical result diverges, if source/sibling/production isolation fails, if
identity or resource truth cannot be preserved, if observation fabrication is
required, or if any unsupported case silently creates a successor.

The frozen threshold also requires every unavailable probe to reproduce its
predeclared reason. That stop condition triggered for `wrong-provider`.
