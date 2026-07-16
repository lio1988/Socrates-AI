# Socrates AI Coding-Agent Operating Contract

This file governs coding-agent work in this repository. It is written for Claude
Code, Cursor, Codex, and other tool-using software agents.

The objective is not to produce the largest diff or the cleverest abstraction.
The objective is to make the smallest correct, test-backed, auditable change that
preserves the epistemic and governance invariants of Socrates AI.

## 1. Read before writing

Before changing code:

1. identify the current branch, HEAD, and working-tree state;
2. read the complete relevant implementation, tests, and nearby documentation;
3. trace actual imports, call sites, schemas, and persisted artifacts;
4. state the intended scope and concrete success criterion;
5. distinguish what is implemented on the current branch from what exists only in
   another PR, branch, design note, or future plan.

Never invent an API, field, status, command, file, or architectural capability.
Search the repository and verify it.

The root `README.md` is the canonical project overview. The detailed technical and
historical reference is `backend/dialogues/README.md`. Focused governance documents
under `docs/` are authoritative for their own contracts.

## 2. Canonical architecture boundary

The current governed engine lives under `backend/dialogues/`.

- `CEDOrchestrator` is the sole execution and reasoning-protocol authority.
- Socratic agents are stateless contributors that receive structured tasks and
  return structured moves.
- Provider adapters execute model calls; they do not decide protocol state.
- Peer agents/providers supply qualitative judgments.
- CED validates, aggregates, routes, records, and enforces the protocol
  mechanically.
- Council Ratification is council-wide governance, not a permanent chairman or
  Final Evaluator monopoly.

The older `socrates_ai.py`, `backend/orchestrator/`, and historical frontend
prototypes are pattern donors only. Do not treat them as the canonical authority
or silently wire new production behavior through them.

## 3. Permanent epistemic invariants

A change is invalid if it causes CED to:

- fabricate a qualitative score;
- replace a missing score with zero or another synthetic value;
- silently drop a failed, timed-out, malformed, or unavailable provider;
- allow an agent to score its own output;
- expose hidden scores, rankings, scorer identities, provider mappings, or audit
  internals to deliberating agents;
- treat agreement, popularity, or model rank as truth;
- grant one permanent model final authority;
- override a structurally valid critical blocking objection;
- mutate Memory, Identity, Soul, prompts, or governance state outside the governed
  evidence and attestation path;
- use self-recommendation, self-consultation, self-scoring, or self-attestation as
  approval.

Invalid or unavailable evidence remains invalid or unavailable. Report honest
statuses such as `missing`, `partial`, `timeout`, `failed`, `disabled`, or
`quorum_failed` rather than concealing the failure.

## 4. Determinism and reproducibility

Preserve deterministic behavior wherever the protocol claims determinism.

- Role assignment must remain independent of provider latency and completion
  order.
- Task, move, event, and receipt identifiers must use their documented canonical
  inputs and stable ordering.
- Do not introduce dependence on wall-clock time, unordered iteration, process
  scheduling, random provider completion order, or ambient global state unless the
  contract explicitly requires and records it.
- Do not replace stable hashing or canonical serialization casually.
- New nondeterminism must be explicit, bounded, testable, and represented in audit
  metadata.
- Exact reruns may be idempotent. Conflicting reuse of an immutable identity or
  receipt must fail closed.

When editing deterministic code, add tests that vary ordering, timing, or repeated
execution where those differences could reveal drift.

## 5. Provider integrity and fail-closed execution

Provider failures are protocol data, not inconveniences to hide.

For current and future provider integrations:

- never silently substitute another model;
- never silently activate an automatic model selector or fallback;
- pin the exact requested model ID where exact identity matters;
- fail closed when the required model is unavailable;
- verify and record the model actually returned;
- retain immutable provider receipts for governed or reproducibility-sensitive
  paths;
- for strict reproducibility, pin or allowlist the upstream provider route when
  supported;
- preserve bounded timeout, retry, and call-budget rules;
- never log or commit API keys, authorization headers, private prompts, or secrets.

Any repair or retry behavior must be explicit in the schema and audit trail. A
retry must not turn a failed call into an untraceable success.

## 6. Governance, learning, and lasting change

Learning components may produce lessons, telemetry, hypotheses, candidate evidence,
or proposals. They may not silently rewrite the system.

Lasting changes to Memory, Identity, Soul, prompts, governance, or agent profiles
must preserve the repository's governed lifecycle, including the applicable parts
of:

```text
verified observation
    -> retained tamper-evident artifact
    -> named non-self attestation
    -> immutable evidence record
    -> bounded self-review
    -> strict proposal
    -> independent evaluation
    -> named non-self approval
    -> recoverable application
    -> probation
    -> confirmation or governed rollback
```

