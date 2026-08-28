# Controlled structured-output experiment plan

## Success criterion

Run exactly one no-retry inference for each authorized arm, retain the exact
outputs and requested measurements, apply both through unchanged CED, compare
their Socratic quality separately from schema compliance, then stop.

## Scope

1. Reconstruct and hash-lock the prompt-only control.
2. Generate the provider JSON Schema from the accepted CED opening-move fields
   and existing enums; prove nesting and field parity.
3. Validate the exact pinned endpoint and endpoint-compatible output-token field
   immediately before each arm.
4. Dispatch ARM 1 (`openai/gpt-4.1-mini`) once and ARM 2
   (`openai/gpt-4.1`) once, in fresh processes, with no retries.
5. Record transport, schema, CED, Socratic, content, latency, token, and cost
   evidence; compare the two actual questions side by side.

## Non-goals

- No CED relaxation or new transition authority.
- No additional model, question, retry, fallback, or architecture phase.
- No production integration and no push.

## Gates and stop conditions

- Offline parity and transport-path tests must pass before live dispatch.
- Exact numeric operator price ceilings and per-arm maxima must be explicitly
  authorized before they are rendered as authority.
- Credential presence is checked without exposing the credential before claims
  or live invocation.
- Any arm failure is its result; it is not retried.
- Stop after the second arm and report.
