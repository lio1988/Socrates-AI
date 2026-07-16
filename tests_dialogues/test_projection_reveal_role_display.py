"""
Council Live View Foundation — audited contract tests: reveal + role display.

Explicit audit cases covered here:
- alias scope differs by evaluator (and by phase/round/purpose)
- mapping tamper detection; forged registration refused
- reveal before close refused; NEVER policy remains unrevealable
- reveal layer is not a scheduler (tripwire on upstream self-subject bug)
- role_history malformed row refused (no silent repair)
- role display never recalculates roles (verbatim projection, even of rows a
  scheduler would never produce)
- projection matches a REAL offline CEDOrchestrator run exactly
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.dialogues.projection import (
    AnonymousMapping,
    EvaluationPurpose,
    RevealPolicy,
    RevealPolicyStore,
    RevealSealedError,
    SelfSubjectError,
    anonymous_subject_id,
    build_mapping,
    derive_permutation_seed,
    group_by_round,
    permute_subjects,
    project_role_history,
    verify_mapping,
)

SUBJECTS = ["agent_0", "agent_1", "agent_2"]


def _mapping(evaluator="agent_3", purpose=EvaluationPurpose.SECTION_SCORE,
             policy=RevealPolicy.AFTER_EVALUATION_CLOSE):
    return build_mapping(
        session_id="sess_x",
        phase="synthesis",
        round_index=0,
        evaluator_id=evaluator,
        purpose=purpose,
        real_subject_agent_ids=list(SUBJECTS),
        reveal_policy=policy,
    )


_CTX = dict(session_id="sess_x", phase="synthesis", round_index=0,
            evaluator_id="agent_3", purpose=EvaluationPurpose.SECTION_SCORE)


# ── deterministic per-evaluator permutation + alias scoping ─────────────────

class TestPermutationAndAliasScope:
    def test_same_inputs_same_permutation(self):
        seed = derive_permutation_seed(
            "sess_x", "synthesis", 0, "agent_3",
            EvaluationPurpose.SECTION_SCORE)
        assert permute_subjects(seed, SUBJECTS) == \
               permute_subjects(seed, SUBJECTS)

    def test_input_order_does_not_matter(self):
        seed = derive_permutation_seed(
            "sess_x", "synthesis", 0, "agent_3",
            EvaluationPurpose.SECTION_SCORE)
        assert permute_subjects(seed, SUBJECTS) == \
               permute_subjects(seed, list(reversed(SUBJECTS)))

    def test_seed_components_all_matter(self):
        base = derive_permutation_seed(
            "sess_x", "synthesis", 0, "agent_3",
            EvaluationPurpose.SECTION_SCORE)
        variants = [
            derive_permutation_seed("sess_y", "synthesis", 0, "agent_3",
                                    EvaluationPurpose.SECTION_SCORE),
            derive_permutation_seed("sess_x", "elenchus", 0, "agent_3",
                                    EvaluationPurpose.SECTION_SCORE),
            derive_permutation_seed("sess_x", "synthesis", 1, "agent_3",
                                    EvaluationPurpose.SECTION_SCORE),
            derive_permutation_seed("sess_x", "synthesis", 0, "agent_2",
                                    EvaluationPurpose.SECTION_SCORE),
            derive_permutation_seed("sess_x", "synthesis", 0, "agent_3",
                                    EvaluationPurpose.MOVE_SCORE),
        ]
        assert all(v != base for v in variants)

    def test_alias_scope_differs_by_evaluator(self):
        """The SAME subject gets a DIFFERENT anonymous id per evaluator."""
        seed_a = derive_permutation_seed(
            "sess_x", "synthesis", 0, "eval_a",
            EvaluationPurpose.SECTION_SCORE)
        seed_b = derive_permutation_seed(
            "sess_x", "synthesis", 0, "eval_b",
            EvaluationPurpose.SECTION_SCORE)
        assert anonymous_subject_id(seed_a, "agent_0") != \
               anonymous_subject_id(seed_b, "agent_0")

    def test_alias_scope_differs_by_phase_round_purpose(self):
        contexts = [
            ("synthesis", 0, EvaluationPurpose.SECTION_SCORE),
            ("elenchus", 0, EvaluationPurpose.SECTION_SCORE),
            ("synthesis", 1, EvaluationPurpose.SECTION_SCORE),
            ("synthesis", 0, EvaluationPurpose.MOVE_SCORE),
        ]
        aliases = {
            anonymous_subject_id(
                derive_permutation_seed("sess_x", phase, rnd, "eval_a", purp),
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
                "sess_x", "synthesis", 0, evaluator,
                EvaluationPurpose.SECTION_SCORE)
            orders.add(tuple(permute_subjects(seed, subjects)))
        assert len(orders) > 1


# ── mapping: sealing, forgery, non-scheduler tripwire ───────────────────────

class TestMapping:
    def test_build_is_deterministic(self):
        m1, m2 = _mapping(), _mapping()
        assert m1.assignments == m2.assignments
        assert m1.presentation_order == m2.presentation_order
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

    def test_mapping_is_frozen(self):
        m = _mapping()
        with pytest.raises(ValidationError, match="frozen"):
            m.mapping_digest = "0" * 64

    def test_self_subject_tripwire_refuses_never_repairs(self):
        """
        Not-a-scheduler rule: a self-subject in the input is an UPSTREAM
        eligibility bug. The reveal layer raises; it must not silently drop
        the evaluator from the subject list (that would be scheduling).
        """
        with pytest.raises(SelfSubjectError, match="own output"):
            build_mapping(
                session_id="sess_x", phase="synthesis", round_index=0,
                evaluator_id="agent_0",           # also a subject author
                purpose=EvaluationPurpose.SECTION_SCORE,
                real_subject_agent_ids=list(SUBJECTS),
            )

    def test_duplicate_subjects_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            build_mapping(
                session_id="sess_x", phase="synthesis", round_index=0,
                evaluator_id="agent_3",
                purpose=EvaluationPurpose.SECTION_SCORE,
                real_subject_agent_ids=["agent_0", "agent_0"],
            )


# ── store: controlled reveal ────────────────────────────────────────────────

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
            session_id="sess_x", phase="synthesis", round_index=0,
            evaluator_id="agent_3",
            purpose=EvaluationPurpose.SECTION_SCORE,
            real_subject_agent_ids=["agent_0", "agent_1"],  # different set
        )
        with pytest.raises(ValueError, match="conflicting"):
            store.register(conflicting)

    def test_unknown_context_raises(self):
        store = RevealPolicyStore()
        with pytest.raises(KeyError):
            store.evaluator_view(**_CTX)


# ── role display: projection of canonical role_history ─────────────────────

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

    def test_malformed_row_is_refused_not_repaired(self):
        with pytest.raises(ValueError, match="missing required keys"):
            project_role_history([{"phase": "opening", "round_index": 0}])

    def test_rows_are_frozen(self):
        row = project_role_history(self.ROWS)[0]
        with pytest.raises(ValidationError, match="frozen"):
            row.agent_id = "agent_hijack"

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
        from backend.dialogues.projection import RoleDisplayRow
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
