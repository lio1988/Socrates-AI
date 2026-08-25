# SocratesZero Value v1 Decision Gate

Status: Phase 6.5 decision complete on
`feature/socrates-zero-canonical-observability-v1`

## 1. Executive verdict

```text
DECISION: VALUE V1 IMPLEMENTATION EARNED
```

What is earned is one bounded deterministic experiment, not promotion and not
a claim of search improvement. Phase 6 exposed a lawful intermediate-state
governing summary—`ClaimAssessment.support_state`—that v0 cannot inspect. Its
negative/readiness states have defensible directional meaning for `V(s)` when
used once, claim-locally, without positive support rewards.

The approved shape is **penalty-only**. `SUPPORTED` removes a claim-readiness
deficit but earns no positive bonus. Evidence, verification results, objection
state, and contradiction state are audit/provenance inputs already aggregated
by the governing assessment; they receive no independent contribution.
Resolved objections and dismissed contradictions remove an applicable penalty
only. They never become positive progress. Counts never increase Value.

The next branch is:

```text
feature/socrates-zero-heuristic-value-v1
```

It must freeze a new development/holdout evaluation before implementing
`heuristic-value-estimator/v1`. The sealed Phase 5 benchmark remains diagnostic
history, never the promotion holdout.

## 2. Phase 6 evidence and frozen boundary

Repository truth at this gate:

- Phase 6 HEAD: `968a35b350895b6cc702cf5daac68778965a7ecf`;
- SearchState semantic ID: `socrates.zero.search-state/v1`;
- projection semantic ID: `ced-search-state-projection/v1`;
- Phase 6 hypothesis: `SUPPORTED`;
- Phase 5 normalized artifact SHA-256:
  `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`.

Phase 6 proved two exact v0 collapses:

1. protocol/deterministic `VERIFIED` and model-produced `VERIFIED` records can
   have the same v0 semantic identity while Hybrid assesses their claims as
   `SUPPORTED` and `UNSUPPORTED` respectively;
2. no contradiction record and a canonical `DISMISSED` contradiction have an
   identical full v0 projection.

It also made verification outcomes, required-but-unverified support, and
resolved objection lifecycle structurally inspectable. That establishes
observability, not reward semantics. This gate preserves every Phase 6
rejection: no question-resolution lifecycle, upstream epistemic abstention,
revision/commitment process history, provider failure, score, consensus,
confidence, marker, or ratification signal is added to Value.

## 3. Complete v1 signal inventory and classification

Class meanings:

- **A** — safe directional signal;
- **B** — safe structural signal, not directional;
- **C** — redundant/derived; useful for provenance or suppression, not an
  independent contribution;
- **D** — unsuitable for Value.

“Record-terminal” below means the immutable result of one bounded record. It
does not mean the CED session is terminal.

