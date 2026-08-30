# Normal Socrates CLI

Normal Socrates is the ordinary interactive entry point for asking an arbitrary
question of the repository's full canonical three-model CED council. It is a
thin standard-library CLI over `CEDOrchestrator.run_registry_session()`; it does
not implement a second dialogue engine.

## Launch from PowerShell

Make the OpenRouter credential available through the repository's existing
secure environment setup; never place it in source control. From PowerShell,
the exact launch sequence is:

```powershell
cd "C:\Users\spirc\Desktop\Socrates-AI-Normal-Live"
py -3.12 -m socrates
```

Once PowerShell is in that worktree, `py -3.12 -m socrates` is the single
stable command used for each question.

The `SOCRATES_MAX_RUN_USD` maximum-run setting is optional; its default is USD
25.00. When set in the existing secure environment, it must be a positive
decimal USD amount with at most 12 decimal places. Normal mode refuses to run
while the shared `SOCRATES_DEBUG_PREDISPATCH` diagnostic switch is enabled,
because that switch can print private transport diagnostics.

## What happens

1. Type any nonblank question at `Ask Socrates:`.
2. The CLI performs an offline preflight. It shows the exact model pinned to
   each physical seat, confirms `FULL council: YES`, and reports 115 base calls,
   up to 20 same-seat CED retries, and a 135-call conservative maximum.
3. The CLI shows the exact conservative maximum cost and the configured standing
   cap. If the maximum is over the cap, the run stops before confirmation and no
   live runtime is constructed.
4. If the preflight is within the cap, type exactly `Y` or `YES`
   (case-insensitive) to authorize the live run. Every other response cancels.
5. Progress appears as short metadata-only labels such as `[Opening]`,
   `[Elenchus 1]`, `[Scoring]`, `[Ratification]`, and `[Governing release]`.
6. The console prints only the governing release notice and its authorized
   public answer. A blocked, unavailable, or inconsistent release fails closed:
   the internal assembled candidate is not printed.
7. The final line identifies the write-once `result.json` artifact under
   `runs\normal\<run-id>\`. The same directory also contains the offline
   `plan.json` and live claim/receipt evidence created by the runtime.

Preflight does not create provider adapters, read a credential, or make a
provider request. Provider dispatch is possible only after both the standing-cap
check and explicit `Y`/`YES` confirmation. The cost shown is a conservative
authorization ceiling; actual accepted calls and accounted spend are recorded in
the result artifact.

The exact question remains bound in memory to the canonical task, session ID,
UTF-8 byte length, and SHA-256 digest. Raw question text is deliberately not
copied into `plan.json` or `result.json`; the digest supplies artifact
provenance without turning normal run evidence into a store for pasted secrets.

The 135-call authorization is the full two-cycle ceiling. The runtime also
derives the legal one-cycle early-stop branch (89 base + 14 retry headroom =
103) and requires every pre-dispatch task to fit at least one branch. The
two-cycle branch remains the displayed and authorized maximum because it also
dominates the current conservative cost bound.

Visible answers and internal candidates pass through high-confidence secret
redaction for labelled credentials, sensitive environment assignments,
Authorization/Cookie headers, common provider token prefixes, credentialed
URLs, and PEM private keys. Terminal escape sequences and unsafe C0/C1 control
bytes are removed before that redaction and before console or artifact output.
This is defense in depth, not a secret manager: never paste credentials into a
question and never place them in source control.

## Current Normal council

The CLI derives this topology from the retained live policy and prints it before
authorization:

| Seat | Model |
| --- | --- |
| Alpha | `openai/gpt-5-mini` |
| Beta | `google/gemini-3.7-flash` |
| Gamma | `openai/gpt-4.1-mini` |

Normal Socrates preserves the canonical council's deterministic logical-role
rotation, full deliberation/scoring/assembly/ratification/governing path, current
same-seat retry semantics, and task-aware output budgets. In particular, the
GPT-5 mini initial-response tier remains 14,000 output tokens.

## Normal is not a Q2-Q7 benchmark runner

Normal mode accepts an arbitrary user question and writes only to
`runs\normal\`. It does not load a frozen question bundle, benchmark answer key,
experimental arm, manual score, or benchmark replay artifact.

The Q2-Q7 benchmark/lab scripts, frozen protocols, strict closure manifests, and
historical run artifacts remain separate. Use their dedicated documented runners
when reproducing a benchmark; do not use `py -3.12 -m socrates` as a benchmark
substitute.
