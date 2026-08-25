# Branch: feature/socrates-zero-canonical-successor-env-v0

## Durable facts

- Exact base is Phase 7.5 commit
  `803c31b285c0ac6f9f40af1fb61ec8c67fc56e42`.
- Phase 7.5 selected exactly `CANONICAL SUCCESSOR ENVIRONMENT NEXT`.
- The sole supported family is canonical registry opening
  `ASK_SOCRATIC_QUESTION / OPENING / SOCRATES / SOCRATIC_QUESTION / round=0 /
  slot=0 / attempt=0`.
- CED is the sole transition authority. SocratesZero must not contain copied
  role, scheduling, parser, firewall, acceptance, move, TaskLog, commitment,
  phase, ratification, or release rules.
- A behavior-preserving extraction is required because task construction and
  response application are currently nested inside `_run_registry_phase`.
  Production and replay must call the same extracted CED helpers.
- Provider acquisition stays outside the transition core. Phase 8 consumes
  recorded raw observations and performs zero provider/model/tool calls.
- The v0 corpus ID
  `cedobscorpus_99a8090204758b4085f6f937d0e36ab77f6fe4f79f3c66ab8416b05c49bfb8e0`
  is preserved as `INVALIDATED / SUPERSEDED FOR AUTHORITATIVE PHASE-8 PARITY`.
  It rebound raw output to caller-created task/provider metadata.
- The repaired lineage commit is `5ad83db`. Its manifest ID is
  `cedcapturemanifest_ab3391e6fa324dec6ca2d8937ba09bdb7100c373fb7e7c38bb6be53bb0c86a60`;
  corpus ID is
  `cedobscorpus_b5ebe4b46d2b3ae4fed3faded341c8a2d8ff5f5f254531f000e479bf66b7f8b7`;
  canonical corpus SHA-256 is
  `06c5eda5ee8c71992cb8b7427794f6d5ab6e44b4f92f0d6f71f4366d5729427c`.
- The five frozen records are one accepted opening plus content, injection,
  invalid-JSON, and schema canonical rejections. Each unchanged donor raw
  producer is exercised inside the actual registry/CED capture path.
- Observation compatibility binds semantic source/context/request, task
  coordinates, provider, configured/actual model, configuration, capsule, and
  execution. Exact manifest membership prevents caller rebinding.
- A different canonical question with the same session, action, provider,
  model, configuration, raw bytes, and task coordinates fails closed as
  `ROOT_CONTEXT_MISMATCH` without dispatch or mutation.
- CED now emits the explicit accepted/canonical-rejection application outcome;
  the successor environment only projects that CED-owned category.
- The aggregate evaluator is frozen separately and must turn evaluation
  failures into `FALSIFIED` evidence. Replay-lock publication must compare the
  actual authoritative and reverse-order replay artifacts internally.
- The complete pre-result evaluator/docs freeze is commit `36393fe`. No
  aggregate builder had run when that commit was created.
- `move_id` remains the exact canonical CED ID and contains no branch entropy.
  Random production `task_id` and timestamps are non-semantic audit fields.
- Canonical rejection is distinct from `SUCCESSOR_UNAVAILABLE`. A provider-OK
  opening refused by the Socratic firewall is an applied canonical rejection.
- The post-transition SearchState-v1 diagnostic uses the same consumed opening
  task spec. CED has no singular persisted next-task cursor and Phase 8 must not
  invent one.
- Depth two, shadow collection, Experience Store, learning, RL, and production
  authority remain blocked after Phase 8.
- Frozen Phase 5 normalized SHA-256:
  `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`.
- Frozen Phase 7 primary SHA-256:
  `d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca`.
- Frozen Phase 7 BestOfN SHA-256:
  `86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637`.
- The first authoritative artifact is immutable at commit `07ec5ab`, ID
  `cedparityartifactv1_893771ebb142e48b63dcdd623bdc734d7bb0da5697df251fadf73d3eda45f5e0`,
  SHA-256
  `00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea`.
- Its frozen hypothesis status is `FALSIFIED`. Supported parity is 5/5 and
  unavailable negatives are 13/14. `wrong-provider` expected
  `OBSERVATION_PROVIDER_MISMATCH` but returned `ROOT_CONTEXT_MISMATCH` because
  changing the provider roster changes the CED-owned `council_roster` task
  context before the provider-ID compatibility check.
- The failed probe still created no successor, used no replay resources,
  dispatched no provider, and mutated neither source nor production control.
  The falsification is an exact predeclared taxonomy mismatch, not unsafe
  acceptance.
- No independent aggregate replay or replay lock was run after falsification.
  The v1 artifact must never be rewritten; Phase 8.5 is not earned.

## Protected local state

Do not touch `scripts/live_dialogue.py.bak` or the malformed untracked root
filename beginning `ocratic_followup_mandate`.
