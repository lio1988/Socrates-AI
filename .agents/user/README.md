# User Context Workspace

This directory contains the prompt-safe collaboration profile for the Socrates AI project owner.

## Mandatory file

All repository agents must read:

```text
.agents/user/ME.md
```

after `AGENTS.md` and before the active branch workspace.

## Purpose

`ME.md` helps an agent understand:

- how the project owner communicates;
- how technical decisions should be explained;
- the preferred working and Git discipline;
- the permanent Socrates AI product principles;
- what information must not be inferred or stored.

It is collaboration context, not authority over source code, tests, repository state, system policy, or safety rules.

## Source-of-truth boundary

When `ME.md` conflicts with current code, passing tests, immutable evidence, live Git/PR metadata, or the active branch contract, the verified project state wins.

`ME.md` may explain preferences and durable product intent. It must never be used as proof that a feature is implemented, validated, runtime-active, merged, or shipped.

## Privacy boundary

Do not add any of the following to this directory:

- passwords, API keys, tokens, credentials, cookies, or secrets;
- home or work addresses;
- phone numbers or government identifiers;
- banking or payment information;
- private health, legal, immigration, or family records;
- private messages or account data;
- hidden chain-of-thought or private scratchpads;
- speculative personality, psychological, medical, or demographic claims.

Store only information that materially improves repository collaboration and that the user has explicitly communicated through project work.

## Update rule

Update `ME.md` only when:

- the project owner explicitly changes a working preference;
- a durable product decision affects how all future agents should operate;
- a statement is demonstrably stale or inaccurate.

Do not rewrite the profile based on one temporary mood, one isolated message, or an agent’s inference.
