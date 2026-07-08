# Agent Prompt Base v0.1

This document records the shared base design for future CED / OpenClaw agent prompts.

## Purpose

Every provider should follow the same council protocol. Provider-specific behavior should be added only as small patches.

## Variables

- TASK
- PHASE
- ROLE
- CYCLE_NUMBER
- MODEL_ID
- COUNCIL_HISTORY
- MEMORY_LESSONS
- EVIDENCE
- OUTPUT_LANGUAGE
- OUTPUT_SCHEMA

## Principles

- No permanent model authority.
- No permanent provider role.
- CED assigns roles per phase.
- Evidence over agreement.
- Claims must be explicit.
- Unsupported claims must be marked.
- Uncertainty must be preserved when evidence is incomplete.
- Exact output constraints must be obeyed.
- Memory lessons are guidance, not factual evidence.
- Future changes should be small prompt patches.

## Roles

- THESIS_BUILDER
- ELENCHUS_CRITIC
- EVIDENCE_VERIFIER
- ALTERNATIVE_FRAMER
- RECONSTRUCTOR
- SYNTHESIZER
- RATIFICATION_REVIEWER

## Default output sections

- answer
- claims
- criticisms
- revisions_needed
- synthesis_draft
- ratification_review
- final_answer

## Next step

Create a prompt registry that loads this base, applies provider-specific patches, fills the variables, and passes the final prompt to the selected model provider.
