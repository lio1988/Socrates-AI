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
- Marker enforcement is a separate atomic milestone.

## Protected local state

The pre-existing untracked `scripts/live_dialogue.py.bak` and malformed root
filename beginning `ocratic_followup_mandate` remain untouched.
