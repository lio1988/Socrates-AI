# Present State — `feature/openclaw-memory-ab-attestation`

Snapshot date: 2026-07-16  
PR: `#62 — Add bound single-agent Lesson A/B Memory attestation`  
Original remote PR head before handoff files: `0ea3bfb3dc4552616d44eda20a09fc67b107855b`  
Handoff head before this `PRESENT.md` commit: `659a71e8013b64e2638b6224966c2206c5f1a1cf`

Always verify the live head, base, mergeability, and commit graph before editing. This file records a snapshot, not an immutable ref.

## PR and stack state

At the initial verified inspection:

```text
PR: #62
state: open
draft: true
merged: false
mergeable: true
base: feature/openclaw-attestation-bridges
base SHA recorded by PR: 15483130d04bfe02a16efc3f589b8d78ff848210
remote head before handoff: 0ea3bfb3dc4552616d44eda20a09fc67b107855b
commits: 37
changed files: 15
additions: 2670
deletions: 13
```

PR #61 is now closed and merged into `main`:

```text
PR #61 merged: true
PR #61 head: f4caf3f75cef40f51c6963bf909ec85c8101a4b5
PR #61 merge commit: d2916038c8fdd633414d0a2d8dc0e272e9f2ec09
```

PR #62 still targets the historical feature branch and has not been cleanly retargeted to `main`.

## Verified divergence before handoff files

Comparison with the live feature-base branch reported:

```text
base: feature/openclaw-attestation-bridges
base head: f4caf3f75cef40f51c6963bf909ec85c8101a4b5
status: diverged
PR branch ahead: 37 commits
PR branch behind: 20 commits
merge base: 037595a7698e1aa706e72f8b95595a675a59636a
```

Comparison with current `main` reported:

```text
main head: b699dad275a9c8824811b0c7307a688f700d3eb2
status: diverged
PR branch ahead: 47 commits
PR branch behind: 10 commits
merge base: 8753c2c65697c1c4395a2674979a708d08ccd481
```

These counts were taken before the six handoff documentation files were added. Recompute before synchronization.

Do not infer that GitHub’s initial `mergeable: true` means the stack is ready. The base relationship is stale and the branch is behind both the feature base and `main`.

## Intended PR-owned files before handoff

The live PR listed fifteen changed files:

```text
backend/dialogues/openclaw_identity/governed_system.py
backend/dialogues/openclaw_identity/memory_evidence_binding.py
backend/dialogues/openclaw_identity/revision_registry_governed.py
backend/dialogues/openclaw_identity/revision_transaction_governed.py
backend/dialogues/openclaw_memory/__init__.py
backend/dialogues/openclaw_memory/lesson_loader.py
docs/openclaw_memory_lessons/AGENT_LESSON_AB_ATTESTATION.md
docs/openclaw_memory_lessons/G4_MEMORY_LIFECYCLE_BINDING.md
docs/openclaw_memory_lessons/OPERATOR_GUIDE.md
scripts/openclaw_attest_lesson_ab.py
tests_dialogues/test_openclaw_lesson_ab_attestation.py
tests_dialogues/test_openclaw_lesson_ab_attestation_provenance.py
tests_dialogues/test_openclaw_lesson_ab_experiment_manifest.py
tests_dialogues/test_openclaw_lesson_fingerprint.py
tests_dialogues/test_openclaw_memory_evidence_binding.py
```

The handoff added:

```text
AGENTS.md
CLAUDE.md
.agents/branches/feature-openclaw-memory-ab-attestation/README.md
.agents/branches/feature-openclaw-memory-ab-attestation/MEMORY.md
.agents/branches/feature-openclaw-memory-ab-attestation/PLANS.md
.agents/branches/feature-openclaw-memory-ab-attestation/PRESENT.md
```

These six files are documentation-only and do not change G4 runtime/operator behavior.

## Implemented on the inspected remote branch

The remote PR source contains:

