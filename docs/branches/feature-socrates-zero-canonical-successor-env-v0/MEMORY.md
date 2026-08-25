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

## Protected local state

Do not touch `scripts/live_dialogue.py.bak` or the malformed untracked root
filename beginning `ocratic_followup_mandate`.