| Signal / exact v1 fields | Canonical upstream type | Authority / exact source | Available at state time? | Terminal or nonterminal? | Derived? | Direction for Value | Positive / negative / neutral use | Double-count risk | Reward-hack risk | Temporal risk | Class and disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `schema_version`, `projection_version`, `authority_schema_version` | version literals | v1 contract / Hybrid schema | yes | both | contract identity | none | neutral validation only | none | identity gaming if rewarded | low | **B** validate only |
| v1 `state_id` | deterministic contract ID | `SearchStateV1.identity_payload()` | yes | both | aggregate of all fields | none | neutral identity/audit | total aggregate | high if ordinalized | low | **B** equality/replay only |
| `base_state` and its v0 `state_id` | frozen `SearchState` v0 | unchanged v0 projector | yes | both | compatibility envelope | existing v0 only | terminal/aporia compatibility only | medium with v1 views | count/digest gaming | low | **B** compatibility; never score its opaque digests |
| evidence `source_record_id`, `claim_id`, `semantic_digest` | `EvidenceRecord` IDs | Hybrid evidence ledger | yes | both | no / identity | none | neutral provenance/dedup | low | high if IDs/counts rewarded | low | **B** provenance only |
| evidence `stance` | `EvidenceStance` | `EvidenceRecord.stance` | yes | both | input to `assess_claim()` | context-dependent | no direct contribution | **high**: basis/unresolved then SupportState | evidence farming | low | **C** assessment provenance only |
| evidence `source_type` | `EvidenceSourceType` | `EvidenceRecord.source_type`; projector includes admissible records only | yes | both | determines admissibility upstream | no ordering among admissible types | neutral provenance | high with support state | source-label gaming | low | **B** structural; do not rank methods/sources |
| evidence `receipt_ref` | optional canonical receipt link | `EvidenceRecord.receipt_ref` | when present | both | no | none | neutral traceability | low | receipt-count farming | low | **B** provenance only |
| evidence collection size/existence as a numeric feature | canonical records, but quantity is not support quality | Hybrid ledger | yes | both | aggregate count | unsafe | none | high | **high** | low | **D** never reward evidence quantity |
| verification `source_record_id`, `claim_id`, `objection_id`, `evidence_ids`, `semantic_digest` | `VerificationRecord` links | Hybrid verification ledger | yes | record-terminal; session both | no / identity | relationship-dependent | neutral provenance/dedup | high with assessment/lifecycle | attempt farming | low | **B** links; **C** when represented by assessment |
| verification `verification_class` | `VerificationClass` | `VerificationRecord.verification_class` | yes | record-terminal; session both | upstream classification | not ordinal | neutral structural use | medium | class-selection gaming if ranked | low | **B** do not rank classes |
| verification `method` | `VerificationMethod` | `VerificationRecord.method` | yes | record-terminal; session both | constrained by class | not ordinal | neutral provenance | medium | method farming | low | **B** do not rank methods |
| verification `result` | `VerificationResult` | verifier-owned immutable record | yes after that attempt | record-terminal; session both | input to objection/contradiction and claim assessment | directional only in context | no direct contribution | **very high** | repeated-attempt farming | low at snapshot; high if future result read | **C** use governing assessment, retain result in audit |
| verification collection size/activity | record count | Hybrid ledger | yes | both | aggregate | unsafe | none | high | **high** | low | **D** no attempt/count reward |
| assessment `claim_id`, `semantic_digest` | `ClaimAssessment` identity | result of `HybridEpistemicState.assess_all()` | yes | both | governing current summary | ID has none | neutral scope/audit | low | claim-splitting if counted | low | **B** active-claim scope only |
| assessment `support_state` | `SupportState` | computed inside `assess_claim()` and stored in `ClaimAssessment` | yes whenever records exist | both; not a release label | aggregate governing summary | **yes, as readiness deficit** | negative or neutral; never positive | manageable if highest-authority representative | claim splitting if per-claim | low at snapshot; terminal-shortcut risk in fixtures | **A** sole new directional family |
| `basis_record_ids`, `falsifying_record_ids`, `unresolved_record_ids` | exact governing provenance lists | `ClaimAssessment` from `assess_claim()` | yes | both | aggregate underlying records | no independent direction | neutral refs and duplicate suppression | **very high** | record inflation | low | **C** provenance/suppression only |
| `eligible_for_assembly` | governing Boolean | `_eligibility()` from supersession and `SupportState.FALSIFIED` | yes | both | derived downstream of claim/support | no independent direction | neutral validation | high with falsified/support state | assembly-label shortcut | low | **C** never add a component |
| objection `source_record_id`, `target_claim_id`, `scope`, `target_provenance`, `verification_id`, `semantic_digest` | typed `ObjectionRecord` links | Hybrid objection ledger | yes | both | links feed assessment | none by themselves | neutral provenance | high with assessment | target/objection farming | low | **B** structural, **C** for suppression |
| objection `state` | `ObjectionState` | `add_objection()` / `transition_objection()` | yes | lifecycle-current; session both | raised/pending/inconclusive/validated feed assessment; rejected is ignored | open state can remove readiness; closure is not positive | no independent contribution | **very high** | create-and-resolve farming | low at snapshot; future resolution forbidden | **C** assessment representative; rejected only removes penalty |
| objection collection count or resolved count | record count/lifecycle aggregate | Hybrid ledger | yes | both | aggregate | unsafe | none | high | **very high** | low | **D** no closure/count reward |
| contradiction `source_record_id`, `claim_id_a`, `claim_id_b`, `verification_id`, `semantic_digest` | typed `ContradictionRecord` links | Hybrid contradiction ledger | yes | both | links feed assessment/compatibility | none by themselves | neutral provenance | high | edge farming | low | **B** structural, **C** for suppression |
| contradiction `state` | `ContradictionState` | add/validate/dismiss lifecycle | yes | lifecycle-current; session both | only `VALIDATED` enters claim assessments/incompatibility | candidate and dismissed are neutral; validated is already unresolved support | no independent contribution | **very high** | create-and-dismiss farming | low at snapshot; future resolution forbidden | **C** assessment representative; dismissal only removes penalty |
| contradiction count or dismissed/resolved count | lifecycle aggregate | Hybrid ledger | yes | both | aggregate | unsafe | none | high | **very high** | low | **D** no edge/closure reward |