- `memory_lesson_fingerprint()` over the complete canonical lesson record;
- strict-looking G4 envelope/manifest validation code;
- exact lesson, governed Identity, and experiment fingerprint binding;
- single-agent treatment/control causality checks;
- named non-self verifier binding;
- link and unlink evidence construction paths;
- immutable evidence-registry integration;
- `memory_ab_binding_marker()` and parser;
- current lesson/Identity binding checks for personal Memory proposals;
- governed facade plumbing for lesson fingerprint maps;
- evaluation/decision/application preflight integration;
- application binding before journal or Identity mutation;
- operator and lifecycle documentation;
- focused tests for attestation, provenance, manifest, lesson fingerprint, and lifecycle binding.

## Authority preserved by design

The attestation command is intended to create immutable evidence only.

It does not intentionally:

- run the experiment;
- edit the lesson catalogue;
- link or unlink Memory;
- create, evaluate, approve, or apply a proposal;
- mutate Identity;
- invoke a provider;
- change prompts, tools, roles, permissions, or CED authority.

This must be verified in code and tests after synchronization.

## Known remote concerns requiring audit

### Stale stack/base

PR #61 has merged but PR #62 remains stacked on the old feature branch. The first task is synchronization and diff isolation, not new feature work.

### CLI parsing boundary

The inspected remote patch for `scripts/openclaw_attest_lesson_ab.py` contains manual argument lookup helpers such as `_value(argv, name, default)`.

This does not by itself prove an exploitable defect, but it requires direct adversarial comparison against the strict `argparse` boundary established in PR #61. Abbreviations, duplicates, unknown options, equals-form inputs, option-shaped values, and parse-before-mutation behavior must be tested explicitly.

### Local-only work is not remote state

A later developer/agent report may describe a local merge commit or unstaged RED→GREEN fixes beyond remote head `0ea3bfb...`.

No such work is part of PR #62 unless the exact commits appear on the GitHub branch. Inspect local repositories separately and never report local-only fixes as pushed.

### Validation staleness

The PR body documents an intended local gate but does not provide GitHub CI statuses for the inspected remote head. The combined-status query returned no statuses.

The original PR body says to keep draft until all local tests pass. That requirement remains.

## Tests currently claimed by the PR

The PR body lists commands for:

- compile/import checks;
- focused attestation/fingerprint/manifest/evidence-builder tests;
- attestation bridge, script, and self-review regressions;
- complete `tests_dialogues`;
- full repository suite.

However, the PR body does not state final exact pass counts for the current remote head, and no CI statuses were observed.

For the six handoff files added after `0ea3bfb...`:

- no source behavior changed;
- no tests were run as part of their creation;
- no CI was triggered or observed by this handoff;
- no merge/rebase/retarget was performed.

Honest status:

```text
G4 source: implemented on remote branch
focused tests: present; current exact remote-head results not independently established here
full validation: not established for current synchronized target
PR state: draft
stack synchronization: required
retarget to main: not performed
shipped: no
```

## Known risks

- stale stacked base may hide conflicts or duplicate already-merged PR #61 content;
- branch is behind current `main`;
- manual CLI parsing may permit ambiguous operator inputs unless proven strict;
- lesson/Identity/manifest binding must remain exact after conflict resolution;
- unlink must use fingerprints for all current curated lessons, not stable lessons only;
- failed application preflight must leave no journal or Identity mutation;
- transaction recovery must not become a fresh approval or re-evaluation;
- exact replay and conflicting reference reuse must remain distinct;
- docs and commands may become stale after parser hardening or synchronization;
- local-only fixes may be confused with remote state;
- no current GitHub CI status proves the branch.

## Exact next action

Perform `PLANS.md` Gate 0 only:

1. inspect the live remote commit graph after the handoff commits;
2. inspect any local checkout for unpushed merge/fix work and record it separately;
3. identify exactly why the branch is behind the old feature base by twenty commits and current `main` by ten commits at the last comparison;
4. reconstruct the intended PR #62-only diff on top of merged PR #61;
5. write a reversible synchronization/retarget plan with recovery SHAs;
6. do not change code or PR base until that plan is reviewed.

## Handoff completion rule

The next agent must update this file before stopping with:

- exact local and remote head SHAs;
- current PR base and mergeability;
- synchronization action taken;
- files changed;
- tests and exact pass/fail counts;
- unresolved findings;
- one next action.