Do not collapse distinct stages merely because one component can technically write
all of them. Producer, evaluator, approver, and applier identities must remain
separate where the contract requires separation.

Runtime-inert foundations must remain runtime-inert unless the requested scope
explicitly authorizes their integration and the integration has dedicated tests.
Documentation must accurately label features as implemented, open draft, planned,
or historical.

## 7. Change discipline

Prefer a surgical change over a broad rewrite.

- Modify only files required by the task.
- Do not perform unrelated refactors, formatting sweeps, renames, dependency
  upgrades, or cleanup.
- Reuse an existing abstraction only after confirming that its semantics match the
  new use case.
- Do not create a generic framework for one concrete need.
- Do not add configuration flags for hypothetical future variants.
- Avoid new dependencies when the standard library or existing dependency set is
  sufficient.
- If a new dependency is truly necessary, explain the need, security impact,
  maintenance cost, and lockfile consequences.
- Preserve public schemas and persisted artifact compatibility unless the task
  explicitly requires a versioned migration.
- Prefer additive, versioned changes over in-place semantic mutation of immutable
  or externally consumed records.

Keep the diff reviewable. If the implementation starts spreading into unrelated
subsystems, stop and reassess the design.

## 8. Bug-fix protocol: RED -> GREEN -> regression

For a reproducible bug:

1. add or identify a focused test that fails for the correct reason;
2. run it and record the failure;
3. implement the smallest root-cause fix;
4. rerun the focused test and confirm it passes;
5. run the relevant surrounding suite;
6. run the full canonical suite when the change can affect shared behavior.

Do not weaken, delete, skip, xfail, or over-mock a valid test merely to obtain green
output. Do not change expected values until you have proved that the previous
contract was wrong.

For new behavior, tests must cover the success path and the most important failure
or boundary path. Governance changes require negative tests showing that bypasses
remain impossible.

## 9. Validation commands

From the repository root, the canonical regression suite is:

```bash
python -m pytest tests_dialogues -q
```

On Windows with the repository virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest tests_dialogues -q
```

Run the narrowest relevant tests first, then broaden. Report the exact command and
result. Never state that tests passed if they were not run successfully in the
current worktree and environment.

Useful deterministic smoke paths include:

```bash
python -m backend.dialogues.demo
python -m backend.dialogues "Is mathematics discovered or invented?"
```

Do not activate live-provider tests, spend API credits, or depend on network access
unless the user explicitly requests it and all repository gates are satisfied.
Offline and deterministic execution is the default.

## 10. Security and privacy

- Never read, print, modify, stage, or commit `.env` unless the user explicitly
  requests a local-only environment edit and the file remains uncommitted.
- Never place provider keys or secrets in source, HTML, frontend code, tests,
  fixtures, prompts, receipts, logs, screenshots, or documentation.
- Do not persist hidden chain-of-thought or private scratchpads as
  authority-bearing artifacts.
- Do not transfer raw private scratchpads between agents or consultation services.
- Sanitize exception messages and receipts when upstream payloads may contain
  secrets.
- Treat immutable evidence and receipts as append-only. Refuse conflicting writes
  rather than overwriting history.

## 11. Git and publication safety

Before staging anything, inspect the full status and diff.

- Never stage unrelated user changes.
- Prefer explicit file paths over `git add -A` in a mixed worktree.
- Do not amend, rebase, reset, force-push, delete branches, or rewrite history
  unless explicitly requested.
- Do not commit, push, open a PR, merge, or modify GitHub state unless the user has
  explicitly authorized that action.
- When authorization is limited to commit or push, do not infer authorization to
  merge.
- Preserve the user's current branch and uncommitted work.
- Confirm the remote branch points to the commit you claim was pushed.

A commit should contain one coherent change and a terse, accurate message.

## 12. Completion report

At the end of a coding task, report:

- the exact files changed;
- the behavior added or corrected;
- why the change is minimal and compatible with the architecture;
- tests and checks actually run, with results;
- remaining risks, limitations, or deliberately untouched work;
- branch, commit SHA, and PR state only when those actions occurred.

Separate verified facts from assumptions. Do not use confident language to hide
missing evidence.

## 13. Stop conditions

Stop and surface the conflict instead of guessing when:

- the requested behavior violates a permanent invariant;
- the same persisted schema has incompatible definitions in authoritative files;
- the task requires secrets or permissions that are unavailable;
- a destructive Git operation would be needed without explicit permission;
- the repository state contains unrelated changes that cannot be safely isolated;
- a test failure reveals that the proposed fix changes a wider contract than the
  requested scope.

A partial, honest result is better than a broad unverified rewrite.

---

Core rule:

> Read the real system. Preserve the invariants. Make the smallest correct change.
> Prove it with evidence. Never hide failure.
