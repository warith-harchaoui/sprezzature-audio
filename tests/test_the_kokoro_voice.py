"""
What this package must still get right about narration, now the voice moved.

The voice itself — the tables, the language pairing, the refusals, the
timeline — lives in ``speaker-helper`` and is tested there, against a backend
that needs no model. Keeping a second copy of those checks here would be two
owners for one fact, and the pair would drift.

What stays is what this package owns: that the extras name something pip can
resolve, that each engine has a command, that the light extra really is light
— installing chatterbox-tts into a working environment once downgraded torch
2.8 to 2.6 and broke an unrelated package, and asking for an article to be
read aloud must not be able to do that — and the measurement that says how
flat a voice is before a long document is committed to it.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from pathlib import Path

import pick_voice
import pytest
import tomllib

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


# ── The packaging says what the code needs ─────────────────────────────────


def test_the_engine_has_its_own_extra_and_its_own_command() -> None:
    """
    An engine reachable only from a clone is not shipped. Both halves are
    checked because they fail apart: a missing extra installs nothing, a
    missing console script installs it and leaves no way to run it.
    """
    extras = PYPROJECT["project"]["optional-dependencies"]
    assert "narrate-kokoro" in extras
    packages = " ".join(extras["narrate"])
    # The engine arrives through speaker-helper now, and the extra has to name
    # the release that carries `Speaker.narrate` — an older one installs a
    # package whose API this adapter calls and which does not have it.
    assert "speaker-helper" in packages
    assert ">=0.8.0" in packages
    # No torch. That is the whole reason this engine exists alongside the
    # other two, and an innocent-looking edit to the extra would undo it.
    assert "torch" not in packages

    scripts = PYPROJECT["project"]["scripts"]
    assert scripts["sprezzature-audio-narrate-kokoro"].endswith("narrate_kokoro:main")


def test_the_default_narration_extra_is_the_light_one() -> None:
    """
    ``[narrate]`` is what a site generator asks for when it wants a page read
    aloud. It used to mean torch, and installing chatterbox-tts into a
    working environment once downgraded torch 2.8 to 2.6 and broke an
    unrelated package that depended on it. Reading an article aloud must not
    be able to do that.
    """
    extras = PYPROJECT["project"]["optional-dependencies"]
    light = " ".join(extras["narrate"])
    assert "torch" not in light
    # And the cloning extras are the ones that do pull it, so the split is
    # real rather than a name.
    assert "speaker-helper[openvoice]" in " ".join(extras["narrate-openvoice"])


def test_the_install_hint_names_an_extra_that_exists() -> None:
    """
    The failure this repository has shipped before, in another file: an
    install line that reads perfectly and resolves to nothing.
    """
    source = (ROOT / "scripts" / "_speaker.py").read_text(encoding="utf-8")
    extras = set(PYPROJECT["project"]["optional-dependencies"])
    import re

    for named in set(re.findall(r"sprezzature-audio\[([a-z,\-]+)\]", source)):
        for extra in named.split(","):
            assert extra in extras, f"the adapter offers [{extra}], pyproject has no such extra"


# ── Ranking a voice by how far it moves ────────────────────────────────────


def _tone(path: Path, hertz, seconds: float = 2.0, rate: int = 24_000) -> Path:
    """A 16-bit mono WAV at a given pitch — constant, or swept.

    Synthetic on purpose. The measurement is being tested, not the model,
    and a test that has to load 340 MB of weights to check an arithmetic
    property is a test nobody runs.
    """
    import wave

    import numpy as np

    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    track = np.full_like(t, hertz) if np.isscalar(hertz) else np.linspace(
        hertz[0], hertz[1], t.size
    )
    # Integrate the frequency track, or a sweep comes out at the wrong pitch.
    phase = 2 * np.pi * np.cumsum(track) / rate
    wave_data = (0.4 * np.sin(phase) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(wave_data.tobytes())
    return path


def test_a_flat_tone_measures_as_flat(tmp_path: Path) -> None:
    """The floor of the scale. A constant pitch moves by nothing."""
    pytest.importorskip("numpy")
    span = pick_voice.pitch_span_semitones(_tone(tmp_path / "flat.wav", 150.0))
    assert span is not None
    assert span < 1.0, f"a constant 150 Hz tone measured {span:.1f} semitones"


def test_a_sweep_measures_as_the_interval_it_sweeps(tmp_path: Path) -> None:
    """
    120 Hz to 240 Hz is an octave, which is twelve semitones. Measured off
    the 5th and 95th percentiles, so the answer lands slightly under.
    """
    pytest.importorskip("numpy")
    span = pick_voice.pitch_span_semitones(_tone(tmp_path / "sweep.wav", (120.0, 240.0)))
    assert span is not None
    assert 9.0 < span < 12.5, f"an octave sweep measured {span:.1f} semitones"


def test_the_measure_orders_a_sweep_above_a_flat_tone(tmp_path: Path) -> None:
    """
    The property the shortlist rests on. Absolute accuracy does not matter
    much — this estimator is autocorrelation, not a research pitch tracker —
    but the ordering has to hold, or the table is noise.
    """
    pytest.importorskip("numpy")
    flat = pick_voice.pitch_span_semitones(_tone(tmp_path / "f.wav", 150.0))
    sweep = pick_voice.pitch_span_semitones(_tone(tmp_path / "s.wav", (120.0, 240.0)))
    assert flat is not None and sweep is not None
    assert sweep > flat + 5.0


def test_silence_is_refused_rather_than_scored(tmp_path: Path) -> None:
    """
    A failed render is an empty or near-empty file. Returning a number for
    it would put a voice in the table that was never spoken.
    """
    import wave

    path = tmp_path / "silence.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24_000)
        handle.writeframes(b"\x00\x00" * 24_000)
    assert pick_voice.pitch_span_semitones(path) is None


# ── A sentence with nothing to say ─────────────────────────────────────────
