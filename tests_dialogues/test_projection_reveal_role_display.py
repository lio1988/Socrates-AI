"""
Council Live View Foundation — hardened contract tests: reveal + role display.

Hardening round 1 additions (review findings 1, 2, 3, 7, 8):
- NEVER policy cannot be downgraded by re-registration; register never
  overwrites; identical re-registration is idempotent
- deep immutability at the store boundary (mutating registered mappings or
  returned views cannot change the store)
- CANONICAL forgery detection: recomputed digests over non-canonical aliases
  or non-canonical order still fail verification
- structural rejection at the model: duplicate aliases, duplicate real
  subjects, manually constructed self-subject mappings
- canonical JSON seed derivation: no delimiter collisions
- role display: strict validation, no silent repair (float/bool/None/extra)
"""

from __future__ import annotations

import threading

import pytest
from pydantic import ValidationError

from backend.dialogues.projection import (
    AnonymousMapping,
    EvaluationPurpose,
    REVEAL_CONTRACT_SCHEMA,
    RevealPolicy,
    RevealPolicyStore,
    RevealSealedError,
    RoleDisplayRow,
    SelfSubjectError,
    anonymous_subject_id,
    build_mapping,
    derive_permutation_seed,
    group_by_round,
    permute_subjects,
    project_role_history,
    verify_mapping,
)
import backend.dialogues.projection.reveal as reveal_module
from backend.dialogues.projection.reveal import _compute_digests

SUBJECTS = ["agent_0", "agent_1", "agent_2"]


def _mapping(evaluator="agent_3", purpose=EvaluationPurpose.SECTION_SCORE,
             policy=RevealPolicy.AFTER_EVALUATION_CLOSE, run_id="run_1"):
    return build_mapping(
        session_id="sess_x",
        run_id=run_id,
        phase="synthesis",
        round_index=0,
        evaluator_id=evaluator,
        purpose=purpose,
        real_subject_agent_ids=list(SUBJECTS),
        reveal_policy=policy,
    )


_CTX = dict(session_id="sess_x", run_id="run_1", phase="synthesis",
            round_index=0, evaluator_id="agent_3",
            purpose=EvaluationPurpose.SECTION_SCORE)
_CTX_RUN_B = {**_CTX, "run_id": "run_2"}


# ── deterministic per-evaluator permutation + alias scoping ─────────────────

