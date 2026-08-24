# fix/socratic-acceptance-contract

## Current checkpoint

DONE: verified baseline ancestry, added phase-aware deterministic Socratic
content validation, applied it before CED move acceptance, made the offline
scripted provider obey the same contract, and added negative/end-to-end tests.

TESTS:

- acceptance/firewall/policy: `87 passed`;
- acceptance plus retry/identity/registry/live-view/Hybrid shadow:
  `131 passed`;
- full `tests_dialogues`: `2064 passed, 1 skipped`;
- repository-wide: `2359 passed, 1 skipped, 23 pre-existing warnings`.

FILES CHANGED:

- `backend/dialogues/socratic.py`;
- `backend/dialogues/ced.py`;
- `backend/dialogues/provider_registry.py` (offline mock fixture only);
- `tests_dialogues/test_socratic_acceptance_contract.py`;
- branch README, MEMORY, PLAN, PRESENT.

COMMIT: `6d352de` (`fix: enforce Socratic move acceptance contract`).

KNOWN ISSUES: marker omission/malformed-marker acceptance is intentionally
unchanged until the separate marker milestone. No live external call was made.

NEXT: enforce the already-documented marker contract in a separate atomic
change.
