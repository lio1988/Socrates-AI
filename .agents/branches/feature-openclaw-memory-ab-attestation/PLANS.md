# Plans — `feature/openclaw-memory-ab-attestation`

This file describes future work. Nothing here is implemented merely because it is listed.

## End-state

Deliver a clean PR #62 against merged `main` that adds only the strict G4 single-agent Lesson A/B Memory evidence bridge and its current-state lifecycle binding, with no direct Memory/Identity mutation and no duplicated PR #61 scope.

## Ordered implementation plan

### Gate 0 — Establish remote truth and stack state

Before editing behavior:

1. fetch the live PR #62 head and base;
2. inspect the current head of `feature/openclaw-attestation-bridges`;
3. confirm PR #61 is merged into `main` and record its merge commit;
4. inspect all commits by which PR #62 diverges from both its feature base and `main`;
5. distinguish remote commits from any local-only merge, unstaged, or uncommitted fixes;
6. identify the exact intended fifteen-file G4 diff after removing already-merged PR #61 content;
7. choose an explicit synchronization strategy and recovery point.

Do not retarget, rebase, merge, or force-push until this analysis is written into `PRESENT.md`.

Acceptance:

- exact base/head/merge-base are recorded;
- intended PR-owned files are listed;
- no local-only fix is claimed as remote;
- synchronization plan is reversible and reviewed.

### Gate 1 — Safe synchronization and retarget preparation

Because PR #61 has merged, create a clean branch state that preserves PR #62-owned work on top of the current intended `main` baseline.

Possible strategies must be evaluated, not assumed:

- merge current `main` into the feature branch;
- rebase the PR-owned commits onto `main`;
- reconstruct/cherry-pick the exact PR-owned diff onto a clean branch and update the PR safely.

Selection criteria:

- smallest understandable history;
- no loss of reviewed PR #62 changes;
- no resurrection of removed PR #61 preliminary G4 code;
- no duplicate PR #61 diff;
- deterministic testability;
- explicit rollback SHA.

After synchronization:

1. compare the branch against `main`;
2. verify only intended files remain;
3. resolve conflicts with semantic review, not automatic preference;
4. update PR #62 base to `main` only when the branch diff is clean;
5. update the PR body with the new base/head and validation truth.

Acceptance:

- branch is no longer behind the selected base;
- PR diff is branch-owned and reviewable;
- PR remains draft until all gates pass.

### Gate 2 — Strict CLI boundary audit

Audit `scripts/openclaw_attest_lesson_ab.py` as an adversarial command-line boundary.

The current remote patch visibly contains manual option lookup helpers. Compare the actual branch implementation against the strict CLI standards established by PR #61.

Required properties:

- explicit parser with `allow_abbrev=False` or an equivalently strict proven boundary;
- one required positional `agent_id`;
- required `--report`, `--action`, and `--verified-by`;
- explicit action vocabulary;
- no abbreviated, duplicated, missing, option-shaped, unknown, irrelevant, or equals-form ambiguity unless intentionally supported and tested;
- parse and envelope validation before Identity/evidence registry mutation;
- deterministic non-zero refusal with no traceback for expected operator errors;
- no trusted values inferred from ambiguous token position;
- local-file-only, UTF-8 JSON object, bounded size, no URL support;
- no secret-shaped data or non-finite values.

Acceptance:

- deterministic RED→GREEN tests for every parser ambiguity found;
- no registry/profile artifacts on parser refusal;
- exact valid commands remain supported.

### Gate 3 — Attestation envelope and manifest audit

Audit the complete `openclaw_agent_lesson_ab_attestation_v1` contract.

Verify:

- exact envelope field set;
- exact nested report field set;
- exact experiment-manifest field set;
- exact control/treatment, judge, and compute-budget subfields;
- canonical JSON hashing with sorted keys, compact separators, UTF-8, and `allow_nan=False`;
- all external digests are lowercase SHA-256;
- lesson, Identity, and experiment fingerprints are recomputed rather than trusted;
- target agent, lesson ID, verifier, date, source, and scope all bind consistently;
- question hashes, seeds, arm order, counterbalancing, provider IDs, judge set, and budgets are causally coherent;
- whole-council and bare personal reports fail closed;
- self-attestation and self-judging fail closed;
- link and unlink verdict semantics are coherent.

Acceptance:

- field addition/removal/change tests;
- changed lesson content/status under same ID refusal;
- changed governed Identity refusal;
- changed manifest/fingerprint refusal;
- exact idempotent replay and conflicting reference refusal;
- no unbounded input or secret leakage.

### Gate 4 — Current-state lifecycle binding audit

Audit binding across:

```text
submit -> evaluate -> decide -> transactional apply
```

Verify:

- Memory proposals require bound single-agent evidence;
- submit compares evidence Identity binding against the self-review snapshot;
- evaluate and decide require the current complete lesson fingerprint map;
- application rechecks current lesson and governed Identity before journal/profile mutation;
- stale lesson or Identity fails closed;
- missing map fails closed;
- generic evidence errors remain distinct from binding errors;
- non-Memory proposals remain backward-compatible;
- duplicate active proposal and causal-isolation rules remain intact;
- unlink can address deprecated-but-currently-curated linked lessons;
- transaction recovery completes only preflighted prepared intent.