class TestPermutationAndAliasScope:
    def test_same_inputs_same_permutation(self):
        seed = derive_permutation_seed(
            "sess_x", "run_1", "synthesis", 0, "agent_3",
            EvaluationPurpose.SECTION_SCORE)
        assert permute_subjects(seed, SUBJECTS) == \
               permute_subjects(seed, SUBJECTS)

    def test_input_order_does_not_matter(self):
        seed = derive_permutation_seed(
            "sess_x", "run_1", "synthesis", 0, "agent_3",
            EvaluationPurpose.SECTION_SCORE)
        assert permute_subjects(seed, SUBJECTS) == \
               permute_subjects(seed, list(reversed(SUBJECTS)))

    def test_seed_components_all_matter(self):
        base = derive_permutation_seed(
            "sess_x", "run_1", "synthesis", 0, "agent_3",
            EvaluationPurpose.SECTION_SCORE)
        variants = [
            derive_permutation_seed("sess_y", "run_1", "synthesis", 0,
                                    "agent_3",
                                    EvaluationPurpose.SECTION_SCORE),
            derive_permutation_seed("sess_x", "run_2", "synthesis", 0,
                                    "agent_3",
                                    EvaluationPurpose.SECTION_SCORE),
            derive_permutation_seed("sess_x", "run_1", "elenchus", 0,
                                    "agent_3",
                                    EvaluationPurpose.SECTION_SCORE),
            derive_permutation_seed("sess_x", "run_1", "synthesis", 1,
                                    "agent_3",
                                    EvaluationPurpose.SECTION_SCORE),
            derive_permutation_seed("sess_x", "run_1", "synthesis", 0,
                                    "agent_2",
                                    EvaluationPurpose.SECTION_SCORE),
            derive_permutation_seed("sess_x", "run_1", "synthesis", 0,
                                    "agent_3", EvaluationPurpose.MOVE_SCORE),
        ]
        assert all(v != base for v in variants)

    def test_no_delimiter_collision_in_seed_context(self):
        a = derive_permutation_seed("s|x", "r", "p", 0, "e",
                                    EvaluationPurpose.MOVE_SCORE)
        b = derive_permutation_seed("s", "x|r", "p", 0, "e",
                                    EvaluationPurpose.MOVE_SCORE)
        assert a != b

    def test_alias_scope_differs_by_evaluator(self):
        """The SAME subject gets a DIFFERENT anonymous id per evaluator."""
        seed_a = derive_permutation_seed(
            "sess_x", "run_1", "synthesis", 0, "eval_a",
            EvaluationPurpose.SECTION_SCORE)
        seed_b = derive_permutation_seed(
            "sess_x", "run_1", "synthesis", 0, "eval_b",
            EvaluationPurpose.SECTION_SCORE)
        assert anonymous_subject_id(seed_a, "agent_0") != \
               anonymous_subject_id(seed_b, "agent_0")

    def test_alias_scope_differs_by_run(self):
        """Round 3, finding 1: same session, different run → different
        aliases — blind evaluations are RUN-scoped."""
        seed_run1 = derive_permutation_seed(
            "sess_x", "run_1", "synthesis", 0, "agent_3",
            EvaluationPurpose.SECTION_SCORE)
        seed_run2 = derive_permutation_seed(
            "sess_x", "run_2", "synthesis", 0, "agent_3",
            EvaluationPurpose.SECTION_SCORE)
        assert anonymous_subject_id(seed_run1, "agent_0") != \
               anonymous_subject_id(seed_run2, "agent_0")
        m1, m2 = _mapping(run_id="run_1"), _mapping(run_id="run_2")
        assert set(m1.presentation_order).isdisjoint(m2.presentation_order)

    def test_alias_scope_differs_by_phase_round_purpose(self):
        contexts = [
            ("synthesis", 0, EvaluationPurpose.SECTION_SCORE),
            ("elenchus", 0, EvaluationPurpose.SECTION_SCORE),
            ("synthesis", 1, EvaluationPurpose.SECTION_SCORE),
            ("synthesis", 0, EvaluationPurpose.MOVE_SCORE),
        ]
        aliases = {
            anonymous_subject_id(
                derive_permutation_seed("sess_x", "run_1", phase, rnd,
                                        "eval_a", purp),
                "agent_0")
            for phase, rnd, purp in contexts
        }
        assert len(aliases) == len(contexts), \
            "aliases must be scoped per phase/round/purpose, never global"

    def test_evaluators_get_independent_orders(self):
        subjects = [f"agent_{i}" for i in range(8)]
        orders = set()
        for evaluator in ("eval_a", "eval_b", "eval_c", "eval_d"):
            seed = derive_permutation_seed(
                "sess_x", "run_1", "synthesis", 0, evaluator,
                EvaluationPurpose.SECTION_SCORE)
            orders.add(tuple(permute_subjects(seed, subjects)))
        assert len(orders) > 1


# ── mapping: sealing, canonical forgery, structural integrity ───────────────

