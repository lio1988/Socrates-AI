from types import SimpleNamespace as NS

import pytest

from backend.dialogues.openclaw_identity.tree_revision_evidence import (
    TreeRevisionObservation,
    build_tree_revision_failure_evidence,
    build_tree_revision_resolution_evidence,
    extract_tree_revision_observations,
    summarize_tree_revision_observations,
)


def score(session, draft, author, voter, section, value):
    return NS(
        session_id=session,
        draft_id=draft,
        author_agent_id=author,
        voter_agent_id=voter,
        section_name=section,
        overall_score=value,
        provider_status="ok",
    )


def card(session, draft, author, voter, values):
    return NS(
        session_id=session,
        draft_id=draft,
        author_agent_id=author,
        voter_agent_id=voter,
        provider_status="ok",
        section_scores=[
            score(session, draft, author, voter, section, value)
            for section, value in values.items()
        ],
    )


def draft(session, draft_id, author, provider=None, move_id=None):
    return NS(
        session_id=session,
        draft_id=draft_id,
        author_agent_id=author,
        provider_id=provider or author,
        move_id=move_id or f"move_{draft_id}",
    )


def session(
    sid="s1",
    question="Q?",
    child_author="agent_b",
    parent_vals=(6, 6),
    child_vals=(8, 8),
    judges=("j1", "j2"),
):
    parent = draft(sid, "p", "agent_a", "prov_a")
    child = draft(sid, "c", child_author, "prov_b")
    cards = []
    for judge, parent_value, child_value in zip(judges, parent_vals, child_vals):
        cards.append(card(
            sid, "p", "agent_a", judge,
            {"core_answer": parent_value, "nuance": parent_value},
        ))
        cards.append(card(
            sid, "c", child_author, judge,
            {"core_answer": child_value, "nuance": child_value},
        ))
    move = NS(
        move_id=child.move_id,
        agent_id=child_author,
        provider_id="prov_b",
        task_kind="tree_revision",
        phase="synthesis",
    )
    task = NS(
        move_id=child.move_id,
        agent_id=child_author,
        provider_id="prov_b",
        task_kind="tree_revision",
        phase="synthesis",
    )
    state = NS(
        session_id=sid,
        question=question,
        section_drafts=[parent, child],
        draft_scorecards=cards,
        moves=[move],
        task_log=[task],
    )
    final = NS(audit_summary={
        "deliberation_tree": {
            "enabled": True,
            "exploration": 0.5,
            "total_expansions": 1,
            "expansion_log": [
                {"parent": "p", "child": "c", "ok": True, "child_score": 99.0}
            ],
        }
    })
    return state, final


def test_extract_recomputes_matched_margin_and_ignores_cached_score():
    state, final = session()
    result = extract_tree_revision_observations(
        state, final, min_matched_scores=4)
    assert len(result) == 1
    observation = result[0]
    assert observation.agent_id == "agent_b"
    assert observation.parent_score == 6
    assert observation.child_score == 8
    assert observation.margin == 2
    assert observation.outcome == "improved"
    assert observation.matched_score_count == 4
    assert observation.judge_ids == ("j1", "j2")
    assert TreeRevisionObservation.from_record(observation.to_record()) == observation


def test_only_exact_matched_judge_section_pairs_count():
    state, final = session(judges=("j1", "j2"))
    state.draft_scorecards[-1].section_scores.pop()
    assert extract_tree_revision_observations(
        state, final, min_matched_scores=4) == ()
    observation = extract_tree_revision_observations(
        state, final, min_matched_scores=3)[0]
    assert observation.matched_score_count == 3


def test_tampered_observation_digest_refused():
    state, final = session()
    record = extract_tree_revision_observations(state, final)[0].to_record()
    record["margin"] = 9
    with pytest.raises(ValueError, match="margin"):
        TreeRevisionObservation.from_record(record)


def test_self_scoring_fails_closed():
    state, final = session()
    state.draft_scorecards[0].voter_agent_id = "agent_a"
    state.draft_scorecards[0].section_scores[0].voter_agent_id = "agent_a"
    state.draft_scorecards[0].section_scores[1].voter_agent_id = "agent_a"
    with pytest.raises(ValueError, match="self-scored"):
        extract_tree_revision_observations(state, final)


def observation(
    sid,
    key,
    margin,
    outcome,
    agent="agent_b",
    judges=("j1", "j2"),
):
    parent = 6.0
    child = parent + margin
    return TreeRevisionObservation(
        session_id=sid,
        comparison_key=key,
        question_hash="a" * 64,
        agent_id=agent,
        provider_id="prov_b",
        parent_draft_id=f"p_{sid}",
        child_draft_id=f"c_{sid}",
        parent_score=parent,
        child_score=child,
        margin=margin,
        outcome=outcome,
        matched_score_count=4,
        judge_ids=judges,
        matched_sections=("core_answer", "nuance"),
        tree_exploration=0.5,
        tree_total_expansions=2,
        scorecard_digest="b" * 64,
        source_trace=f"trace:{sid}",
    )


def test_failure_evidence_requires_repeated_distinct_regressions():
    values = [
        observation("s1", "q1", -1, "regressed"),
        observation("s2", "q2", -2, "regressed"),
    ]
    evidence = build_tree_revision_failure_evidence(
        values,
        reference="tree/fail/1",
        agent_id="agent_b",
        pattern_key="tree_revision_regression",
        weakness="Tree revisions repeatedly reduce matched peer score.",
        verified_by="tree_instrument",
        verification_reference="report.json",
    )
    assert evidence.supports == ("identity:add_known_failure",)
    assert evidence.agent_id == "agent_b"
    assert evidence.source.startswith("CEDDeliberationTreeEvidence/v1/failure/")