Exactly one newly exposed semantic field family is Class A:
`ClaimAssessment.support_state`. All direct record semantics are structural or
derived once that governing summary is present.

## 4. Authority ownership and state-time rule

CED/Hybrid/Verifier remain authoritative. Future Value v1 receives one already
constructed immutable `SearchStateV1`; it may not import or call Hybrid,
re-assess a claim, validate a verification, transition a lifecycle, inspect a
release, or execute an action.

State-time admissibility is mechanical:

```text
V1(S_t) may read only fields contained in the frozen SearchStateV1 passed for t.
```

It may not look up a later ledger, a mutable session object, a final release,
an episode result, a benchmark label, or any successor other than the state
explicitly being evaluated. If an observation is not in `S_t`, it does not
exist for Value.

## 5. Derivation and double-count graph

The governing dependency graph is:

```text
EvidenceRecord
  ├─ admissible + SUPPORTING ───────────────┐
  ├─ admissible + CONTRADICTING ────────┐  │
  └─ WEAK / inadmissible -> no basis     │  │
                                         │  │
VerificationRecord                       │  │
  ├─ direct claim + creates_support ─────┤  │
  ├─ direct claim + FALSIFIED ───────────┤  │
  ├─ direct claim + INCONCLUSIVE /       │  │
  │  EXTERNAL_EVIDENCE_REQUIRED ─────────┤  │
  ├─ objection-linked result             │  │
  │    -> ObjectionState transition ─────┤  │
  └─ VERIFIED contradiction check        │  │
       -> ContradictionState.VALIDATED ──┤  │
                                         ▼  ▼
ObjectionState + scope ──────────────> assess_claim()
ContradictionState.VALIDATED ────────> assess_claim()
                                         │
                                         ├─ basis_record_ids
                                         ├─ falsifying_record_ids
                                         ├─ unresolved_record_ids
                                         ├─ SupportState
                                         └─ eligible_for_assembly
                                                │
                                                ▼
                                    later FrozenRelease (NOT in v1 Value)
```

`SupportState` is not a separate observation derived from an already-created
`ClaimAssessment`. `assess_claim()` computes the record sets and categorical
state together, then returns the `ClaimAssessment` that contains them.

One source event can therefore appear as evidence, a verification, a lifecycle
link, an assessment reference, and the final `SupportState`. Rewarding each
would multiply one epistemic event. The approved representative is the
highest-authority current summary: one active claim's `SupportState`. All source
records remain in the audit as suppressed/represented provenance.

## 6. Verification semantics

`VerificationResult` contains exactly:

| Result | Meaning in one immutable record | Global/session meaning | Governing effect |
|---|---|---|---|
| `VERIFIED` | bounded condition was verified | not universal truth; record-terminal only | creates claim support only when `record.creates_support`; may validate an objection or contradiction |
| `FALSIFIED` | bounded condition failed | not “the whole dialogue failed” | direct claim record falsifies; objection-linked record can instead reject the objection |
| `INCONCLUSIVE` | attempt did not settle the condition | later attempts remain possible | direct claim becomes unresolved; lifecycle may remain/re-enter pending |
| `EXTERNAL_EVIDENCE_REQUIRED` | task cannot settle an external claim | claim/session may later acquire evidence | direct claim becomes required-but-unverified when it has no basis |
| `NOT_APPLICABLE` | declared verification does not apply | neutral to the current governing assessment | no support/falsification contribution |