class TestMapping:
    def test_build_is_deterministic(self):
        m1, m2 = _mapping(), _mapping()
        assert m1 == m2
        assert m1.mapping_digest == m2.mapping_digest
        assert m1.permutation_digest == m2.permutation_digest

    def test_anonymous_ids_do_not_leak_real_ids(self):
        m = _mapping()
        for anon in m.presentation_order:
            assert anon.startswith("anon_")
            for real in SUBJECTS:
                assert real not in anon

    def test_verify_accepts_genuine_mapping(self):
        assert verify_mapping(_mapping()) is True

    def test_verify_rejects_forged_assignment(self):
        m = _mapping()
        forged_assignments = dict(m.assignments)
        first_anon = m.presentation_order[0]
        forged_assignments[first_anon] = "agent_impostor"
        forged = AnonymousMapping(
            **{**m.model_dump(exclude={"assignments"}),
               "assignments": forged_assignments},
        )
        assert verify_mapping(forged) is False

    def test_verify_rejects_forged_digest(self):
        m = _mapping()
        forged = AnonymousMapping(
            **{**m.model_dump(exclude={"mapping_digest"}),
               "mapping_digest": "0" * 64},
        )
        assert verify_mapping(forged) is False

    def test_recomputed_digest_cannot_validate_noncanonical_alias(self):
        """
        Finding 3: SHA-256 is not a MAC. An attacker who invents arbitrary
        aliases and RECOMPUTES both digests must still fail, because
        verification re-derives the canonical aliases from context.
        """
        m = _mapping()
        fake_assignments = {
            f"anon_forged_{i:02d}": real
            for i, real in enumerate(m.assignments.values())
        }
        fake_order = list(fake_assignments.keys())
        pd, md = _compute_digests(
            m.context_key(), m.reveal_policy, fake_assignments, fake_order)
        forged = AnonymousMapping(
            **{**m.model_dump(exclude={
                "assignments", "presentation_order",
                "permutation_digest", "mapping_digest"}),
               "assignments": fake_assignments,
               "presentation_order": fake_order,
               "permutation_digest": pd,
               "mapping_digest": md},
        )
        assert verify_mapping(forged) is False

    def test_recomputed_digest_cannot_validate_noncanonical_order(self):
        """Canonical aliases but attacker-chosen order + recomputed digests
        must still fail verification."""
        m = _mapping()
        reordered = list(reversed(m.presentation_order))
        assert reordered != list(m.presentation_order)
        pd, md = _compute_digests(
            m.context_key(), m.reveal_policy, dict(m.assignments), reordered)
        forged = AnonymousMapping(
            **{**m.model_dump(exclude={
                "presentation_order", "permutation_digest", "mapping_digest"}),
               "presentation_order": reordered,
               "permutation_digest": pd,
               "mapping_digest": md},
        )
        assert verify_mapping(forged) is False

    def test_duplicate_presentation_alias_rejected(self):
        m = _mapping()
        dup_order = list(m.presentation_order)
        dup_order[1] = dup_order[0]
        with pytest.raises(ValidationError, match="duplicate aliases"):
            AnonymousMapping(
                **{**m.model_dump(exclude={"presentation_order"}),
                   "presentation_order": dup_order},
            )

    def test_duplicate_real_subject_values_rejected(self):
        m = _mapping()
        dup_assignments = dict(m.assignments)
        first, second = m.presentation_order[0], m.presentation_order[1]
        dup_assignments[second] = dup_assignments[first]
        with pytest.raises(ValidationError, match="same real subject"):
            AnonymousMapping(
                **{**m.model_dump(exclude={"assignments"}),
                   "assignments": dup_assignments},
            )

    def test_self_subject_in_manually_constructed_mapping_rejected(self):
        m = _mapping()
        self_assignments = dict(m.assignments)
        self_assignments[m.presentation_order[0]] = m.evaluator_id
        with pytest.raises((SelfSubjectError, ValidationError),
                           match="eligibility"):
            AnonymousMapping(
                **{**m.model_dump(exclude={"assignments"}),
                   "assignments": self_assignments},
            )

    def test_mapping_is_frozen(self):
        m = _mapping()
        with pytest.raises(ValidationError, match="frozen"):
            m.mapping_digest = "0" * 64

    def test_mapping_wire_alias_round_trip(self):
        m = _mapping()
        wire = m.model_dump(by_alias=True, mode="json")
        assert wire["schema"] == REVEAL_CONTRACT_SCHEMA
        assert "schema_name" not in wire
        assert AnonymousMapping.model_validate(wire) == m

    def test_self_subject_tripwire_refuses_never_repairs(self):
        with pytest.raises(SelfSubjectError, match="own output"):
            build_mapping(
                session_id="sess_x", run_id="run_1", phase="synthesis",
                round_index=0,
                evaluator_id="agent_0",           # also a subject author
                purpose=EvaluationPurpose.SECTION_SCORE,
                real_subject_agent_ids=list(SUBJECTS),
            )

    def test_duplicate_subjects_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            build_mapping(
                session_id="sess_x", run_id="run_1", phase="synthesis",
                round_index=0,
                evaluator_id="agent_3",
                purpose=EvaluationPurpose.SECTION_SCORE,
                real_subject_agent_ids=["agent_0", "agent_0"],
            )

    def test_negative_round_index_rejected(self):
        with pytest.raises(ValidationError):
            build_mapping(
                session_id="sess_x", run_id="run_1", phase="synthesis",
                round_index=-1,
                evaluator_id="agent_3",
                purpose=EvaluationPurpose.SECTION_SCORE,
                real_subject_agent_ids=list(SUBJECTS),
            )

    def test_empty_subject_list_rejected(self):
        with pytest.raises((ValidationError, ValueError),
                           match="at least one subject"):
            build_mapping(
                session_id="sess_x", run_id="run_1", phase="synthesis",
                round_index=0,
                evaluator_id="agent_3",
                purpose=EvaluationPurpose.SECTION_SCORE,
                real_subject_agent_ids=[],
            )