def test_failure_evidence_refuses_improvement_or_same_session():
    with pytest.raises(ValueError, match="concrete regressions"):
        build_tree_revision_failure_evidence(
            [
                observation("s1", "q1", -1, "regressed"),
                observation("s2", "q2", 1, "improved"),
            ],
            reference="x",
            agent_id="agent_b",
            pattern_key="p",
            weakness="w",
            verified_by="v",
            verification_reference="r",
        )
    with pytest.raises(ValueError, match="distinct sessions"):
        build_tree_revision_failure_evidence(
            [
                observation("s1", "q1", -1, "regressed"),
                observation("s1", "q2", -1, "regressed"),
            ],
            reference="x",
            agent_id="agent_b",
            pattern_key="p",
            weakness="w",
            verified_by="v",
            verification_reference="r",
        )


def test_resolution_requires_matched_before_after_benchmark_items():
    before = [
        observation("b1", "q1", -1, "regressed"),
        observation("b2", "q2", -1.5, "regressed"),
    ]
    after = [
        observation("a1", "q1", 1, "improved"),
        observation("a2", "q2", 2, "improved"),
    ]
    evidence = build_tree_revision_resolution_evidence(
        before,
        after,
        reference="tree/resolve/1",
        agent_id="agent_b",
        pattern_key="tree_revision_regression",
        weakness="Tree revisions repeatedly reduce matched peer score.",
        verified_by="tree_instrument",
        verification_reference="matched.json",
    )
    assert evidence.supports == (
        "identity:add_known_failure",
        "identity:resolve_known_failure",
    )
    assert evidence.outcomes == ("reverted",)


def test_resolution_refuses_changed_judges_and_unmatched_keys():
    before = [
        observation("b1", "q1", -1, "regressed"),
        observation("b2", "q2", -1, "regressed"),
    ]
    after = [
        observation("a1", "q1", 1, "improved"),
        observation("a2", "q3", 1, "improved"),
    ]
    with pytest.raises(ValueError, match="matched comparison keys"):
        build_tree_revision_resolution_evidence(
            before,
            after,
            reference="x",
            agent_id="agent_b",
            pattern_key="p",
            weakness="w",
            verified_by="v",
            verification_reference="r",
        )
    after = [
        observation("a1", "q1", 1, "improved", judges=("j1", "j3")),
        observation("a2", "q2", 1, "improved"),
    ]
    with pytest.raises(ValueError, match="different judges"):
        build_tree_revision_resolution_evidence(
            before,
            after,
            reference="x",
            agent_id="agent_b",
            pattern_key="p",
            weakness="w",
            verified_by="v",
            verification_reference="r",
        )


def test_summary_is_agent_bound_and_deterministic():
    values = [
        observation("s2", "q2", -1, "regressed"),
        observation("s1", "q1", 2, "improved"),
    ]
    summary = summarize_tree_revision_observations(values, agent_id="agent_b")
    assert summary["sessions"] == ["s1", "s2"]
    assert summary["mean_margin"] == 0.5
    assert summary["counts"] == {
        "improved": 1,
        "neutral": 0,
        "regressed": 1,
    }


def test_no_tree_is_noop_and_missing_move_fails_closed():
    state, final = session()
    final.audit_summary = {"deliberation_tree": {"enabled": False}}
    assert extract_tree_revision_observations(state, final) == ()
    state, final = session()
    state.moves = []
    with pytest.raises(ValueError, match="move/task audit records"):
        extract_tree_revision_observations(state, final)


def test_two_seat_unmatched_judges_produce_no_evidence():
    state, final = session(judges=("j_parent", "j_common"))
    state.draft_scorecards = [
        card("s1", "p", "agent_a", "judge_x", {"core_answer": 6}),
        card("s1", "c", "agent_b", "judge_y", {"core_answer": 8}),
    ]
    assert extract_tree_revision_observations(state, final) == ()


def test_observation_exact_schema_and_secret_labels_fail_closed():
    state, final = session()
    record = extract_tree_revision_observations(state, final)[0].to_record()
    record["unknown"] = 1
    with pytest.raises(ValueError, match="missing or unknown"):
        TreeRevisionObservation.from_record(record)
    with pytest.raises(ValueError, match="secret-shaped"):
        extract_tree_revision_observations(
            state,
            final,
            comparison_key="api_key=abcdefghijklmnop",
        )


def test_resolution_refuses_changed_tree_budget():
    before = [
        observation("b1", "q1", -1, "regressed"),
        observation("b2", "q2", -1, "regressed"),
    ]
    after = [
        observation("a1", "q1", 1, "improved"),
        observation("a2", "q2", 1, "improved"),
    ]
    changed = after[0].to_record()
    changed_observation = TreeRevisionObservation(
        session_id=changed["session_id"],
        comparison_key=changed["comparison_key"],
        question_hash=changed["question_hash"],
        agent_id=changed["agent_id"],
        provider_id=changed["provider_id"],
        parent_draft_id=changed["parent_draft_id"],
        child_draft_id=changed["child_draft_id"],
        parent_score=changed["parent_score"],
        child_score=changed["child_score"],
        margin=changed["margin"],
        outcome=changed["outcome"],
        matched_score_count=changed["matched_score_count"],
        judge_ids=tuple(changed["judge_ids"]),
        matched_sections=tuple(changed["matched_sections"]),
        tree_exploration=changed["tree_exploration"],
        tree_total_expansions=3,
        scorecard_digest=changed["scorecard_digest"],
        source_trace=changed["source_trace"],
    )
    after[0] = changed_observation
    with pytest.raises(ValueError, match="different budgets"):
        build_tree_revision_resolution_evidence(
            before,
            after,
            reference="x",
            agent_id="agent_b",
            pattern_key="p",
            weakness="w",
            verified_by="v",
            verification_reference="r",
        )
