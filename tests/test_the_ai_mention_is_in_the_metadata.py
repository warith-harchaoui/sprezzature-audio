"""Every file made with a model says so in its metadata, and shows nothing."""

from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import _provenance as prov  # noqa: E402
import _vtt  # noqa: E402

FR = "généré avec l'aide de l'IA de sprezzature par deraison.ai"
EN = "generated with the help of sprezzature AI by deraison.ai"


def test_the_two_sentences_are_exact():
    assert prov.MENTION_FR == FR
    assert prov.MENTION_EN == EN


def test_the_vtt_note_is_a_note_and_never_a_cue():
    vtt = _vtt.write_vtt([_vtt.Cue(0.0, 1.0, "Bonjour."), _vtt.Cue(1.0, 2.0, "Salut.")])
    noted = prov.vtt_note(vtt)
    assert noted.startswith("WEBVTT\n\nNOTE\n")
    assert FR in noted and EN in noted
    # the NOTE sits before the first timing line
    assert noted.index("NOTE") < noted.index("-->")
    cues = _vtt.parse(noted)
    assert [c.text for c in cues] == ["Bonjour.", "Salut."]
    for cue in cues:
        assert "sprezzature" not in cue.text and "deraison" not in cue.text
        assert cue.identifier is None


def test_the_vtt_note_is_idempotent_and_leaves_other_text_alone():
    noted = prov.vtt_note("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHi\n")
    assert prov.vtt_note(noted) == noted
    assert prov.vtt_note("1\n00:00:00,000 --> 00:00:01,000\nHi\n") == (
        "1\n00:00:00,000 --> 00:00:01,000\nHi\n"
    )


def _wav(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 800)


def test_a_wav_carries_the_comment_and_still_plays(tmp_path):
    path = tmp_path / "n.wav"
    _wav(path)
    assert prov.tag_audio(path)
    raw = path.read_bytes()
    assert b"ICMT" in raw and FR.encode() in raw and EN.encode() in raw
    with wave.open(str(path)) as handle:
        assert handle.getnframes() == 800


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
@pytest.mark.parametrize("suffix", [".mp3", ".flac", ".ogg"])
def test_a_compressed_file_carries_both_sentences(tmp_path, suffix):
    src = tmp_path / "n.wav"
    _wav(src)
    path = tmp_path / f"n{suffix}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), str(path)], check=True)
    assert prov.tag_audio(path)
    # Read it back the way a player would: ID3v2.3 stores "é" as UTF-16, so
    # the raw bytes are not the place to look.
    shown = subprocess.run(
        ["ffprobe", "-loglevel", "error", "-show_entries", "format_tags:stream_tags", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert FR in shown and EN in shown
    assert prov.DIGITAL_SOURCE_TYPE in shown