# ── strict reveal input contract (round 4, finding 1) ───────────────────────

class TestRevealStrictContract:
    def _dumped(self, **overrides):
        """A valid mapping's field dict, with strict-hostile overrides."""
        base = _mapping().model_dump()
        base.update(overrides)
        return base

    def test_string_round_index_rejected(self):
        with pytest.raises(ValidationError):
            AnonymousMapping(**self._dumped(round_index="0"))

    def test_bool_round_index_rejected(self):
        with pytest.raises(ValidationError):
            AnonymousMapping(**self._dumped(round_index=True))

    def test_whitespace_session_id_rejected(self):
        with pytest.raises(ValidationError, match="non-whitespace"):
            AnonymousMapping(**self._dumped(session_id="   "))

    def test_whitespace_phase_rejected(self):
        with pytest.raises(ValidationError, match="non-whitespace"):
            AnonymousMapping(**self._dumped(phase="   "))

    def test_whitespace_evaluator_rejected(self):
        with pytest.raises(ValidationError, match="non-whitespace"):
            AnonymousMapping(**self._dumped(evaluator_id=" \t "))

    def test_sentinel_run_id_rejected(self):
        with pytest.raises(ValidationError, match="sentinel"):
            AnonymousMapping(**self._dumped(run_id="none"))

    def test_blank_real_subject_rejected_at_model(self):
        m = _mapping()
        dumped = m.model_dump()
        first = m.presentation_order[0]
        dumped["assignments"] = {**dumped["assignments"], first: "  "}
        with pytest.raises(ValidationError, match="non-whitespace"):
            AnonymousMapping(**dumped)

    def test_blank_real_subject_rejected_in_build(self):
        with pytest.raises(ValueError, match="non-whitespace"):
            build_mapping(
                session_id="sess_x", run_id="run_1", phase="synthesis",
                round_index=0, evaluator_id="agent_3",
                purpose=EvaluationPurpose.SECTION_SCORE,
                real_subject_agent_ids=["agent_0", "   "],
            )

    def test_malformed_digests_rejected(self):
        with pytest.raises(ValidationError, match="pattern"):
            AnonymousMapping(**self._dumped(mapping_digest="A" * 64))
        with pytest.raises(ValidationError, match="pattern"):
            AnonymousMapping(**self._dumped(permutation_digest="deadbeef"))

    def test_wire_json_enum_strings_still_round_trip(self):
        import json
        m = _mapping()
        wire = m.model_dump(by_alias=True, mode="json")
        assert wire["purpose"] == "section_score"          # raw string on wire
        assert wire["reveal_policy"] == "after_evaluation_close"
        assert AnonymousMapping.model_validate(wire) == m
        assert AnonymousMapping.model_validate_json(json.dumps(wire)) == m


# ── store: controlled reveal + write-once + deep immunity ───────────────────