Acceptance:

- no journal or Identity mutation on failed preflight;
- valid link reaches probation only through existing governance;
- valid unlink/reversal semantics remain canonical;
- existing Identity/Soul and unrelated proposal tests stay green.

### Gate 5 — Evidence and persistence integration audit

Verify all evidence conversion still passes through the existing hardened strict builder and append-only registry.

Required properties:

- action-specific supports are exact;
- source marker commits lesson, Identity, and experiment fingerprints;
- exact rerun is idempotent;
- conflicting reference reuse is refused;
- no mutable overwrite or deletion path;
- no provider/network call;
- no direct proposal or profile mutation;
- verifier provenance remains named and non-self.

Acceptance:

- mixed existing/new evidence registry tests pass;
- no partial record after expected failure;
- persisted records verify on reload.

### Gate 6 — Documentation and operator truth

Synchronize:

- `AGENT_LESSON_AB_ATTESTATION.md`;
- `G4_MEMORY_LIFECYCLE_BINDING.md`;
- `OPERATOR_GUIDE.md`;
- PR #62 body;
- this branch handoff workspace.

Documentation must clearly distinguish:

```text
whole-council lesson_ab_v2 -> global curation evidence only
single-agent G4 envelope  -> personal Memory evidence candidate
immutable evidence        -> not Memory mutation
```

Document both catalogue inputs correctly:

- `stable_lesson_ids` for new links;
- fingerprints for all current curated lessons, including deprecated lessons needed for unlink.

Acceptance:

- commands match the actual strict parser;
- schemas match actual code;
- current remote status and test results are exact;
- no claim says shipped before merge.

### Gate 7 — Validation ladder

Run on the synchronized real branch checkout.

Minimum commands:

```powershell
.\.venv\Scripts\python.exe -m compileall backend\dialogues\openclaw_memory\lesson_loader.py scripts\openclaw_attest_lesson_ab.py
.\.venv\Scripts\python.exe -c "from backend.dialogues.openclaw_memory import memory_lesson_fingerprint; print('IMPORT OK')"
.\.venv\Scripts\python.exe -m pytest tests_dialogues\test_openclaw_lesson_fingerprint.py tests_dialogues\test_openclaw_lesson_ab_attestation.py tests_dialogues\test_openclaw_lesson_ab_attestation_provenance.py tests_dialogues\test_openclaw_lesson_ab_experiment_manifest.py tests_dialogues\test_openclaw_memory_evidence_binding.py -q
.\.venv\Scripts\python.exe -m pytest tests_dialogues\test_openclaw_revision_evidence_builders.py tests_dialogues\test_openclaw_attest_evidence_script.py tests_dialogues\test_openclaw_attestation_bridges.py tests_dialogues\test_openclaw_review_self_revision.py -q
.\.venv\Scripts\python.exe -m pytest tests_dialogues -q
.\.venv\Scripts\python.exe -m pytest -q
```

Also run transaction/recovery and parser-specific tests added during review.

Acceptance:

- exact pass/fail counts recorded;
- no new warnings from changed files without explanation;
- environment-only failures proven in isolation before dismissal;
- no CI status implied when none exists.

### Gate 8 — Independent adversarial review

Review at minimum:

- parser ambiguity and option smuggling;
- path/URL/size/encoding boundaries;
- secret and non-finite data detection;
- manifest causality and counterbalancing;
- same-ID changed-lesson attacks;
- stale governed Identity;
- self-attestation/self-judging normalization;
- exact replay versus conflict reuse;
- stale map at evaluation, decision, and application;
- pre-journal/pre-Identity failure atomicity;
- recovery semantics;
- scope leakage into direct Memory mutation or authority.

All CRITICAL/HIGH/MEDIUM findings must be reproduced and closed with deterministic tests before readiness.

### Gate 9 — Retarget and readiness decision

Only after Gates 0–8:

1. confirm PR #62 diff against `main` is exact;
2. retarget to `main` if not already done;
3. update PR body with final head/base, scope, review history, and validation;
4. keep draft if any gate remains incomplete;
5. mark ready only when mergeability, tests, and independent review are clean.

Do not merge automatically.

## Explicit non-goals

Do not:

- run the actual experiment inside the attestation command;
- add live providers;
- mutate `.env` or dependencies;
- directly edit Memory or Identity;
- create/approve/apply proposals inside evidence registration;
- add CED authority;
- combine PR #62 with Agent Prompt v2, Micro-Socratic runtime activation, or unrelated features;
- rewrite evidence history;
- accept whole-council evidence for personal Memory;
- treat local-only work as pushed.

## Next exact action

Perform Gate 0 only:

1. inspect the exact remote commit graph;
2. identify the ten commits by which the branch is behind current `main` and the twenty commits by which it is behind the old feature-base head at the last comparison;
3. map those commits to PR #61 merge history and later main changes;
4. inspect whether any known local fix commit or unstaged work exists outside GitHub;
5. write the safe synchronization strategy into `PRESENT.md` before changing code or PR base.
