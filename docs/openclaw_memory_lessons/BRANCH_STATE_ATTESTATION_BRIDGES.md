# Branch State — Governed Attestation Bridges

Branch: `feature/openclaw-attestation-bridges`

Base: `main` at `8753c2c` (`Add evidence attestation bridge and bind self-revision docs`)

Scope:

- extend named-human attestation from repeated weakness evidence to matched
  Identity resolution evidence;
- add explicit Soul constitutional/risk attestation over existing same-agent
  evidence;
- make `openclaw_review.py` report immutable self-revision evidence and proposal
  lifecycle state in `SELF_REVISION_PIPELINE.md`;
- preserve the existing offline, no-provider, no-authority boundary;
- add focused regression tests and an explicit local test gate.

Not in scope:

- automatic Soul inference;
- automatic proposal creation, approval, or application;
- lesson A/B attestation bridge;
- CED authority changes;
- live provider activation;
- merge before local full-suite verification.
