# Upload the completed Phase 8.5D-S ZIP from Windows

This procedure uses a separate temporary clone. It does **not** switch branches,
stash, reset or otherwise change the active repository at:

`C:\Users\spirc\Desktop\Socrates-AI-OpenRouter`

## 1. Download the completed ZIP from the ChatGPT conversation

Save it as:

`C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-phase8_5ds-completed.zip`

Expected SHA-256:

`6cdd1115c3deae951384dc0e12c523d9a7d1a47098ae3caf1e379330b763256a`

Verify it:

```powershell
(Get-FileHash `
  -Algorithm SHA256 `
  -LiteralPath "C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-phase8_5ds-completed.zip"
).Hash.ToLowerInvariant()
```

Do not continue unless the result is exactly the expected SHA-256.

## 2. Create a temporary delivery clone

Open PowerShell at the Desktop and run:

```powershell
cd "C:\Users\spirc\Desktop"

Remove-Item `
  -LiteralPath ".\Socrates-AI-phase8_5ds-delivery" `
  -Recurse -Force -ErrorAction SilentlyContinue

git clone `
  --branch "deliverables/socrates-zero-phase8-5ds" `
  --single-branch `
  "https://github.com/lio1988/Socrates-AI.git" `
  ".\Socrates-AI-phase8_5ds-delivery"

cd ".\Socrates-AI-phase8_5ds-delivery"
```

## 3. Copy, verify, commit and push the ZIP

```powershell
$source = "C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-phase8_5ds-completed.zip"
$destination = ".\deliverables\phase8_5ds\Socrates-AI-OpenRouter-phase8_5ds-completed.zip"

Copy-Item -LiteralPath $source -Destination $destination -Force

$expected = "6cdd1115c3deae951384dc0e12c523d9a7d1a47098ae3caf1e379330b763256a"
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()

if ($actual -ne $expected) {
    throw "SHA-256 mismatch. Expected $expected, got $actual"
}

git add -- "deliverables/phase8_5ds/Socrates-AI-OpenRouter-phase8_5ds-completed.zip"
git commit -m "chore: add completed Phase 8.5D-S snapshot"
git push origin "deliverables/socrates-zero-phase8-5ds"
```

## 4. Confirm

```powershell
git status --short --branch
```

Expected tracked status: clean.

The active project worktree and these protected untracked files remain untouched:

- `scripts/live_dialogue.py.bak`
- the malformed root filename beginning `ocratic_followup_mandate`