class TestRevealPolicyStore:
    def test_pre_close_view_is_anonymous_only(self):
        store = RevealPolicyStore()
        m = _mapping()
        store.register(m)
        view = store.evaluator_view(**_CTX)
        assert view == list(m.presentation_order)
        assert all(v.startswith("anon_") for v in view)

    def test_reveal_before_close_is_refused(self):
        store = RevealPolicyStore()
        store.register(_mapping())
        with pytest.raises(RevealSealedError, match="not closed"):
            store.reveal(**_CTX)

    def test_reveal_after_close_returns_mapping(self):
        store = RevealPolicyStore()
        m = _mapping()
        store.register(m)
        store.close_evaluation(**_CTX)
        assert store.reveal(**_CTX) == dict(m.assignments)

    def test_never_policy_remains_unrevealable(self):
        store = RevealPolicyStore()
        store.register(_mapping(policy=RevealPolicy.NEVER))
        store.close_evaluation(**_CTX)
        with pytest.raises(RevealSealedError, match="NEVER"):
            store.reveal(**_CTX)

    def test_never_policy_cannot_be_downgraded_by_reregistration(self):
        """
        Finding 1 (critical): a canonical, digest-valid mapping for the SAME
        context with a WEAKER policy must be a registration conflict — a
        registered NEVER mapping is never overwritten and never revealed.
        """
        store = RevealPolicyStore()
        store.register(_mapping(policy=RevealPolicy.NEVER))
        downgraded = _mapping(policy=RevealPolicy.AFTER_EVALUATION_CLOSE)
        assert verify_mapping(downgraded) is True   # canonical, valid digests
        with pytest.raises(ValueError, match="conflicting"):
            store.register(downgraded)
        store.close_evaluation(**_CTX)
        with pytest.raises(RevealSealedError, match="NEVER"):
            store.reveal(**_CTX)

    def test_identical_reregistration_is_idempotent(self):
        store = RevealPolicyStore()
        store.register(_mapping())
        store.register(_mapping())      # exact same record: no error
        assert store.evaluator_view(**_CTX) == \
               list(_mapping().presentation_order)

    def test_register_rejects_forged_mapping(self):
        store = RevealPolicyStore()
        m = _mapping()
        forged = AnonymousMapping(
            **{**m.model_dump(exclude={"mapping_digest"}),
               "mapping_digest": "0" * 64},
        )
        with pytest.raises(ValueError, match="forgery"):
            store.register(forged)

    def test_register_rejects_conflicting_remap(self):
        store = RevealPolicyStore()
        store.register(_mapping())
        conflicting = build_mapping(
            session_id="sess_x", run_id="run_1", phase="synthesis",
            round_index=0,
            evaluator_id="agent_3",
            purpose=EvaluationPurpose.SECTION_SCORE,
            real_subject_agent_ids=["agent_0", "agent_1"],  # different set
        )
        with pytest.raises(ValueError, match="conflicting"):
            store.register(conflicting)

    def test_same_session_different_run_independent_registration(self):
        """Round 3, finding 1: two runs in one session are independent
        registration contexts — no overwrite, no shared reveal."""
        store = RevealPolicyStore()
        run_a = _mapping(run_id="run_1")
        run_b = _mapping(run_id="run_2")
        store.register(run_a)
        store.register(run_b)   # NOT a conflict: different context
        assert store.evaluator_view(**_CTX) == list(run_a.presentation_order)
        assert store.evaluator_view(**_CTX_RUN_B) == \
               list(run_b.presentation_order)

    def test_closing_run_a_does_not_reveal_run_b(self):
        store = RevealPolicyStore()
        store.register(_mapping(run_id="run_1"))
        store.register(_mapping(run_id="run_2"))
        store.close_evaluation(**_CTX)          # close run A only
        assert store.is_closed(**_CTX) is True
        assert store.is_closed(**_CTX_RUN_B) is False
        with pytest.raises(RevealSealedError, match="not closed"):
            store.reveal(**_CTX_RUN_B)          # run B stays sealed

    def test_never_policy_in_run_a_cannot_affect_run_b(self):
        store = RevealPolicyStore()
        store.register(_mapping(run_id="run_1", policy=RevealPolicy.NEVER))
        run_b = _mapping(run_id="run_2",
                         policy=RevealPolicy.AFTER_EVALUATION_CLOSE)
        store.register(run_b)
        store.close_evaluation(**_CTX_RUN_B)
        # run B reveals normally; run A's NEVER is irrelevant to it.
        assert store.reveal(**_CTX_RUN_B) == dict(run_b.assignments)
        with pytest.raises(RevealSealedError, match="NEVER"):
            store.close_evaluation(**_CTX)
            store.reveal(**_CTX)

    def test_snapshot_before_verify_stored_mapping_stays_canonical(self):
        """Round 3, finding 2 (TOCTOU): mutating the caller's mapping right
        after verification cannot poison the stored snapshot."""
        store = RevealPolicyStore()
        m = _mapping()
        store.register(m)
        # Post-registration mutation of the caller-owned nested containers.
        m.assignments[m.presentation_order[0]] = "agent_impostor"
        m.presentation_order.append("anon_injected")
        store.close_evaluation(**_CTX)
        revealed = store.reveal(**_CTX)
        assert set(revealed.values()) == set(SUBJECTS)
        assert "agent_impostor" not in revealed.values()
        assert store.evaluator_view(**_CTX) == \
               list(_mapping().presentation_order)

    def test_caller_mutation_between_verify_and_store_cannot_poison(
        self, monkeypatch
    ):
        """
        Round 4, finding 2: exercise the EXACT window — mutate the caller's
        mapping the instant verification returns, before the store commits.
        Because register() verifies and stores a private SNAPSHOT taken
        before verification, the injected mutation of the caller object
        cannot reach the store.
        """
        store = RevealPolicyStore()
        caller_mapping = _mapping()
        real_verify = reveal_module.verify_mapping

        def verify_then_mutate(candidate):
            result = real_verify(candidate)
            # Fire inside the verify→store window, on the caller object.
            caller_mapping.assignments[
                caller_mapping.presentation_order[0]
            ] = "agent_impostor"
            caller_mapping.presentation_order.append("anon_injected")
            return result

        monkeypatch.setattr(reveal_module, "verify_mapping",
                            verify_then_mutate)
        store.register(caller_mapping)

        store.close_evaluation(**_CTX)
        revealed = store.reveal(**_CTX)
        assert "agent_impostor" not in revealed.values()
        assert set(revealed.values()) == set(SUBJECTS)
        assert "anon_injected" not in store.evaluator_view(**_CTX)

    def test_mutating_mapping_after_register_cannot_change_store(self):
        store = RevealPolicyStore()
        m = _mapping()
        store.register(m)
        # frozen blocks attribute assignment, but the dict itself is
        # reachable on the CALLER's object — the store must hold its own copy.
        m.assignments[m.presentation_order[0]] = "agent_impostor"
        store.close_evaluation(**_CTX)
        revealed = store.reveal(**_CTX)
        assert "agent_impostor" not in revealed.values()
        assert set(revealed.values()) == set(SUBJECTS)

    def test_mutating_evaluator_view_cannot_change_store(self):
        store = RevealPolicyStore()
        m = _mapping()
        store.register(m)
        view = store.evaluator_view(**_CTX)
        view.clear()
        view.append("anon_fake")
        assert store.evaluator_view(**_CTX) == list(m.presentation_order)

    def test_mutating_revealed_dict_cannot_change_store(self):
        store = RevealPolicyStore()
        m = _mapping()
        store.register(m)
        store.close_evaluation(**_CTX)
        revealed = store.reveal(**_CTX)
        revealed[m.presentation_order[0]] = "agent_impostor"
        assert store.reveal(**_CTX) == dict(m.assignments)

    def test_unknown_context_raises(self):
        store = RevealPolicyStore()
        with pytest.raises(KeyError):
            store.evaluator_view(**_CTX)


