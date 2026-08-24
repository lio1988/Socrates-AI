# fix/socratic-acceptance-contract

## Current checkpoint

DONE: completed the separate epistemic-marker milestone. The canonical
`marker_is_contracted(task_kind)` predicate now governs prompt and parser;
deliberative moves reject missing, non-string, or non-canonical markers, and
evaluative moves reject semantically misplaced markers. Deterministic and
canned fixtures now emit canonical markers only for contracted tasks. Marker
data remains advisory and has no CED authority.

TESTS:

- focused marker/acceptance/firewall/policy/learning bundle: `190 passed`;
- direct parser/provider transport bundle: `130 passed`;
- end-to-end custom-provider bundle: `104 passed`;
- full `tests_dialogues`: `2066 passed, 1 skipped`;
- repository-wide: `2373 passed, 1 skipped, 23 pre-existing warnings`.

FILES CHANGED:

- `backend/dialogues/provider_registry.py`;
- `backend/dialogues/reasoning_prompts.py`;
- `backend/dialogues/README.md`;
- marker contract tests plus deterministic/canned provider fixtures across the
  dialogue suite;
- branch README, MEMORY, PLAN, PRESENT.

COMMIT: `5d248c3` (`fix: enforce epistemic marker contract`). The preceding
acceptance implementation remains `6d352de` and its checkpoint is `25d5086`.

KNOWN ISSUES: the 23 warnings are pre-existing Pydantic `.dict()` deprecations
and duplicate FastAPI operation IDs. No live external call was made.

NEXT: integrate the reviewed acceptance and marker commits into
`feature/socrates-zero-search-v0` by cherry-pick, then rerun focused and full
regressions there.
