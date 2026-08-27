# MEMORY — feature/socrates-zero-openrouter-one-live-shadow-v1

## Source checkpoint

- Source branch: `feature/socrates-zero-openrouter-live-safety-closure-v1`
- Source HEAD: `e60856963310028bf391ac64792a9c1658f5e2c3`
- S7A artifact: `szorlivesafetyartifactv1_237286af63bc509db7fe2cbd4e40a78150d36213ec162a2a745494eeeeed70b3`
  SHA-256 `9bdc7f58ca1e29a9ed082a863a6bc4487f9687c564207887b226953cc6f95a01`
- S6 artifact: `szorpreliveartifactv1_4330f2640058037e2d8d4a7df45ab4694813e485538a552a91bffe1c331f6779`
  SHA-256 `8f457a36bf0fbfcae71e16ff708a1b6d35d96161540c35fd4520c4f769f64b9d`

**A conflicting S7A artifact ID was circulated and is wrong.** The variant
ending `…0ca5e2255a2f4d205c7f2d6364a67588e2c39b69c9eba01` is a splice of the
artifact prefix with the tail of the *case-set* ID
(`szorlivesafetycasesetv1_21ab3255104dbb5fe0ca5e2255a2f4…`). It appears nowhere
in the repository. Repository bytes are the authority.

## Non-negotiable invariants

1. **At most one inference POST, ever.** A process-wide latch claims the budget
   *before* a socket opens, so even a crash mid-flight consumes it. A second
   request needs a new human authorization and a new phase.
2. **No retry, for any reason.** A 4xx, a 5xx, a timeout, a malformed body and a
   provider error envelope are all scientific evidence, not a reason to re-send.
3. **Consumption precedes dispatch.** The authorization is burned in the durable
   store before the request goes out, so a crash under-executes rather than
   leaving a reusable authorization behind.
4. **Budgets stay separate.** `jit_metadata_get` and `live_inference_post` are
   distinct latches and distinct counters; never aggregate them.
5. **The credential is read in exactly one place** and only ever interpolated
   into a live header. It is never returned, stored, logged, hashed, or bound
   into any identity. Only `PRESENT`/`ABSENT` leaves the module.
6. **Registered bytes are the sent bytes.** The dispatch boundary re-derives the
   digest from the bytes about to go out and refuses if it disagrees.

## The claim store, stated exactly

Frozen S7A semantics: `ATOMIC_CREATE_NEW_TRUSTED_DURABLE_NON_ROLLBACK`.

The frozen contract does **not** require cryptographic anti-rollback. Its own
docstring says the record "makes the trust dependency explicit" and that a live
preflight "must obtain the live operator/store evidence". So the property is
externalized to an operator grant, and the operator supplied one.

The scientific claim is therefore the narrower
`TRUSTED_DURABLE_NON_ROLLBACK_UNDER_DECLARED_OPERATOR_TRUST_MODEL`.

| in the threat model | outside it |
| --- | --- |
| process crash | malicious local administrator |
| ordinary process restart | deliberate filesystem rollback |
| accidental duplicate execution | VM/snapshot rollback |
| concurrent duplicate consumption | backup restore across the boundary |

**Never describe this store as cryptographically rollback-proof.** The grant
carries the exclusions inside its content-addressed identity so an artifact
cannot quietly drop them.

Location: `C:\Users\spirc\AppData\Local\SocratesZero\openrouter-claim-store-v1`,
outside the repository and outside temporary directories — both measured by the
grant builder rather than asserted by its caller.

## Operator authority

The operator supplies every monetary value; S7B invents none. Ceilings are
maxima, not pricing evidence, and they are not P18. Grants are content addressed
over the exact decimal strings, so a grant cannot authorize different numbers.

**The renderer canonicalizes decimal money**: `"0.50"` reaches the wire as
`"0.5"` and `"2.00"` as `"2"`. Same value, canonical form. Report the wire form
honestly rather than echoing the input string.

## Traps

The acquisition tripwire treats reading `OPENROUTER_API_KEY` as a credential
access and aborts. Offline tests must inject at `_read_bearer_credential_v1`
rather than touching the environment — which is also why there is exactly one
read site.

`SYNTHETIC_OFFLINE` mode requires `szorclaimstorefixturev1_` evidence and
`LIVE_JIT` requires `szorclaimstoregrantv1_`. The frozen contract refuses the
cross product, deliberately; do not "fix" that by passing a live grant offline.

