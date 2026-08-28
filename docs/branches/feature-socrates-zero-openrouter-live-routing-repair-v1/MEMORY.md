# Stable branch memory

- Branch: `feature/socrates-zero-openrouter-live-routing-repair-v1`.
- The two prompt-only GPT-4.1-mini runs are frozen controls. Their CED schema
  acceptance remains `0/2`; neither result may be rewritten or discarded.
- The reproduced failure is a valid marker at the wrong location: top-level
  `epistemic_marker`. CED continues to require `content.epistemic_marker`.
- CED is the sole acceptance authority. Provider JSON-Schema validity, generic
  CED schema acceptance, and canonical Socratic/firewall acceptance are three
  separate observations.
- The provider schema is generated from strict types using the existing CED
  operator and epistemic-marker enums, then checked for exact field and nesting
  parity. It is not a second CED schema.
- The controlled treatment has exactly two no-retry arms: GPT-4.1-mini and
  GPT-4.1, both pinned to `azure/swedencentral` with the same schema, question,
  phase, role, dialogue context, temperature, and output limit.
- Exact endpoint capability is fetched and validated independently for each
  model immediately before its arm. Model-level parameter unions are never
  accepted as endpoint authority.
- No push is authorized.
- The completed treatment produced two HTTP-200, provider-valid, CED-accepted,
  Socratic-accepted moves with zero retries. Mini succeeded under structured
  output, so the preserved prompt-only failure is classified as interface
  reliability rather than semantic-move failure.
- This pair establishes no material GPT-4.1 Socratic capability gain. Prefer
  GPT-4.1-mini for the opening Socratic role until broader evidence changes that
  conclusion.

Frozen control SHA-256 values:

- `runs/README.md`: `14c362c4bd05337ce61e1fc7899bcc0d17ab5b38521bdf897ad7bbd99325d547`
- `runs/socrates_live_run_002.json`: `9636ceabc377bee74cf235584599f7a1d11f1880c10b9b5647046ee29a6cbf0d`
- `runs/socrates_live_run_003.json`: `59f1c4c622bb0a985f560398dc4fd1b78445f31681c14617ef0efce698088c2e`
