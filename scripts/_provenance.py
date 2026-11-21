"""
_provenance: say, in the file itself, that a model helped make it.

Decided 2026-11-21: every file this suite produces with the help of a model
carries one exact sentence in its metadata, in French and in English, so that
whoever receives the file can tell without being told. Nothing visible in the
content changes; the sentence sits where the format keeps such things.

What counts. A transcript is a model's reading of a recording, a translation
is a model's rewriting, a narration is a model's voice, and a speaker-labelled
caption file carries a diarization model's verdicts. A deterministic
conversion (``captions-convert``) or a metric (WER, DER) is none of those and
gets nothing.

Where it goes, by format.

* **WebVTT**: a ``NOTE`` block straight after the header, which the standard
  provides for exactly this and which no renderer shows.
* **SubRip**: nowhere. SubRip has no header and no comment syntax; any line
  added would be read as a cue or displayed. The file is left untouched, and
  the sentence travels with the ``.vtt`` the same run writes.
* **WAV**: a ``LIST``/``INFO`` chunk with ``ICMT`` (comment), appended after
  the audio, in pure Python.
* **MP3, OGG, FLAC, Opus, M4A**: the container's comment tag plus two named
  tags, through ``ffmpeg -c copy`` (no re-encoding). Without ffmpeg the file
  is left as it is and the caller is told.

The machine-readable companion is the IPTC ``DigitalSourceType`` term
``trainedAlgorithmicMedia``, written as ``digital_source_type``.

Stdlib only.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

#: The two sentences, exactly. Lower case on purpose: ``sprezzature`` and
#: ``deraison.ai`` are never capitalised.
MENTION_FR = "généré avec l'aide de l'IA de sprezzature par deraison.ai"
MENTION_EN = "generated with the help of sprezzature AI by deraison.ai"

#: Both, for the formats that hold a single comment.
MENTION_BOTH = f"{MENTION_FR} / {MENTION_EN}"

#: IPTC ``DigitalSourceType`` for a recording a model synthesised entirely.
DIGITAL_SOURCE_TYPE = "trainedAlgorithmicMedia"


def vtt_note(vtt: str) -> str:
    """Put the mention in a ``NOTE`` block right after the WebVTT header.

    Idempotent: a document that already says it is returned unchanged.
    Anything that is not WebVTT (no ``WEBVTT`` first line) is returned as is.
    """
    if MENTION_FR in vtt:
        return vtt
    lines = vtt.split("\n")
    if not lines or not lines[0].startswith("WEBVTT"):
        return vtt
    end = 1
    while end < len(lines) and lines[end].strip():
        end += 1  # header lines (``Kind:``, ``Language:``) run to the blank line
    block = ["", "NOTE", MENTION_FR, MENTION_EN]
    if end >= len(lines):  # a header and nothing else
        return "\n".join(lines + block + [""])
    return "\n".join(lines[:end] + block + lines[end:])


def _wav_comment(path: Path) -> bool:
    data = path.read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return False
    if b"ICMT" in data and MENTION_FR.encode() in data:
        return True
    text = MENTION_BOTH.encode("utf-8") + b"\x00"
    if len(text) % 2:
        text += b"\x00"
    icmt = b"ICMT" + struct.pack("<I", len(text)) + text
    info = b"INFO" + icmt
    chunk = b"LIST" + struct.pack("<I", len(info)) + info
    if len(data) % 2:
        data += b"\x00"
    new = bytearray(data + chunk)
    struct.pack_into("<I", new, 4, len(new) - 8)
    path.write_bytes(bytes(new))
    return True


def _ffmpeg_comment(path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"tagged{path.suffix}"
        cmd = [
            ffmpeg, "-y", "-loglevel", "error", "-i", str(path),
            "-map", "0", "-c", "copy", "-map_metadata", "0",
            "-metadata", f"comment={MENTION_BOTH}",
            "-metadata", f"ai_generated_fr={MENTION_FR}",
            "-metadata", f"ai_generated_en={MENTION_EN}",
            "-metadata", f"digital_source_type={DIGITAL_SOURCE_TYPE}",
        ]
        if path.suffix.lower() == ".mp3":
            cmd += ["-id3v2_version", "3"]
        cmd.append(str(out))
        done = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if done.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            return False
        shutil.copyfile(out, path)
    return True


def tag_audio(path: Path) -> bool:
    """Write the mention into an audio file's own metadata.

    Returns ``True`` when it is there afterwards, ``False`` when the format
    or the machine could not take it (no ffmpeg, an unknown container). The
    audio itself is never re-encoded and is never lost: on any failure the
    file stays exactly as it was.
    """
    path = Path(path)
    if not path.is_file():
        return False
    if path.suffix.lower() == ".wav":
        return _wav_comment(path)
    return _ffmpeg_comment(path)
