# Private backup, and a separate public showcase

Two repositories doing two jobs. Preparation only — nothing here has been
pushed, and no repository has been created.

## 1. Private backup of the authoritative repository

The core stays private. Not because the ideas are secret, but because the
prompts, the scoring internals, the corroboration rules and the authorization
machinery are the parts an adversary would study to defeat the guarantees the
product makes.

### What to push

- Branch: `feature/agent-quality-minimal-fix-v1`
- The current clean checkpoint, and nothing uncommitted.

### What must stay out of Git

`.gitignore` already excludes `*.md` wholesale and the `authorization/` and
`runs/` paths, so tracked documentation and the authorization manifest exist
only because they were force-added deliberately. Keep it that way, and keep
these out:

| Stays local | Why |
| --- | --- |
| `runs/**` in every worktree | Live-run artifacts. They are evidence, not source, and they belong beside the machine that produced them. |
| `.env`, any file holding `OPENROUTER_API_KEY` | A credential in history is a credential forever. |
| `C:\Users\spirc\Documents\SOCRATES_*` | The operator authorization records and handoffs. |
| Scratchpad helpers | The manifest generator and audit scripts live outside the repo on purpose. |
| `__pycache__`, `*.pyc` | The source verifier refuses them beside authorized sources. |

### Procedure

```bash
# 1. Confirm the checkpoint is exactly what you intend to publish privately.
git -C <repo> status --porcelain --untracked-files=all   # must be empty
git -C <repo> log --oneline -5

# 2. Confirm nothing secret-shaped is tracked.
git -C <repo> grep -nE "sk-or-v1-[A-Za-z0-9]{20,}|OPENROUTER_API_KEY *= *['\"]" -- . || echo clean

# 3. Create the repository on GitHub as PRIVATE, empty, no README.

# 4. Add it and push the one branch.
git -C <repo> remote add origin git@github.com:<owner>/<private-repo>.git
git -C <repo> push -u origin feature/agent-quality-minimal-fix-v1
```

Push nothing else. No tags, no other branches, and no `--mirror`: the local
candidate and verification worktrees are working state, not history worth
publishing.

**Verify the repository is private before the first push, not after.** A
repository that was briefly public must be treated as fully disclosed.

## 2. Public showcase repository — separate, and later

A second, genuinely public repository that explains the product without
shipping the mechanism. **Do not create it without explicit authorization.**

### Suggested contents

```
README.md          product explanation, honest capability claims
docs/              architecture at a level a reader can reason about
media/             logo, screenshots, the seven-phase diagram
web-demo/          a static Demo-Mode-only frontend, no backend
```

### May include

- The logo, screenshots and the phase diagram.
- What a council is, and why rotating roles matter.
- High-level architecture: seats, phases, governed synthesis.
- Selected run summaries — outcome, phases, ratification status, spend bound —
  provided they are already public projections.
- A Demo Mode frontend that runs entirely in the browser.

### Must never include

- CED implementation, phase scheduling or role rotation code.
- Prompts, of any kind.
- Scoring, corroboration, verification or governing-release internals.
- Authorization manifests, the source verifier, or any path list.
- The OpenRouter transport, request rendering or provider policy.
- Private tests, benchmark harnesses or retained provider evidence.
- Secrets, filesystem paths, machine names or operator records.

### The claim discipline carries over

The showcase inherits the same rule as the product interface: multiple model
seats, separately dispatched model turns, rotating Socratic roles, governed
synthesis, public reasoning. Not guaranteed truth, not AGI, not "always
different models", and no provider-independence claim the topology does not
prove.

A screenshot showing a real run must show a real outcome — including a
`release_unresolved` or a withheld candidate. A showcase that only ever shows
the happy path is advertising, and this project's whole argument is that the
unhappy path is the interesting one.