class TestRevealStoreConcurrency:
    """Round 2, finding 3: check-then-write is atomic — racing registrations
    can never overwrite each other."""

    def test_concurrent_identical_registration_is_idempotent(self):
        store = RevealPolicyStore()
        n = 8
        barrier = threading.Barrier(n)
        errors = []

        def worker():
            barrier.wait()
            try:
                store.register(_mapping())
            except Exception as exc:      # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert store.evaluator_view(**_CTX) == \
               list(_mapping().presentation_order)

    def test_concurrent_conflicting_registration_one_winner_one_conflict(self):
        store = RevealPolicyStore()
        mapping_a = _mapping()
        mapping_b = build_mapping(
            session_id="sess_x", run_id="run_1", phase="synthesis",
            round_index=0,
            evaluator_id="agent_3",
            purpose=EvaluationPurpose.SECTION_SCORE,
            real_subject_agent_ids=["agent_0", "agent_1"],  # different set
        )
        barrier = threading.Barrier(2)
        errors = []

        def worker(mapping):
            barrier.wait()
            try:
                store.register(mapping)
            except ValueError as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(m,))
                   for m in (mapping_a, mapping_b)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 1 and "conflicting" in str(errors[0])
        stored_view = store.evaluator_view(**_CTX)
        assert stored_view in (list(mapping_a.presentation_order),
                               list(mapping_b.presentation_order))

    def test_concurrent_never_vs_revealable_cannot_downgrade_policy(self):
        store = RevealPolicyStore()
        never = _mapping(policy=RevealPolicy.NEVER)
        revealable = _mapping(policy=RevealPolicy.AFTER_EVALUATION_CLOSE)
        barrier = threading.Barrier(2)
        errors = []

        def worker(mapping):
            barrier.wait()
            try:
                store.register(mapping)
            except ValueError as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(m,))
                   for m in (never, revealable)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Exactly one won; the loser conflicted — no silent overwrite.
        assert len(errors) == 1 and "conflicting" in str(errors[0])
        # Re-registering both proves write-once: one idempotent, one conflict.
        outcomes = []
        for m in (never, revealable):
            try:
                store.register(m)
                outcomes.append("idempotent")
            except ValueError:
                outcomes.append("conflict")
        assert sorted(outcomes) == ["conflict", "idempotent"]
        # If NEVER won, identities stay sealed forever.
        store.close_evaluation(**_CTX)
        try:
            store.register(never)
            never_won = True
        except ValueError:
            never_won = False
        if never_won:
            with pytest.raises(RevealSealedError, match="NEVER"):
                store.reveal(**_CTX)
        else:
            assert store.reveal(**_CTX) == dict(revealable.assignments)