Every result is final for that record but provisional with respect to the whole
session. Class and method constrain legal provenance; they define no ordinal
ranking. A bare `VERIFIED` view is not safely positive: model-produced verified
records do not create support, and objection-linked verified records validate
an objection rather than the target claim. A bare `FALSIFIED` view can reject a
false objection. Value must therefore consume the resulting assessment, not
reinterpret results.

## 7. ClaimAssessment and SupportState audit

`ClaimAssessment` is claim-local and governing. `assess_all()` returns one for
every Hybrid claim at the current snapshot. It aggregates:

- destructive or support-undermining objections;
- validated contradictions;
- admissible evidence stance;
- direct verification results and support eligibility.

The exact precedence is:

```text
falsifying record exists                    -> FALSIFIED
external required and no basis             -> EXTERNAL_EVIDENCE_REQUIRED
any unresolved record                      -> UNRESOLVED
any basis                                  -> SUPPORTED
otherwise                                  -> UNSUPPORTED
```

`SUPPORTED` can exist without a verification: admissible supporting evidence is
a basis. `EXTERNAL_EVIDENCE_REQUIRED`, `UNRESOLVED`, and `UNSUPPORTED` are not
session terminal; later current-time records can change the next assessment.
An unsupported claim can later become supported. A supported claim can later
become unresolved or falsified. These states are available in nonterminal CED
phases whenever the corresponding canonical records exist.

Assembly eligibility is not the support state. It is false for superseded or
falsified claims and remains true for unsupported, unresolved, and
external-required claims. It is therefore unsuitable as a numeric shortcut.

## 8. Directional semantics and proposed Value shape

Value asks how ready/promising a valid current state is for eventually reaching
an evidence-backed constitutional outcome. The defensible order is a readiness
deficit order, not a truth probability:

```text
FALSIFIED                    strongest current deficit
EXTERNAL_EVIDENCE_REQUIRED  missing external substrate/readiness
UNRESOLVED                   governing friction remains
UNSUPPORTED                  no basis exists yet
SUPPORTED                    no claim-readiness penalty; no bonus
```

This ordering is deliberately conservative. Discovering a falsification can be
epistemic progress over time, but the current falsified active claim is not more
ready for assembly from that fact alone. A later state that supersedes or
removes it can improve by losing the penalty; no positive “discovery bonus” is
needed.

Value v1 should remain **penalty-only** with neutral base `0.0` and range
`[-1,+1]`. Positive rewards are not earned. This separates Phase 6's exact
`SUPPORTED`/`UNSUPPORTED` alias by assigning a modest unsupported deficit while
keeping supported at neutral.

## 9. Minimal predeclared rule families

The following seven families are the maximum allowed initial surface. Constants
are frozen here before the new holdout is authored or results are inspected.

| Reason code | Canonical source | Direction / maximum contribution | Precedence and deduplication | Nonterminal | Terminal |
|---|---|---:|---|---|---|
| `active_claim_falsified` | active `ClaimAssessment.support_state=FALSIFIED` | negative, `-0.20` maximum | mutually exclusive worst-state representative; claim + falsifying refs audit all underlying signals | yes | suppressed by terminal firewall |
| `active_claim_external_evidence_required` | active assessment `EXTERNAL_EVIDENCE_REQUIRED` | negative, `-0.12` maximum | used only if no active falsified claim; verification/evidence refs suppressed | yes | suppressed |
| `active_claim_unresolved` | active assessment `UNRESOLVED` | negative, `-0.08` maximum | used only if no higher-precedence state; objection/contradiction/evidence/verification components suppressed | yes | suppressed |
| `active_claim_unsupported` | active assessment `UNSUPPORTED` | negative, `-0.05` maximum | used only if no higher-precedence state; count independent | yes | suppressed |
| `socratic_remainder_open` | v0-base unresolved IDs minus canonical objection IDs | readiness penalty, `-0.05` maximum | one state-level component, never per remainder; preserves aporia without inventing resolution | yes | suppressed |
| `terminal_blocked` | `base_state.terminal_status=BLOCKED` | negative, `-0.20` maximum | terminal firewall representative; suppress every v1 claim/lifecycle component | no | yes |
| `terminal_budget_exhausted` | `base_state.terminal_status=BUDGET_EXHAUSTED` | negative, `-0.10` maximum | terminal firewall representative; suppress every v1 claim/lifecycle component | no | yes |

