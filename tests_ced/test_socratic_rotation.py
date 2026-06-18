"""Proves: the Socratic role rotates and no agent holds permanent authority."""

from backend.agents.base_agent import Agent, Role
from backend.agents.model_adapter import MockModel
from backend.orchestrator.socratic_rotation import SocraticRotation
from backend.constitution import audit
from backend.epistemic.epistemic_graph import EpistemicGraph


def build_agents(n=3):
    return [Agent(f"a{i}", MockModel(f"m{i}")) for i in range(n)]


def test_role_rotates_across_agents():
    agents = build_agents(3)
    rot = SocraticRotation(agents)
    chosen = [rot.next_socrates().agent_id for _ in range(3)]
    assert chosen == ["a0", "a1", "a2"]


def test_only_one_socrates_per_round():
    agents = build_agents(3)
    rot = SocraticRotation(agents)
    rot.next_socrates()
    socratic = [a for a in agents if a.role == Role.SOCRATES]
    assert len(socratic) == 1


def test_no_permanent_authority_flagged():
    agents = build_agents(3)
    rot = SocraticRotation(agents)
    for _ in range(6):
        rot.next_socrates()
    report = rot.domination_report()
    assert report["balanced"] is True

    # And the constitution audit sees no violation for balanced rotation.
    violations = audit(EpistemicGraph(), rot.history, num_agents=3)
    assert not any(v.principle == "no_permanent_authority" for v in violations)


def test_audit_catches_single_dominator():
    # Simulate a broken run where a0 was always Socrates.
    fake_history = ["a0", "a0", "a0"]
    violations = audit(EpistemicGraph(), fake_history, num_agents=3)
    assert any(v.principle == "no_permanent_authority" for v in violations)
