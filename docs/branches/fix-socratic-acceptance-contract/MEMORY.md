# fix/socratic-acceptance-contract

## Invariants

- Provider success is not CED acceptance.
- Opening and follow-up Socratic questions have different hard contracts.
- Accepted move identity is assigned only after the Socratic content contract
  and injection firewall pass.
- Follow-up grounding must name existing public artifacts; unresolved or
  malformed references authorize no Reflection.
- Cycle-locality, maximum two follow-ups, retry bounds, append-only commitment
  history, reconstruction timing, and model independence remain unchanged.
- `marker_is_contracted(task_kind)` is the sole authority for whether a marker
  is required. Deliberative moves require one canonical string value;
  evaluative moves must not carry one.
- Marker validation is schema completeness only. Markers remain advisory and
  cannot create evidence, scores, verification, ratification, or CED authority.

## Protected local state

The pre-existing untracked `scripts/live_dialogue.py.bak` and malformed root
filename beginning `ocratic_followup_mandate` remain untouched.