# ── role display: strict projection, no silent repair (finding 7) ──────────

class TestRoleDisplay:
    ROWS = [
        {"phase": "opening", "round_index": 0,
         "agent_id": "agent_2", "role": "socrates"},
        {"phase": "elenchus", "round_index": 0,
         "agent_id": "agent_0", "role": "elenchus_critic"},
        {"phase": "elenchus", "round_index": 1,
         "agent_id": "agent_1", "role": "elenchus_critic"},
    ]

    def test_projection_preserves_canonical_order_and_values(self):
        rows = project_role_history(self.ROWS)
        assert [(r.phase, r.round_index, r.agent_id, r.role)
                for r in rows] == [
            ("opening", 0, "agent_2", "socrates"),
            ("elenchus", 0, "agent_0", "elenchus_critic"),
            ("elenchus", 1, "agent_1", "elenchus_critic"),
        ]
        assert [r.recorded_index for r in rows] == [0, 1, 2]

    def test_missing_key_refused_not_repaired(self):
        with pytest.raises(ValueError,
                           match="violates the role display contract"):
            project_role_history([{"phase": "opening", "round_index": 0}])

    def test_float_round_index_rejected(self):
        with pytest.raises(ValueError,
                           match="violates the role display contract"):
            project_role_history([{**self.ROWS[0], "round_index": 1.9}])

    def test_bool_round_index_rejected(self):
        with pytest.raises(ValueError,
                           match="violates the role display contract"):
            project_role_history([{**self.ROWS[0], "round_index": True}])

    def test_none_role_rejected(self):
        with pytest.raises(ValueError,
                           match="violates the role display contract"):
            project_role_history([{**self.ROWS[0], "role": None}])

    def test_noncanonical_role_word_rejected(self):
        with pytest.raises(ValueError,
                           match="violates the role display contract"):
            project_role_history([{**self.ROWS[0], "role": "chairman"}])

    def test_extra_canonical_row_field_rejected(self):
        with pytest.raises(ValueError,
                           match="violates the role display contract"):
            project_role_history([{**self.ROWS[0], "leaked_score": 9.1}])

    def test_raw_recorded_index_rejected(self):
        # Round 2, finding 7: a forged reserved field is REJECTED, never
        # silently replaced by the backend-owned value.
        with pytest.raises(ValueError, match="reserved or unknown"):
            project_role_history([{**self.ROWS[0], "recorded_index": 99}])

    def test_raw_schema_field_rejected(self):
        with pytest.raises(ValueError, match="reserved or unknown"):
            project_role_history([{**self.ROWS[0],
                                   "schema": "ced_role_display_v1"}])
        with pytest.raises(ValueError, match="reserved or unknown"):
            project_role_history([{**self.ROWS[0],
                                   "schema_name": "ced_role_display_v1"}])

    def test_rows_are_frozen(self):
        row = project_role_history(self.ROWS)[0]
        with pytest.raises(ValidationError, match="frozen"):
            row.agent_id = "agent_hijack"

    def test_row_wire_alias_round_trip(self):
        row = project_role_history(self.ROWS)[0]
        wire = row.model_dump(by_alias=True, mode="json")
        assert wire["schema"] == "ced_role_display_v1"
        assert RoleDisplayRow.model_validate(wire) == row

    def test_group_by_round(self):
        grouped = group_by_round(project_role_history(self.ROWS))
        assert sorted(grouped.keys()) == [0, 1]
        assert [r.agent_id for r in grouped[0]] == ["agent_2", "agent_0"]
        assert [r.agent_id for r in grouped[1]] == ["agent_1"]

    def test_role_display_never_recalculates_roles(self):
        """
        Verbatim projection even of a record the deterministic scheduler would
        NEVER produce (one agent as Socrates in every phase). The canonical
        record is the authority — the display must not "correct" it toward
        what assign_roles_for_phase would compute.
        """
        pinned = [
            {"phase": phase, "round_index": 0,
             "agent_id": "agent_0", "role": "socrates"}
            for phase in ("opening", "elenchus", "synthesis")
        ]
        rows = project_role_history(pinned)
        assert all(r.agent_id == "agent_0" and r.role == "socrates"
                   for r in rows)
        assert len(rows) == 3   # nothing dropped, nothing reassigned

    def test_no_inferred_primary_role(self):
        """The projection exposes only recorded per-phase rows — it computes
        no aggregate/primary role for an agent."""
        assert "primary_role" not in RoleDisplayRow.model_fields
        rows = project_role_history(self.ROWS)
        agent_1_rows = [r for r in rows if r.agent_id == "agent_1"]
        assert [r.role for r in agent_1_rows] == ["elenchus_critic"]