For nonterminal states, exactly one of the first four claim-state components may
appear, regardless of claim count. Only assessments whose `claim_id` appears in
`base_state.active_claims` are eligible; superseded historical assessments do
not influence Value. The worst active state is selected by the table precedence.
An optional single Socratic-remainder component can coexist because aporia is
not derived from Hybrid claim assessment.

For terminal states, only the frozen v0-compatible terminal component is
active. `ANSWER_READY` and `ABSTAINED` remain explicit neutral audit outcomes.
This firewall prevents governing support from becoming a near-terminal answer
label and prevents blocked release plus its underlying claim state from being
counted twice.

`SUPPORTED` may emit a zero-valued audit reason such as
`active_claim_supported_no_bonus`, but it is not an eighth numeric rule.

## 10. Precedence and duplicate suppression policy

The policy is hierarchical, not additive across representations:

1. validate the immutable v1 and embedded v0 state;
2. if terminal, use the terminal firewall and suppress all v1 semantic inputs;
3. intersect assessment claim IDs with v0 active claim IDs;
4. choose one worst `SupportState` across that active set;
5. emit at most one claim-state contribution;
6. record every basis/falsifying/unresolved record and related evidence,
   verification, objection, and contradiction source as represented/suppressed;
7. optionally add one state-level Socratic remainder penalty after subtracting
   canonical objection IDs from the conflated v0 unresolved set;
8. bound once to `[-1,+1]`.

No per-claim, per-record, per-evidence, per-verification, per-objection, or
per-contradiction accumulation exists. Adding records that leave the governing
worst active support state unchanged leaves Value unchanged.

## 11. Lifecycle and reward-hacking analysis

| Attack | Unsafe rule | Approved behavior |
|---|---|---|
| create many objections then reject them | bonus per rejected/resolved objection | open objection may contribute only through one assessment deficit; rejected/no-record are equal and earn no bonus |
| create contradictions then dismiss them | bonus per dismissal | candidate and dismissed are neutral; validated state appears only through one unresolved assessment deficit |
| add many admissible evidence records | reward per record/source | evidence quantity is ignored; governing support saturates at neutral |
| force repeated verification attempts | reward per `VERIFIED` or attempt | results are never scored directly; unchanged assessment means unchanged Value |
| split one claim into many claims | sum claim scores | one worst active support state only; counts do not matter |
| add an easy trivial supported claim | positive supported bonus | supported is neutral and cannot offset an existing deficit |
| manufacture uncertain claims | gain exploration/value spread | unsupported adds a modest deficit, never a benefit; dedicated holdout cases test over-penalized exploration |
| resolve workflow without new support | positive closure reward | resolution removes an open-state penalty at most; baseline no-record and resolved-record states tie |

The main residual risk is search avoiding useful hypothesis generation because
new claims begin unsupported. The modest one-state cap and holdout intermediate
exploration cases are mandatory guardrails. Failure there falsifies the rule;
it is not fixed by tuning after holdout inspection.

## 12. Circularity and terminal-label firewall

Using governing `SupportState` is not authority duplication: Value reads a
current fact and cannot alter it. It is nevertheless a downstream summary of
the same evidence Value is trying to estimate around, so circularity risk is
real.

The experiment controls it by:

- using SupportState once and suppressing all underlying record components;
- assigning no positive value to `SUPPORTED`;
- scoring v1 semantic rules only on nonterminal states;
- excluding FrozenRelease, release decision, final synthesis and benchmark
  outcome from Value input;
