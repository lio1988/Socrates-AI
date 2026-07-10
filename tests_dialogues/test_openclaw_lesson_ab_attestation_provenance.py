"""Focused provenance tests for the single-agent Lesson A/B bridge."""

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

from backend.dialogues.openclaw_identity import AGENT_LESSON_AB_REPORT_VERSION

_ROOT = Path(__file__).resolve().parents[1]
AGENT = "local_apprentice_001"


def _module():
    path = _ROOT / "scripts" / "openclaw_attest_lesson_ab.py"
    spec = importlib.util.spec_from_file_location(
        "openclaw_attest_lesson_ab_provenance", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _report(observed_on):
    return {
        "schema_version": AGENT_LESSON_AB_REPORT_VERSION,
        "target_agent_id": AGENT,
        "verified_by": "Operator",
        "observed_on": observed_on,
    }


def test_report_requires_nonempty_observation_date():
    module = _module()
    with pytest.raises(ValueError, match="requires observed_on"):
        module._validate_report_identity(
            _report(""), agent_id=AGENT, verified_by="Operator")


def test_report_requires_iso_observation_date():
    module = _module()
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        module._validate_report_identity(
            _report("10/07/2026"), agent_id=AGENT, verified_by="Operator")

    module._validate_report_identity(
        _report(dt.date.today().isoformat()),
        agent_id=AGENT,
        verified_by="operator",
    )


def test_report_cannot_claim_future_observation():
    module = _module()
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="cannot be in the future"):
        module._validate_report_identity(
            _report(tomorrow), agent_id=AGENT, verified_by="Operator")
