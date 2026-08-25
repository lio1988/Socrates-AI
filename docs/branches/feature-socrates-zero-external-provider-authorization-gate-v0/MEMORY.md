# Stable branch memory — Phase 8.5B authorization gate

## Starting checkpoint

- Parent branch: `feature/socrates-zero-live-acquisition-contract-v0`.
- Fork HEAD: `765425eb9a6decabe3deb81abe2b08bb7914740e`.
- Current branch:
  `feature/socrates-zero-external-provider-authorization-gate-v0`.
- Protected untracked files: `scripts/live_dialogue.py.bak` and the malformed
  root filename beginning `ocratic_followup_mandate`.

## Sealed evidence

- Acquisition artifact:
  `acqartifactv0_fb7fc0b8f19607cf74cb549992a62ea94638228e8c5c9fedab65f445272c2d11`,
  SHA-256
  `2b22b0284b3feb3f79ab722e74b1e91d87024e6b0e9f6cb5337c70d32b468255`.
- Replay execution:
  `acqreplayexecutionv0_08125a577c16aa3324f395c46461651e50ce5f1df38627edf3401dbaf1b96f8f`,
  SHA-256
  `7f55030edf62b98f65122b5e43a010e32730dcaec6b179739a65f7fe9ec4ed4b`.
- Replay lock:
  `acqreplaylockv0_af196a855a1cefd1220a0a61b159ac75d1b8928b112704c48d7e30b686080e0a`,
  SHA-256
  `335dec0cc1a1e7bc9f5d78368cacbf1d253b754ba276f0e894082737538c859c`.
- Semantic equality, artifact-ID equality and byte identity are all true.

## Non-negotiable invariants

- This gate performs static inspection and canned/dry-run verification only.
- Network, DNS, credential access, provider dispatch, model and tool activity
  remain zero.
- Acquisition Contract v0 and all sealed artifacts are read-only.
- No canonical CED application or production mutation is permitted.
- Unknown mandatory controls block authorization.
- Exactly one of the four mandated decisions must be selected, with no tie.
- No authorization manifest may contain TBD, UNKNOWN, defaults, ranges or
  mutable `latest` identifiers.

## Gate decision

- Exact decision: `PROVIDER-ADAPTER HARDENING REQUIRED`.
- Selected hardening base: OpenRouter
  `OpenRouterProviderAdapter`, exact repository candidate model
  `openai/gpt-4.1-mini`; current selection status `REJECTED`.
- Section 60 applies before Section 61 because the adapter itself is not yet
  adequate. External credential/network hardening remains a later gate.
- Exact next branch:
  `feature/socrates-zero-provider-adapter-controls-v0`.
- No authorization manifest or manifest ID was issued.

## Decisive adapter blockers

- Acquisition Contract v0 accepts only its exact canned transport; no external
  acquisition adapter exists.
- No canonical final-byte request renderer/digest/length exists.
- The OpenRouter council prompt contains task/session/agent/process metadata and
  is not built from `AcquisitionSemanticRequest` alone.
- OpenRouter omits maximum output tokens and does not freeze upstream provider
  routing, seed, fallback, tools or complete termination behavior.
- Raw response, usage completeness and frozen integer-micro-USD cost evidence
  are absent.
- No candidate has a frozen pricing record.

## Verification evidence

- Acquisition focused suite: `214 passed`.
- Phase 5/7/8 and core-lock integrity suite: `106 passed`.
- Static/canned adapter suite: `96 passed, 1 deselected`.
- The deselected test probes credential-environment presence and was excluded by
  the gate's zero-credential-access rule.
- Existing credential-broker and independent external-network-boundary canned
  suites: none found; this is blocking evidence, not a pass.
- Live/network/credential/provider/model/tool activity: `0/0/0/0/0/0`.
