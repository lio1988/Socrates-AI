# PLAN — fix/openrouter-wire-spec-acquisition-timestamp-race

## Success criterion

`acquire_openrouter_wire_spec_sources_v1` produces a valid retrieval log even
when the wall clock advances between every read, and the retrieval log contract
is unchanged.

Concretely: a regression test that advances `_utc_now()` by one second on every
call must pass, and must fail without the fix with the exact production error
`retrieval event and snapshot bytes diverge`.

## Scope

- One clock read per source in the acquisition loop.
- The regression test.
- Branch documentation.

## Non-goals

No contract change, no `_utc_now()` precision change, no `_failure_event` change,
no touching of the Socrates-Zero OpenRouter pre-live modules or the S6 test file,
no regeneration of retained evidence, no push.

## Ordered steps

1. **Verify** the diagnosis against the source before editing — confirm both
   clock reads, the one-second format, and the contract equality check. *Done.*
2. **Isolate** the work in a git worktree so the frozen S6 checkout is untouched.
   *Done.*
3. **Write the failing test first** and watch it fail with the production error.
   *Done — failed with "retrieval event and snapshot bytes diverge".*
4. **Fix** by reading the clock once per source and reusing the value. *Done.*
5. **Watch the test pass** and confirm the contract file is untouched. *Done.*
6. **Run** the validation gates. *Done.*
7. **Document** the branch and commit. *Done.*
8. **Stop.** Do not push.

## Validation gates

| gate | required | observed |
| --- | --- | --- |
| acquisition test module | all pass | **4 passed** |
| regression test without the fix | fails with the production error | **confirmed** |
| full `tests_dialogues` on this branch | exit 0 | **3122 passed, 10 skipped, exit 0** |
| `git diff --check` | PASS | **PASS** |
| retrieval log contract file | unchanged | **unchanged** |
| files touched | 2 source + branch docs | **2 source + 4 docs** |

## Stop conditions

Falsify rather than proceed if the fix requires relaxing the contract's equality
check, if a single clock read cannot satisfy `completed_utc >= started_utc`, or
if any retained evidence would have to be regenerated. None triggered.
