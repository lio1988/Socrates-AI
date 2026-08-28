# MEMORY — fix/openrouter-wire-spec-acquisition-timestamp-race

## Source checkpoint

- Base branch: `feature/socrates-zero-openrouter-wire-spec-evidence-v2r1`
- Base commit: `0d09822` — the branch that owns the acquisition script and the
  retrieval log contract.
- The three affected files are byte-identical at this base and at the current
  S6 branch head, so the fix applies cleanly to both lineages.

## The diagnosis, verified before changing anything

`_utc_now()` (script line 269) formats at **one-second precision**:

    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

Inside one iteration of the acquisition loop the clock was read twice:

| read | line | becomes |
| --- | --- | --- |
| first | ~1232 | `snapshot.retrieved_utc`, via `_build_retained_bundle` |
| second | ~1268 | `event.completed_utc` |

`OpenRouterWireRetrievalLogV1` (contract line ~1394) requires
`snapshot.retrieved_utc == event.completed_utc` and otherwise raises
**"retrieval event and snapshot bytes diverge"**.

Between the two reads the script writes the retained bundle to disk. When that
write is slow — a loaded machine, a full test suite — a second boundary can land
between the reads, the two strings differ, and the entire log refuses to
construct. Intermittent by nature: it passes standalone and usually passes in the
suite.

## Non-negotiable invariants

1. **The contract check is correct and must not be weakened.** Requiring the
   snapshot and its event to agree is exactly the kind of cross-check that caught
   this. Relaxing it to "within one second", or dropping it, would trade a
   visible intermittent failure for a silent inconsistency in retained evidence.
2. **One clock read per source.** The snapshot timestamp and the event's
   completion timestamp are the same fact and must come from the same read.
3. **Ordering still holds.** The single read happens after `started_utc`, so the
   event contract's `completed_utc >= started_utc` check is still satisfied.
4. **`_failure_event` is deliberately untouched.** Failure events carry no
   snapshot, so no equality constraint applies to them; changing it would widen
   the diff without cause.
5. **No retained evidence is regenerated.** This changes how a *future*
   acquisition run stamps its log, not anything already written.

## Why not "just retry"

The failure is not transient in the sense that retrying fixes the data — the run
has already produced two mutually inconsistent timestamps for one event. Retrying
would re-run a network acquisition to paper over an arithmetic-free bug in local
bookkeeping.

## Test technique

The regression test monkeypatches `acquire._utc_now` with a counter that advances
**one second on every call**. That is the worst case a real clock can produce, so
it turns a rare race into a deterministic failure. Without the fix it reproduces
the exact production error; with the fix the log builds and every snapshot's
`retrieved_utc` equals its event's `completed_utc` by construction.

## Environment

Repository `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish`, worked
through a separate git worktree so the frozen S6 checkout is never touched;
interpreter `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe`;
`PYTHONPATH` at the worktree root. `.gitignore` ignores `*.md` and `*.json`, so
documentation needs `git add -f`.

A worktree under the session scratchpad exceeded the Windows path limit and
failed to check out; a short path (`C:\Users\spirc\AppData\Local\Temp\wt-tsr`)
works.
