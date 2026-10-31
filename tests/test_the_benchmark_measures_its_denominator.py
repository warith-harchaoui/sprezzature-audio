"""
The number that divides every speed this tool prints was typed by hand.

The real-time factor is ``elapsed / audio_seconds``, so the audio duration is
half of it — and until ``--audio`` existed the only way to supply it was
``--audio-seconds``, from memory. A duration typed as 360 instead of 3600 does
not look wrong anywhere: the report says RTF 0.084 as confidently as it would
have said 0.84, and nothing in the run disagrees.

``benchmark_stt.measure_audio_seconds`` reads it off the file through
``audio_helper.get_audio_duration``, which probes with ffprobe and so answers
for the containers this benchmark actually times — mp4, mkv, m4a, mp3 — none
of which the standard library can open.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def quiet_device_report(monkeypatch):
    """Keep ``benchmark_stt.main`` from pulling a Whisper model.

    ``main`` records the hardware on every run, and ``_device.whisper_backend``
    probes it honestly: it spawns a Python that builds a ``Model('tiny')`` and
    transcribes a second of silence, because build flags can disagree with
    what the runtime manages to initialise. On a machine where pywhispercpp is
    installed but has no weights cached, that probe downloads them — tens of
    megabytes and a network dependency for a test about an argparse flag.

    Worth naming rather than hiding: it is why nothing in this suite called
    ``main`` before.
    """
    import benchmark_stt

    monkeypatch.setattr(benchmark_stt, "device_report", lambda: {"platform": "test", "threads": 1})


def _write_wav(path: Path, seconds: float, rate: int = 16000) -> Path:
    """A real WAV of a known length, so the measurement has something to read."""
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(
            b"".join(
                struct.pack("<h", int(12000 * math.sin(2 * math.pi * 220 * t / rate)))
                for t in range(int(rate * seconds))
            )
        )
    return path


def test_the_duration_is_read_off_the_file(tmp_path) -> None:
    """The measured duration matches the file that was written."""
    pytest.importorskip("audio_helper")
    import benchmark_stt

    wav = _write_wav(tmp_path / "two-seconds.wav", 2.0)
    assert benchmark_stt.measure_audio_seconds(wav) == pytest.approx(2.0, abs=0.01)


def test_a_measured_duration_wins_over_a_stated_one(tmp_path, capsys, quiet_device_report) -> None:
    """``--audio`` beats ``--audio-seconds``, and the report says which it used.

    The stated value here is wrong by a factor of ten, which is exactly the
    typo the flag exists to stop mattering: a report that used it would print
    a real-time factor ten times too small and look entirely plausible.
    """
    pytest.importorskip("audio_helper")
    import benchmark_stt

    wav = _write_wav(tmp_path / "two-seconds.wav", 2.0)
    code = benchmark_stt.main(
        [
            "--audio",
            str(wav),
            "--audio-seconds",
            "20",
            "--time-command",
            f"{sys.executable} -c pass",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "for 2 s of audio (measured)" in out


def test_a_stated_duration_still_works_and_says_so(capsys, quiet_device_report) -> None:
    """``--audio-seconds`` is kept: not every machine has audio-helper."""
    import benchmark_stt

    code = benchmark_stt.main(
        ["--audio-seconds", "20", "--time-command", f"{sys.executable} -c pass"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "for 20 s of audio (stated)" in out


def test_timing_without_any_duration_is_refused(quiet_device_report) -> None:
    """A real-time factor needs a denominator, from one flag or the other."""
    import benchmark_stt

    with pytest.raises(SystemExit):
        benchmark_stt.main(["--time-command", f"{sys.executable} -c pass"])
