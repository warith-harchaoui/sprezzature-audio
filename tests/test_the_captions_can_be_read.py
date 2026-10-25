"""
The audit half: captions that are accurate and still unreadable.

This package drafts captions, diarizes speakers and translates tracks, and
every one of those is judged on accuracy. None of them is judged on whether a
viewer can actually read the result as it goes by — which is a different
question with a different answer. A perfectly transcribed sentence held for
four tenths of a second is a flash; two perfectly transcribed cues that
overlap are two lines fighting for the same space.

Whether a `<track>` element exists is `sprezzature-accessibility`'s question.
Whether what is inside it is usable is this package's, and these tests hold
that line.

Each test is a track that is wrong in exactly one way. A clean track must
produce nothing, or the suite is measuring its own fixtures.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit_captions import audit, parse  # noqa: E402


def track(*cues: tuple[str, str, str]) -> list:
    """Build a WebVTT document from (start, end, text) triples."""
    body = "WEBVTT\n\n"
    for start, end, text in cues:
        body += f"{start} --> {end}\n{text}\n\n"
    return parse(body)


CLEAN = (
    ("00:00:00.000", "00:00:02.500", "A short line that reads easily."),
    ("00:00:02.600", "00:00:05.000", "And a second one, also fine."),
)


def test_a_clean_track_reports_nothing() -> None:
    """The baseline, without which no other test here proves anything."""
    assert audit(track(*CLEAN)) == []


def test_subrip_is_read_too() -> None:
    """
    This package emits both formats, so the audit accepts both.

    A reader holding an .srt has no reason to convert it before checking it,
    and a check nobody can run on the file they have is a check nobody runs.
    """
    srt = (
        "1\n00:00:00,000 --> 00:00:02,000\nSubrip works too.\n\n"
        "2\n00:00:02,100 --> 00:00:04,000\nSecond cue.\n"
    )
    cues = parse(srt)
    assert len(cues) == 2
    assert audit(cues) == []


@pytest.mark.parametrize(
    ("rule", "cues"),
    [
        (
            "cue-overlap",
            (
                ("00:00:00.000", "00:00:03.000", "First."),
                ("00:00:02.000", "00:00:04.000", "Second."),
            ),
        ),
        (
            "cue-reversed",
            (("00:00:05.000", "00:00:03.000", "Backwards."),),
        ),
        (
            "cue-too-brief",
            (("00:00:00.000", "00:00:00.200", "Flash."),),
        ),
        (
            "cue-too-long",
            (("00:00:00.000", "00:00:12.000", "Lingering."),),
        ),
        (
            "cue-too-fast",
            (
                (
                    "00:00:00.000",
                    "00:00:01.000",
                    "Far too many characters for one single second of screen time.",
                ),
            ),
        ),
        (
            "line-too-wide",
            (
                (
                    "00:00:00.000",
                    "00:00:09.000",
                    "A single line well past the forty-two character budget any player honours.",
                ),
            ),
        ),
        (
            "too-many-lines",
            (("00:00:00.000", "00:00:04.000", "one\ntwo\nthree"),),
        ),
    ],
)
def test_each_rule_fires_on_its_own_defect(rule: str, cues) -> None:
    """One track, one defect, one rule — so a rule cannot pass by accident."""
    reported = {f.rule for f in audit(track(*cues))}
    assert rule in reported, f"expected {rule}, got {sorted(reported) or 'nothing'}"


def test_an_empty_cue_is_reported() -> None:
    """A timed blank box is on screen for its full duration."""
    cues = parse("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n\n\n")
    assert "cue-empty" in {f.rule for f in audit(cues)}


def test_the_thresholds_are_conventions_not_laws() -> None:
    """
    Every ceiling is a flag, and raising it must actually change the verdict.

    A children's programme and a dense technical talk do not share a reading
    speed. A hard-coded number would make this tool wrong for one of them
    while looking authoritative to both.
    """
    fast = track(("00:00:00.000", "00:00:01.000", "Nineteen characters."))
    assert "cue-too-fast" in {f.rule for f in audit(fast)}
    assert "cue-too-fast" not in {f.rule for f in audit(fast, cps=40)}


def test_every_message_names_the_consequence() -> None:
    """
    A finding that only says "too long" sends the reader back to guess.

    These rules each know why they matter, and the message is where that
    knowledge has to land — it is the only part a user reads.
    """
    cues = track(
        ("00:00:00.000", "00:00:00.200", "Flash."),
        ("00:00:00.100", "00:00:12.000", "Overlapping and lingering."),
    )
    findings = audit(cues)
    assert findings
    for finding in findings:
        assert len(finding.message.split()) >= 8, finding
