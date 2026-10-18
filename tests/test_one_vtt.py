"""
One WebVTT, read and written in one place.

This suite had four writers of this format and two readers. The differences
between them were not cosmetic — voice tags on one track and deliberately not
on another, cue identifiers on a third, line structure kept by one reader and
glued together by the other — so the consolidation had to keep every one of
them rather than pick a winner.

These tests are that list of differences, each pinned. A round trip proves
the pair agree; the individual cases prove the module did not quietly drop
the behaviour one caller depends on.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _vtt import (  # noqa: E402
    Cue,
    format_timestamp,
    from_centiseconds,
    parse,
    write_srt,
    write_vtt,
)

# ── Timestamps ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("seconds", "srt", "expected"),
    [
        (0, False, "00:00:00.000"),
        (61.34, False, "00:01:01.340"),
        (61.34, True, "00:01:01,340"),
        (3661.5, False, "01:01:01.500"),
    ],
)
def test_a_timestamp_reads_the_same_in_both_formats(
    seconds: float, srt: bool, expected: str
) -> None:
    """The decimal separator is the only difference between VTT and SRT."""
    assert format_timestamp(seconds, srt=srt) == expected


def test_a_negative_time_clamps_to_zero() -> None:
    """
    A negative timestamp is never meaningful.

    Renderer behaviour on one is undefined rather than obvious, so the
    format writer decides here instead of letting each caller discover it.
    """
    assert format_timestamp(-5) == "00:00:00.000"


def test_whisper_units_convert() -> None:
    """pywhispercpp counts in 10-ms units and nothing else in the suite does."""
    assert from_centiseconds(6134) == 61.34


# ── The differences that had to survive ────────────────────────────────────


def test_a_speaker_becomes_a_voice_tag() -> None:
    """What `caption_diarize` needs once speakers are attributed."""
    out = write_vtt([Cue(0, 1, "Hello.", speaker="Ada")])
    assert "<v Ada>Hello." in out


def test_voices_can_be_refused() -> None:
    """
    What `translate_captions` needs, and why the flag exists at all.

    W3C reserves voice tags for the same-language `captions` track; a
    translated subtitle track is dialogue and must not carry them. Since the
    reader now lifts a speaker into the cue rather than discarding it, a
    writer without this flag would put the tags back.
    """
    out = write_vtt([Cue(0, 1, "Bonjour.", speaker="Ada")], voices=False)
    assert "<v" not in out
    assert "Bonjour." in out


def test_an_identifier_is_written_before_the_timings() -> None:
    """
    What the narration path needs.

    The cue identifier carries a segment index, which is what lets a page
    highlight the right block without matching on text.
    """
    out = write_vtt([Cue(0, 1, "Hello.", identifier="12")]).splitlines()
    assert out[2] == "12"
    assert "-->" in out[3]


def test_no_identifier_writes_no_line() -> None:
    """Callers that have no use for them must not get blank lines."""
    out = write_vtt([Cue(0, 1, "Hello.")]).splitlines()
    assert "-->" in out[2]


def test_an_empty_cue_is_dropped() -> None:
    """A timed blank box is on screen for its full duration and says nothing."""
    assert "-->" not in write_vtt([Cue(0, 2, "   ")])


def test_srt_numbers_its_cues_and_prefixes_the_speaker() -> None:
    """
    SubRip has no voice tags.

    A speaker becomes a plain prefix — the convention every player renders
    and none hides.
    """
    out = write_srt([Cue(0, 1, "Hello.", speaker="Ada")]).splitlines()
    assert out[0] == "1"
    assert out[2] == "Ada: Hello."


# ── Reading ────────────────────────────────────────────────────────────────


def test_line_structure_survives_a_read() -> None:
    """
    The difference between the two old readers, and it matters.

    The merger joined a cue's lines with a space, which is right for
    comparing spans of speech. `audit_captions` counts lines and measures
    their width, and can do neither on a cue whose lines have been glued
    together.
    """
    cues = parse("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\none\ntwo\n")
    assert cues[0].lines == ["one", "two"]


def test_a_voice_tag_is_lifted_out_of_the_text() -> None:
    """Otherwise a re-write double-tags the cue."""
    cues = parse("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n<v Ada>Hello.\n")
    assert cues[0].speaker == "Ada"
    assert cues[0].text == "Hello."


def test_subrip_reads_too() -> None:
    """This package writes both, so a reader holding either can check it."""
    cues = parse("1\n00:00:00,000 --> 00:00:02,000\nHello.\n")
    assert len(cues) == 1
    assert cues[0].end == 2.0


def test_cues_come_back_in_time_order() -> None:
    """A merger compares spans and needs them ordered."""
    out_of_order = (
        "WEBVTT\n\n"
        "00:00:05.000 --> 00:00:06.000\nsecond\n\n"
        "00:00:01.000 --> 00:00:02.000\nfirst\n"
    )
    assert [c.text for c in parse(out_of_order)] == ["first", "second"]


def test_a_round_trip_keeps_everything() -> None:
    """Writer and reader agree, which is the point of having one of each."""
    original = [
        Cue(0.0, 2.5, "Hello there.", speaker="Ada"),
        Cue(2.6, 5.0, "Two\nlines.", identifier="7"),
    ]
    back = parse(write_vtt(original))
    assert [(c.start, c.end, c.text, c.speaker) for c in back] == [
        (0.0, 2.5, "Hello there.", "Ada"),
        (2.6, 5.0, "Two\nlines.", None),
    ]
    assert back[1].identifier == "7"


def test_collapsing_puts_a_cue_on_one_line() -> None:
    """
    A blank line ends a cue, so a hard-wrapped payload splits one into two.

    Callers assembling text from a document rather than a transcript need
    this before writing.
    """
    assert Cue(0, 1, "a\n\nb  c").collapsed().text == "a b c"