class TestRoleDisplayAgainstRealCed:
    """§6.2: the display must derive from a REAL canonical role_history."""

    @staticmethod
    def _run(session_id: str):
        from backend.dialogues import CEDOrchestrator, FakeProvider, SocraticAgent
        provider = FakeProvider()
        agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
        ced = CEDOrchestrator(agents, provider)
        ced.run_session("Is knowledge merely justified true belief?",
                        session_id=session_id)
        return ced.get_session(session_id)

    def test_projection_matches_canonical_role_history_exactly(self):
        state = self._run("proj_display_sess")
        rows = project_role_history(state.role_history)
        assert len(rows) == len(state.role_history) > 0
        for raw, row in zip(state.role_history, rows):
            assert row.phase == raw["phase"]
            assert row.round_index == raw["round_index"]
            assert row.agent_id == raw["agent_id"]
            assert row.role == raw["role"]

    def test_projection_is_deterministic_across_identical_runs(self):
        rows_a = project_role_history(
            self._run("proj_det_sess").role_history)
        rows_a2 = project_role_history(
            self._run("proj_det_sess").role_history)
        assert rows_a == rows_a2

    def test_different_sessions_rotate_socrates(self):
        def socrates_holder(session_id):
            rows = project_role_history(self._run(session_id).role_history)
            return next(r.agent_id for r in rows
                        if r.phase == "opening" and r.role == "socrates")
        holders = {socrates_holder(f"proj_rotate_{i}") for i in range(6)}
        assert len(holders) > 1, (
            "Socrates appears pinned across sessions — rotation invariant "
            "violated or projection is not reading canonical data"
        )
