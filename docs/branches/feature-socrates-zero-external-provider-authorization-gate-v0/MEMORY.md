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