## Environment

Repository `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter-v2r1-publish`;
interpreter `C:\Users\spirc\Desktop\Socrates-AI-OpenRouter\.venv\Scripts\python.exe`
(Python 3.12.10, the environment that produced S7A); `PYTHONPATH` at the
repository root. `.gitignore` ignores `*.md` and `*.json`, so use `git add -f`.

## Transport invariants locked in the correction round

**One sealing step.** ``_dispatch_once_v1`` binds ``sealed_body`` once; that same
object is digested into the registration and handed to ``connection.request``.
There is no second serialization between identity and the socket, so they cannot
diverge. The offline lock asserts registered == dispatched byte-for-byte and
that a one-byte flip breaks the digest.

**Targets are pinned per dispatch class.**
``FROZEN_OPENROUTER_PERMITTED_TARGETS_V1`` maps ``jit_metadata_get`` to
``GET /api/v1/model/openai/gpt-4.1-mini`` and ``live_inference_post`` to
``POST /api/v1/chat/completions``. Host is a ``Literal``. A wrong method, path or
host is refused by the registration contract before a socket is opened.

**Semantic headers are evidence; Authorization is not.** The registration carries
the authorized header pairs and their digest. Authorization is injected into a
local dict at dispatch and appears in no record, no return value, no exception
and no artifact.

**One credential read site.** ``_read_bearer_credential_v1`` is the only place
that touches ``os.environ``. Offline tests inject there. Import inertness is
proven by executing both module bodies in throwaway namespaces with
``os.environ.get`` and ``builtins.open`` instrumented: zero credential reads,
zero writes.

**S5/S6 take the transport's own representation.**
``s5_observation_from_live_v1`` hands S5 the exact raw bytes and header pairs;
``s6_transport_record_from_live_v1`` copies every S6 transport field straight
across from the registration and completion records. Nothing is rebuilt, so a
binding failure would mean the evidence really disagrees.

## The retained live response is now a regression fixture

The real captured model-detail response is kept under ``evidence/`` and an
offline test asserts it still fails the frozen identity rule. That keeps the
abort reason reproducible without any network.

## A leak my own test caused, and the rule it produced

The first import-inertness probe instrumented ``os.environ.get`` and restored it
by assignment. That leaked: the acquisition tripwire patches
``os._Environ.get`` on the **class**, so assigning ``os.environ.get`` created an
*instance* attribute that kept shadowing the class after the tripwire stopped.
Two unrelated tests in ``test_tree_distillation.py`` then aborted on
``ANTHROPIC_API_KEY`` reads, but only when run in the same process — they passed
standalone.

Rule: **do not patch global interpreter state to prove inertness.** The probe now
patches nothing and simply executes the module bodies inside the tripwire, which
already aborts on credential, network, provider and tool seams. Filesystem
inertness is proven by an AST check over module-level statements instead.

## The P17 alias binding — one exact pair, bound to one observation

The original rule required ``data.canonical_slug == "openai/gpt-4.1-mini"`` by
string equality. The live first-party API returns
``openai/gpt-4.1-mini-2025-04-14``, so P17 could not be established and S7B
aborted. The operator ruled that too strict for the observed contract and
authorized one narrow correction.

``FROZEN_OPENROUTER_P17_AUTHORIZED_ALIAS_BINDINGS_V1`` holds exactly one triple:

    ("openai/gpt-4.1-mini",
     "openai/gpt-4.1-mini-2025-04-14",
     "728a7bfe823bf86c4cf8689fdd6535b5870cc4c7f4b628e982292cc29592e290")

Acceptance is tuple membership over all three components. There is no prefix
match, no date tolerance, no suffix stripping and no resolver, and a source-level
test asserts none of those appear in the acceptance path. Re-serializing the same
semantic content changes the digest and the binding is refused: **the binding
cannot outlive the evidence that justified it.**

**The two identities stay distinct.** ``exact_model_id`` remains the requested
alias, ``canonical_model_id`` the canonical build, and ``alias_state`` names the
relation ``FIRST_PARTY_OBSERVED_ALIAS_TO_CANONICAL_BINDING``. Neither value is
rewritten into the other, and no string identity is claimed.

**The wire is unchanged.** The production request still carries
``model: "openai/gpt-4.1-mini"``; the date never appears in the request body.

Correction to an earlier report: ``alias_target`` is **absent** from the live
response, not present-and-null. The parser treats absent as acceptable.
