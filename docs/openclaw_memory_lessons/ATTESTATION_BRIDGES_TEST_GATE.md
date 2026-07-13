# Attestation Bridges — Local Verification Gate

Run from the repository root. No provider or API credentials are required.

## Syntax and imports

```powershell
.\.venv\Scripts\python.exe -m compileall scripts\openclaw_attest_evidence.py scripts\openclaw_review.py
.\.venv\Scripts\python.exe -c "import backend.dialogues.openclaw_identity as m; print('IMPORT OK')"
```

## Focused tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests_dialogues\test_openclaw_attest_evidence_script.py tests_dialogues\test_openclaw_attestation_bridges.py tests_dialogues\test_openclaw_review_self_revision.py -q
```

## Related governed regression tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests_dialogues\test_openclaw_revision_evidence.py tests_dialogues\test_openclaw_self_review_script.py tests_dialogues\test_openclaw_status.py tests_dialogues\test_openclaw_causal_isolation.py -q
```

## Full gate

```powershell
.\.venv\Scripts\python.exe -m pytest tests_dialogues -q
.\.venv\Scripts\python.exe -m pytest -q
```

Do not merge if any test fails. Fix production root causes; update a test only
when it encodes an obsolete expectation that conflicts with the documented
security invariant.
