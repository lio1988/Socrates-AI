# OpenRouter wire-source retrieval recovery v1r1

This branch changes only the execution environment of the sealed six-source
retrieval plan. It starts from the pushed Phase 8.5D-S checkpoint
`a37e6c0068e3132ca49128295a5ef8453f91592c`.

## Frozen boundary

- The Phase 8.5D-S result remains `FALSIFIED` and its files are hash-locked.
- The source plan remains exactly six official `openrouter.ai` locators.
- No seventh or substitute source is permitted.
- Retry count remains zero.
- No credential, authenticated API, provider inference, model, paid request,
  runtime tool, parser, adapter, or CED call is authorized.
- The sealed v1 retrieval log is never overwritten.
- The new execution publishes `openrouter_wire_retrieval_log_v1r1.json` and a
  separate content-addressed recovery receipt.

## One local command

After checking out this branch on the existing Windows repository:

```powershell
.\.venv\Scripts\python.exe scripts\acquire_socrates_zero_openrouter_wire_spec_sources_v1r1.py --root .
```

Exit `0` means all six sources were retained. Exit `1` means the new retrieval
completed but remained incomplete. Exit `2` is a contract/preflight failure.
The command cannot repeat network retrieval after its new log exists; a later
invocation performs offline receipt verification only.