- stratifying primary results into intermediate and terminal-only subsets;
- requiring improvement on nonterminal holdout pairs independently of all
  terminal cases;
- including terminal-support-only cases where support must not create ranking
  gain.

If success comes primarily from reading late supported/falsified labels, the
hypothesis fails even if aggregate accuracy rises.

## 13. Intermediate versus terminal observability

The new fields are structurally available at early/intermediate, late
predecision, and terminal snapshots whenever their canonical records already
exist. Phase 6 projected actual nonterminal SessionState/Hybrid fixtures and
proved opposite later verification outcomes do not change the shared prefix.

Therefore v1 improves **potential intermediate-state observability**, not only
terminal observability. What remains unknown is empirical density: v1 is not
wired into production, and the repository has no corpus showing how often real
intermediate CED states contain discriminating assessments. The new evaluation
must make nonterminal pairs the primary population. Terminal behavior is a
firewall/control population only.

## 14. Phase 6 alias relevance to Value

| Phase 6 pair | Why v0 collapsed | v1 separation | Safe Value direction? | Timing | Leakage risk |
|---|---|---|---|---|---|
| deterministic/protocol verified support vs model-produced verified non-support | route ID excluded from semantic identity; result digest exposes no governing assessment | `SUPPORTED` vs `UNSUPPORTED` | yes as neutral vs modest readiness deficit; never reward provider identity or `VERIFIED` directly | nonterminal fixture; current-time | low if assessment only; high if fixture label is copied |
| no contradiction vs `DISMISSED` contradiction | v0 omits dismissed records | explicit dismissed lifecycle record | **no positive direction**; states must tie | nonterminal/current | create-dismiss farming if rewarded |
| `VERIFIED` vs `FALSIFIED` | v0 digest changes but result is opaque | literal result | not safely direct; meaning depends on direct claim vs objection target | record current in nonterminal states | future result forbidden |
| `SUPPORTED` vs `EXTERNAL_EVIDENCE_REQUIRED` | no v0 support-state field | literal governing states and refs | yes as neutral vs readiness deficit | nonterminal/current | medium circularity; terminal firewall required |
| validated/rejected objection states | v0 omits resolved objections from unresolved collection | literal lifecycle and verification link | rejected only removes open penalty; validated meaning comes through assessment | nonterminal/current | high closure-farming if bonus exists |

Only the first and fourth pairs justify directional Value. The second is a
mandatory neutral guardrail; the third and fifth are context/provenance used to
explain the governing summary.

## 15. Frozen Phase 5 value-uninformative cases

`value_uninformative_01` and `value_uninformative_02` contain four successors
with zero contradictions, zero unresolved questions, nonterminal status, and
only opaque fixture-transition digests. Their evaluator-only utilities are
future authored labels, not omitted canonical Hybrid observations.

Wrapping the **exact same semantics** in SearchState v1 yields empty typed
collections or identical assessments for every successor. The actions remain
structurally indistinguishable to lawful Value v1. The correct actions remain
unidentifiable. Adding support states that track their utilities would change
the frozen cases and import future labels, which is forbidden.

Verdict:

```text
SearchState v1 does not lawfully solve either frozen value-uninformative case.
```

This is a positive firewall result. Phase 6's real alias pairs justify a new
evaluation family; they do not retroactively make evaluator-only Phase 5
outcomes observable. No accuracy projection for the frozen 20 cases is made.

## 16. Temporal leakage and benchmark contamination firewall

Future Value v1 must reject any implementation or fixture that uses:

- later verification, assessment, support, objection, or contradiction state;
- final release or episode reward;
- benchmark case/category/outcome/optimum labels;
- action IDs or state digests derived from labels;
- prose heuristics, scores, consensus, confidence, markers, model/provider
  identity, or ratification.

The frozen Phase 5 set may run only as compatibility and historical diagnostic.
It cannot be the sole or primary promotion evidence because its cases and
outcomes have been repeatedly inspected.

## 17. New evaluation methodology

The required new semantic family is:

```text
socrateszero-value-v1-eval-case-set/v0
socrateszero-value-v1-eval-harness/v0
```

