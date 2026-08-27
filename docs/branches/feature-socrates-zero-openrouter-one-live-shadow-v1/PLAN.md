# PLAN — feature/socrates-zero-openrouter-one-live-shadow-v1

## Success criterion

Exactly one cost-bounded, explicitly authorized OpenRouter shadow request
dispatched once; raw response captured, mapped by frozen S5, causally integrated
by frozen S6, with no authority leakage, no retry, no privacy violation and no
CED mutation.

## Ordered steps

1. **Verify** source branch, HEAD, worktree, and the sealed predecessor state;
   resolve the circulated S7A artifact-ID conflict from repository bytes. *Done.*
2. **Create** the S7B branch from `e608569`. *Done.*
3. **Obtain** operator price policy, claim-store location and trust attestation.
   *Done — supplied explicitly by the operator.*
4. **Resolve** whether the frozen claim-store contract permits the declared trust
   model, or demands cryptographic anti-rollback. *Done — it externalizes trust
   to an operator grant; it does not demand cryptography.*
5. **Build and offline-test** the claim-store grant, the one-shot transport and
   the JIT client. *Done.*
6. **Build** the live runner as pure functions so the dry run and the live run
   share one code path. *Done.*
7. **Run** all offline adversarial tests and regression gates. *Done.*
8. **Commit** the implementation and create `PRE-INFERENCE S7B FREEZE`.
9. **Obtain** the one allowed first-party model-limit GET.
10. **Establish** P17 from that response alone.
11. **Render** the exact production request using the operator ceilings.
12. **Establish** P19 and verify worst-case total <= the operator ceiling.
13. **Report** the `S7B FINAL PRE-LIVE PREFLIGHT` and **STOP**.
14. On explicit `AUTHORIZE ONE LIVE SHADOW CALL`: re-verify, mint, consume,
    dispatch once, capture, map, integrate, replay offline, report.

## Validation gates

| gate | required | observed |
| --- | --- | --- |
| S7B focused | all pass | **29 passed** |
| S7A | unchanged, all pass | **106 passed** |
| S6 | unchanged, all pass | **149 passed** |
| S5 | unchanged, all pass | **109 passed** |
| S3 | unchanged, all pass | **64 passed** |
| Route Controls | unchanged, all pass | **103 passed** |
| Manifest v1 + v2r1 | unchanged, all pass | **25 passed** |
| all OpenRouter | all pass | **863 passed, 1 skipped** |
| `git diff --check` | PASS | **PASS** |
| inference POSTs before authorization | 0 | **0** |

### Correction round (offline only)

| gate | required | observed |
| --- | --- | --- |
| S7B focused | all pass | **59 passed** |
| request byte preservation | registered == dispatched | **PASS** |
| one-byte mutation | digest must differ | **PASS** |
| semantic-header preservation | exact | **PASS** |
| Authorization excluded from evidence | absent everywhere | **PASS** |
| wrong host / path / method | refused pre-socket | **PASS** |
| credential read sites | exactly 1 | **1** |
| import inertness | 0 reads, 0 writes | **PASS** |
| JIT client offline | synthetic + retained fixtures | **PASS** |
| S5 compatibility | no reconstruction | **PASS** |
| S6 compatibility | no reconstruction | **PASS** |
| network this round | 0 | **0** |

## Stop conditions

Inference POST count stays 0 and the phase halts if: the credential is absent;
the metadata GET fails or its response fails the frozen parser; P17 does not
become ESTABLISHED; P19 does not become ESTABLISHED; the worst-case total exceeds
the operator ceiling; the claim-store grant cannot be honestly produced; the
transport is not ready; the authorization is already consumed; or the operator
does not give the final explicit authorization.

The ceiling is never raised to make a call possible. If the worst case exceeds
`$0.60`, the phase stops and reports — it does not ask for a larger ceiling.

## After the call

Whatever the outcome, there is no second request. A provider error is retained
and analyzed as evidence. A defect discovered after dispatch is documented, not
patched-and-retried.
