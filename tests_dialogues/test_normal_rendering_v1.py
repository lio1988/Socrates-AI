"""Pure tests for the Normal governing-release rendering boundary."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from socrates.rendering import (
    BLOCKED_NOTICE,
    INCONSISTENT_NOTICE,
    UNAVAILABLE_NOTICE,
    UNRESOLVED_NOTICE,
    render_normal_response,
    sanitize_normal_text,
)


class _Synthesis:
    def __init__(self, text: str) -> None:
        self.text = text

    def full_text(self) -> str:
        return self.text


def _final(
    decision: str = "release_supported",
    status: str = "supported",
    *,
    answer: str = "Ratified answer",
    candidate: str = "Internal assembled candidate",
    ratified: bool = True,
    available: bool = True,
):
    return SimpleNamespace(
        answer=answer,
        synthesis=_Synthesis(candidate),
        ratified=ratified,
        release_decision=decision,
        governing_epistemic_status=status,
        epistemic_status="well_supported",  # legacy and deliberately ignored
        audit_summary={
            "governing_release": {
                "available": available,
                "release_decision": decision,
                "governing_epistemic_status": status,
            }
        },
    )


def test_supported_emits_only_the_sanitized_ratified_final_answer():
    final = _final(
        answer=(
            "Answer with Bearer FAKE-NOT-A-REAL-BEARER-VALUE\n"
            "api_key=FAKE-NOT-A-REAL-API-KEY\n"
            "OPENROUTER_SESSION_TOKEN=FAKE-NOT-A-REAL-TOKEN"
        ),
        candidate=(
            "Different synthesis\n"
            "Cookie: cf_clearance=FAKE-CF; session=FAKE-SESSION\n"
            "token=FAKE-NOT-A-REAL-TOKEN"
        ),
    )

    rendered = render_normal_response(final)

    assert rendered.outcome == "release_supported"
    assert rendered.public_answer == (
        "Answer with Bearer [REDACTED]\n"
        "api_key=[REDACTED]\n"
        "OPENROUTER_SESSION_TOKEN=[REDACTED]"
    )
    assert rendered.notice == ""
    assert rendered.candidate_authorized is True
    assert rendered.candidate == (
        "Different synthesis\n"
        "Cookie: [REDACTED]\n"
        "token=[REDACTED]"
    )
    assert "FAKE-SESSION" not in repr(rendered)


def test_unresolved_emits_ratified_answer_with_prominent_finite_notice():
    rendered = render_normal_response(
        _final("release_unresolved", "unresolved", answer="Useful caveated answer")
    )

    assert rendered.outcome == "release_unresolved"
    assert rendered.public_answer == "Useful caveated answer"
    assert rendered.notice == UNRESOLVED_NOTICE
    assert rendered.notice.startswith("WARNING: GOVERNING RELEASE UNRESOLVED")
    assert rendered.candidate_authorized is True


def test_blocked_withholds_public_candidate_but_preserves_sanitized_synthesis():
    rendered = render_normal_response(
        _final(
            "blocked",
            "falsified",
            answer="This backward-compatible answer must not escape",
            candidate="Assembled secret=FAKE-NOT-A-REAL-SECRET and analysis",
        )
    )

    assert rendered.outcome == "blocked"
    assert rendered.public_answer == ""
    assert rendered.notice == BLOCKED_NOTICE
    assert rendered.candidate_authorized is False
    assert rendered.candidate == "Assembled secret=[REDACTED]"
    assert "Assembled" not in repr(rendered)


@pytest.mark.parametrize("audit_summary", [None, {}, {"governing_release": {}}])
def test_missing_or_unavailable_governing_audit_fails_closed(audit_summary):
    final = _final()
    final.audit_summary = audit_summary

    rendered = render_normal_response(final)

    assert rendered.outcome == "unavailable"
    assert rendered.public_answer == ""
    assert rendered.notice == UNAVAILABLE_NOTICE
    assert rendered.candidate == "Internal assembled candidate"


def test_explicitly_unavailable_audit_ignores_stale_release_fields():
    rendered = render_normal_response(_final(available=False))

    assert rendered.outcome == "unavailable"
    assert rendered.release_decision == "release_supported"
    assert rendered.public_answer == ""
    assert rendered.notice == UNAVAILABLE_NOTICE


@pytest.mark.parametrize(
    ("corruption", "value"),
    [
        ("release_decision", "blocked"),
        ("governing_epistemic_status", "falsified"),
    ],
)
def test_audit_field_mismatch_is_inconsistent_and_withheld(corruption, value):
    final = _final()
    final.audit_summary["governing_release"][corruption] = value

    rendered = render_normal_response(final)

    assert rendered.outcome == "inconsistent"
    assert rendered.public_answer == ""
    assert rendered.notice == INCONSISTENT_NOTICE
    assert rendered.candidate_authorized is False


def test_unknown_release_decision_is_inconsistent_even_when_copies_match():
    rendered = render_normal_response(_final("publish_everything", "supported"))

    assert rendered.outcome == "inconsistent"
    assert rendered.public_answer == ""
    assert rendered.notice == INCONSISTENT_NOTICE


def test_semantically_impossible_release_and_status_pair_is_inconsistent():
    rendered = render_normal_response(_final("release_supported", "falsified"))

    assert rendered.outcome == "inconsistent"
    assert rendered.public_answer == ""
    assert rendered.notice == INCONSISTENT_NOTICE


@pytest.mark.parametrize(
    ("answer", "ratified"),
    [("Candidate answer", False), ("", True), ("   ", True)],
)
def test_supported_or_unresolved_requires_nonblank_ratified_final_answer(
    answer, ratified
):
    rendered = render_normal_response(
        _final("release_unresolved", "unresolved", answer=answer, ratified=ratified)
    )

    assert rendered.outcome == "inconsistent"
    assert rendered.public_answer == ""
    assert rendered.notice == INCONSISTENT_NOTICE
    assert rendered.candidate == "Internal assembled candidate"


def test_malformed_synthesis_falls_back_to_sanitized_final_answer():
    class _BrokenSynthesis:
        def full_text(self):
            raise RuntimeError("Bearer FAKE-NOT-A-REAL-EXCEPTION-SECRET")

    final = _final(answer="Safe answer sk-or-v1-FAKE-NOT-A-REAL-KEY")
    final.synthesis = _BrokenSynthesis()

    rendered = render_normal_response(final)

    assert rendered.candidate == "Safe answer [REDACTED]"
    assert "FAKE-NOT-A-REAL-EXCEPTION-SECRET" not in repr(rendered)


@pytest.mark.parametrize(
    ("visible_text", "forbidden"),
    [
        (
            "Authorization: Basic RkFLRS1OT1QtQS1SRUFM",
            "RkFLRS1OT1QtQS1SRUFM",
        ),
        (
            "Cookie: cf_clearance=FAKE-CF; session=FAKE-SESSION",
            "FAKE-SESSION",
        ),
        ("password is FAKE correct horse battery staple", "correct horse"),
        ("cf_clearance=FAKE-CLOUDFLARE-VALUE", "FAKE-CLOUDFLARE-VALUE"),
        ("__cf_bm=FAKE-CLOUDFLARE-BOT-VALUE", "FAKE-CLOUDFLARE-BOT-VALUE"),
        ("AWS_ACCESS_KEY_ID=FAKE-NOT-A-REAL-ACCESS-KEY", "FAKE-NOT-A-REAL"),
        ("DATABASE_URL=postgres://fake:fake@example.invalid/db", "postgres://"),
    ],
)
def test_sensitive_header_cookie_and_env_lines_are_fully_redacted(
    visible_text, forbidden
):
    rendered = render_normal_response(_final(answer=visible_text))

    assert forbidden not in rendered.public_answer
    assert rendered.public_answer.endswith("[REDACTED]")


@pytest.mark.parametrize(
    ("visible_text", "forbidden"),
    [
        ("AWS id AKIAFAKENOTREAL12345", "AKIAFAKENOTREAL12345"),
        ("Google key AIzaFAKE0000000000000000000000000000000", "AIzaFAKE"),
        ("GitHub ghp_FAKE00000000000000000000000000000000", "ghp_FAKE"),
        ("Slack xoxb-FAKE-NOT-A-REAL-SLACK-TOKEN", "xoxb-FAKE"),
        (
            "postgres://fake-user:fake-password@example.invalid/database",
            "fake-password",
        ),
        (
            "-----BEGIN PRIVATE KEY-----\nFAKE-NOT-A-REAL-KEY\n"
            "-----END PRIVATE KEY-----",
            "FAKE-NOT-A-REAL-KEY",
        ),
    ],
)
def test_unlabelled_high_confidence_credentials_are_redacted(
    visible_text, forbidden
):
    rendered = render_normal_response(_final(answer=visible_text))

    assert forbidden not in rendered.public_answer
    assert "[REDACTED" in rendered.public_answer


@pytest.mark.parametrize(
    "ordinary_text",
    ["M = 11", "E = mc^2", "GDP = nominal output", "ANSWER = yes"],
)
def test_ordinary_equations_and_certificate_fields_are_preserved(ordinary_text):
    rendered = render_normal_response(_final(answer=ordinary_text))

    assert rendered.public_answer == ordinary_text


def test_terminal_escape_sequences_and_control_bytes_are_removed():
    visible_text = (
        "safe\x1b[2J\x1b]0;spoofed-title\x07"
        "answer\x00\x9b31m\x1bPignored\x1b\\"
    )

    assert sanitize_normal_text(visible_text) == "safeanswer"


def test_intended_terminal_whitespace_is_preserved():
    visible_text = "first\nsecond\r\n\tindented"

    assert sanitize_normal_text(visible_text) == visible_text


def test_result_is_immutable():
    rendered = render_normal_response(_final())

    with pytest.raises(Exception):
        rendered.public_answer = "replacement"
