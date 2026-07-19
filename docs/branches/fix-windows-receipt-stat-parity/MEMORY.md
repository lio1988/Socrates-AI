# Branch: fix/windows-receipt-stat-parity

## Stable context

The baseline `origin/main` commit
`b699dad275a9c8824811b0c7307a688f700d3eb2` fails all four parameterizations
of `test_load_final_stat_failure_is_safe_domain_error` on Windows with Python
3.12.13 and pytest 9.1.1.

The test computes `final`, monkeypatches the shared `WindowsPath.stat`, and then
calls `store.load()`. The load path invokes `_path_for()` again, whose
containment resolution may call `Path.resolve()` and therefore the patched
`stat` before the intended final existence-discovery operation.

## Decisions

- Reuse the already-computed `final` through an instance-level `_path_for`
  seam during `store.load()`.
- Keep the `WindowsPath.stat` fault injection and the strict
  `assert attempts == [final]`.
- Treat path construction and containment resolution as separate concerns,
  already covered by their dedicated tests.

## Non-negotiable invariants

- Do not change `backend/dialogues/openclaw_receipts.py`.
- Do not change `AtomicReceiptStore`, consultation/kernel wrappers, production
  behavior, or error contracts.
- Preserve safe domain-error mapping and the no-artifact assertion.
- Do not touch Council Live View branches or PRs #71–#74.

## Important file

- `tests_dialogues/test_shared_receipt_store_parity.py`
