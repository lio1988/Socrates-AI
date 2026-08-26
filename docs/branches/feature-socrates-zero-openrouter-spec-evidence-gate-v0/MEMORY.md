# Phase 8.5C memory

## Immutable incoming truth

- Parent HEAD: `040671700760b1fe2d3d9cd41d533ab0bbae085f`.
- OpenRouter adapter-controls artifact:
  `0d530877fc3effe1fa6d0e676fcbb2e980705bb0082a992d6d9c89a7321e5083`.
- Sealed result: `FALSIFIED` at `P08_ROUTE_POLICY`.
- Replay: not performed; replay lock: absent.

## Gate findings

- P08: strong official request controls; exact endpoint response attestation is
  absent.
- Exact endpoint selector: `azure/swedencentral` was available in the mutable
  official inventory and is a documented full-suffix selector form.
- P09: provider/model fallback intent and router attempt checks exist; hidden
  retry/failover remains outside complete attestation.
- P17: v0 byte-count method invalid; a separate exact-endpoint context-ceiling
  method is credible but not implemented.
- P18: mutable snapshot design possible; complete pricing for the selected exact
  endpoint not established.
- P19: pre-dispatch total cost maximum not established; `max_price` is only a
  unit-price eligibility filter.
- One-call evidence: partial, not specification-guaranteed complete.

## Decision

`OPENROUTER ROUTE-CONTROL MILESTONE ONLY EARNED`

No live, credential, provider, model, CED or production authority follows.

## Content-addressed evidence

- Manifest ID:
  `szorspecmanifestv0_6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`.
- Manifest semantic SHA-256:
  `6f09a0f2b2b42920710c19d97bb5b64bbd184c88c6d9983af2efe9b5f7d84f03`.
- Validity: historical snapshot only.
- Revalidation: `REVALIDATE_BEFORE_AUTHORIZATION`.
- Drift: `FAIL_CLOSED`.

## Protected local files

Do not stage, edit, rename, move or delete:

- `scripts/live_dialogue.py.bak`;
- the malformed root filename beginning `ocratic_followup_mandate`.