Every state must be built from real CED SessionState and Hybrid record models
and passed through `project_search_state_v1()`. Directly inventing convenient
SearchStateV1 fields is not sufficient evidence.

The suite freezes nine adversarial categories:

1. canonical support-state distinctions that should help;
2. v1 signals irrelevant to ranking;
3. misleading lifecycle closure;
4. duplicate/derived representations of one event;
5. terminal support only;
6. intermediate verification/assessment states;
7. states where v0 and v1 should remain equivalent;
8. resolution that may only remove a penalty;
9. evidence/verification quantity inflation that must not increase Value.

Freeze exactly two development pairs and three holdout pairs per category:

```text
development: 18 pairs
holdout:     27 pairs
total:       45 pairs
```

The case schema must distinguish ordered pairs from required ties. Evaluator
ordering/tie labels live outside strategy-facing views, state IDs, action IDs,
and successor blueprints.

The chronological firewall is mandatory:

1. this report freezes rule families, constants, precedence and hypothesis;
2. next branch commits case schema, development fixtures, holdout fixtures and
   their semantic digests before estimator code;
3. estimator code may use development fixtures only to verify implementation,
   never to tune frozen constants;
4. holdout is executed once after implementation and all focused gates pass;
5. no post-holdout coefficient, case, category, or expected-order change is
   permitted on the result lineage.

This is chronological holdout isolation, not a claim of human blinding. The
small authored suite remains structural evidence, not population or end-to-end
evidence.

## 18. Primary hypothesis and metrics

Pre-registered primary hypothesis:

> On a new frozen canonical-state-pair holdout dominated by nonterminal states,
> a penalty-only `heuristic-value-estimator/v1` that uses one worst active
> governing `SupportState`, suppresses all source-overlapping record signals,
> and never rewards closure or quantity will reduce lawful state-value aliasing
> and improve pairwise ranking over `heuristic-value-estimator/v0` without
> directional errors on equivalence, duplication, closure, or count-farming
> controls.

Primary metrics, reported separately for development, holdout, nonterminal,
terminal-only and each category:

- ordered-pair ranking accuracy;
- required-tie accuracy;
- directional error count;
- ties on ordered pairs;
- bounded pairwise ranking loss/regret where the evaluator supplies magnitude.

For v0, evaluate the embedded `SearchStateV1.base_state`; for v1, evaluate the
same envelope. Case, Policy, strategy, budget, and successor semantics remain
identical.

Promotion success requires all of:

- holdout ordered-pair accuracy at least `80%`;
- at least `20` percentage points improvement over Value v0 on holdout ordered
  pairs;
- nonterminal holdout ordered accuracy at least `80%` and at least `20` points
  above v0 independently of terminal cases;
- `100%` required-tie accuracy on lifecycle-closure/no-record,
  duplicate-derived, evidence-count, and v0/v1-equivalent guardrails;
- zero positive numeric components and zero forbidden-input use;
- no case failure, missing denominator, mutation, or receipt mismatch.

## 19. Secondary BestOfN test

Only after Value-pair success, construct matched one-ply successor quartets from
the same frozen holdout family. Freeze:

```text
UniformPolicyPrior/v0
BestOfNStrategy/v0
N=4
depth=1
matched successor budget=4
same Constitution and successor semantics
```

Compare only Value v0 versus Value v1. Uniform Policy is selected to avoid the
known harmful Heuristic-Policy confound and make Value the only ranking factor.

Secondary success requires at least `10` percentage points improvement in
holdout selected-successor accuracy, no guardrail-category regression, and
identical resource usage. It is secondary evidence: pairwise Value ranking is
the primary gate. PUCT is not run until both gates pass; PUCT cannot rescue a
failed Value hypothesis.

## 20. Value v1 audit contract required for implementation

A later immutable audit must expose:

```text
estimator_id
search_state_version
projection_version
v1 state_id
embedded v0 state_id
base_value
canonical reason codes
source claim / record IDs
component contributions
suppressed duplicate signal IDs and representative reason
raw value
bounded value
receipt hash
```

It must contain no prose reasoning. Reordering inputs must not change the audit
or receipt hash. Value remains advisory and cannot create evidence, change a
verification/assessment/support state, transition a lifecycle, alter release,
legalize or execute an action.

## 21. Falsification criteria

The Value v1 hypothesis is falsified if any of these occurs:

- holdout pairwise thresholds fail;
- improvement exists only on terminal states;
- required neutral closure/count/duplicate/equivalence pairs do not tie;
- unsupported penalties systematically rank legitimate intermediate
  exploration below less promising controls;
- any rule needs prose, provider identity, consensus, score, future state or
  label information;
- direct evidence/verification/lifecycle signals cannot be suppressed cleanly;
- performance disappears on the holdout;
- Value v1 worsens neutral/ambiguous states;
- results mainly reproduce terminal SupportState/release labels;
- secondary BestOfN improvement requires Policy/search/budget changes;
- the Phase 5 artifact or any frozen v0 component changes.

A negative result ends the estimator branch. It does not authorize coefficient
tuning on holdout, positive rewards, learned Value, deeper search, or RL.

## 22. Decision matrix and readiness

| Option | Information gain | Architectural risk | Leakage | Double count | Reward hacking | Size | API cost | Explains Phase 5 ceiling | RL usefulness | Falsifiability | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A. deterministic Value v1 | high for lawful semantics | low-medium | low with firewall | medium, controllable | medium, controllable | medium | zero | high for representation/estimator ceiling | medium | high | **selected** |
| B. learned Value now | low without targets | high | high | opaque/high | high | high | zero to high | confounded | low now | low | reject |
| C. Policy work | low; Phase 5 heuristic was harmful | medium | medium | low | medium | medium | zero | weak | low | medium | reject |
| D. deeper successor semantics | high long-term | very high; no canonical executor | medium | medium | medium | high | potentially high | tests horizon, not current Value semantics | high later | medium | blocked |
| E. shadow counterfactual collection | very high external validity | high; isolation absent | medium | medium | medium | high | high | high later | high later | medium | defer |
| F. no Value change | low | very low | very low | none | none | none | zero | leaves proven alias unused | none | low | not selected |

Deterministic Value must precede learned Value. It is transparent, needs no
training corpus, exposes every semantic assumption, has lower leakage risk, and
can falsify whether the restored representation is useful. Learned Value would
hide uncertainty about feature direction behind missing data and model
capacity.

Even a successful deterministic Value v1 does **not** earn RL. Still missing
are a canonical isolated successor environment, real counterfactual
trajectories, a governed reward, stable training targets, holdout/generalization
evidence, and production promotion authority. RL remains `NOT YET EARNED`.

## Final decision and next milestone

Phase 6.5 verification:

- Phase 6 canonical observability: `17 passed`;
- complete Phase 5 evaluation integrity bundle: `37 passed`;
- Phase 5 normalized artifact SHA-256:
  `21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c`;
- artifact Git blob at `17be287` and current HEAD:
  `0488de8a555658a55312d8b1da8614ab9347743b`;
- `git diff --check`: passed;
- core/code changes: `0`;
- live/provider calls: `0`.

The broader Phase 6 checkpoint remains `2629 passed, 1 skipped, 23`
pre-existing warnings repository-wide. Phase 6.5 changes documentation only.

```text
VALUE V1 IMPLEMENTATION EARNED

NEXT BRANCH:
feature/socrates-zero-heuristic-value-v1

CANDIDATE ESTIMATOR ID:
heuristic-value-estimator/v1

SHAPE:
penalty-only, base 0.0, range [-1,+1]

PRIMARY METRIC:
new holdout nonterminal ordered-pair ranking accuracy

SECONDARY TEST:
matched BestOfN/v0 with UniformPolicyPrior/v0, N=4, depth=1, budget=4
```

Explicit non-goals remain: no positive support/verification/closure reward, no
Policy change, no Greedy/BestOfN/PUCT change, no SearchState/projection change,
no CED/Hybrid change, no Phase 5 rewrite, no providers/live calls, no learned
Value, no RL, and no production authority.
