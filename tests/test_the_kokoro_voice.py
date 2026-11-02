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

import re
from pathlib import Path

import pick_voice
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _section(name: str) -> str:
    """The raw body of one ``[project.<name>]`` table."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    found = re.search(
        rf"^\[project\.{re.escape(name)}\]\s*$(.*?)(?=^\[|\Z)",
        text,
        re.M | re.S,
    )
    return found.group(1) if found else ""


def _extras() -> dict[str, list[str]]:
    """``extra -> requirement strings``, from ``[project.optional-dependencies]``.

    The closing bracket is found by counting, not by a lazy regex. A
    requirement may carry its own extras — ``speaker-helper[kokoro,detect]`` —
    and the lazy version stopped at *that* bracket, returning a fragment with
    no closing quote in it. Every requirement then read as the empty list, and
    two assertions failed saying ``'speaker-helper' in ''``, which points at
    the packaging rather than at the reader.
    """
    body = _section("optional-dependencies")
    out: dict[str, list[str]] = {}
    for match in re.finditer(r"^([A-Za-z0-9._-]+)\s*=\s*\[", body, re.M):
        depth, index = 1, match.end()
        while index < len(body) and depth:
            depth += {"[": 1, "]": -1}.get(body[index], 0)
            index += 1
        out[match.group(1)] = re.findall(r'"([^"]+)"', body[match.end() : index - 1])
    return out


def _base() -> list[str]:
    """The base install, from ``dependencies = [...]`` in ``[project]``.

    Comments are stripped **before** the brackets are counted. The base block
    carries prose that names requirement-extras --
    ``speaker-helper[kokoro,detect]`` -- and a counter that reads those would
    close the array in the middle of a sentence and return a fragment. That is
    the same mistake :func:`_extras` documents having made with a lazy regex,
    arriving from the other direction.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    stripped = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    start = re.search(r"^dependencies\s*=\s*\[", stripped, re.M)
    if not start:
        return []
    depth, index = 1, start.end()
    while index < len(stripped) and depth:
        depth += {"[": 1, "]": -1}.get(stripped[index], 0)
        index += 1
    return re.findall(r'"([^"]+)"', stripped[start.end() : index - 1])


def _scripts() -> dict[str, str]:
    """``command -> target``, from ``[project.scripts]``."""
    return dict(re.findall(r'^([A-Za-z0-9._-]+)\s*=\s*"([^"]+)"', _section("scripts"), re.M))


#: Read with regexes rather than ``tomllib``, which is in the standard library
#: only from 3.11 while this package supports 3.10 — there the import alone
#: failed collection of this whole file, and CI said so on three runs in a row
#: before anybody looked. Two sibling packages already read pyproject this way
#: and say why in their own comments; this file had not followed.
PYPROJECT = {
    "project": {
        "dependencies": _base(),
        "optional-dependencies": _extras(),
        "scripts": _scripts(),
    }
}


# ── The packaging says what the code needs ─────────────────────────────────


def test_the_engine_ships_with_the_package_and_has_its_own_command() -> None:
    """
    An engine reachable only from a clone is not shipped. Both halves are
    checked because they fail apart: a dependency nobody declares installs
    nothing, and a declared dependency with no console script installs a voice
    with no way to run it.

    Until 2026-11-01 the first half was "the engine has its own extra". The
    engines moved into the base install that day -- narration is what this
    package is *for*, and `pip install sprezzature-audio` used to give four
    packages and no voice -- so the half that still means something is that
    the **base** names the release carrying the API this adapter calls. An
    older one installs a package that does not have it.
    """
    base = " ".join(PYPROJECT["project"]["dependencies"])
    assert "speaker-helper" in base, (
        "the base install names no speaker-helper, so `pip install "
        "sprezzature-audio` ships a package with no voice -- which is the "
        "state this was folded in to end"
    )
    # A floor, compared as a version, not the literal string it was. The
    # literal turned this test red on the 0.8.0 -> 0.11.0 bump, which is the
    # wrong failure: the question is "is the floor high enough", and a test
    # that answers "is the floor exactly what it was when I was written"
    # cannot tell a correct bump from a regression.
    #
    # 0.11.0 is the release that brought the pronunciation lexicon, which
    # `scripts/_speaker.py` passes through as `settings.lexicon`. Against 0.10
    # that key is accepted and ignored, so the failure would be a narration
    # that quietly mispronounces every acronym -- no traceback.
    floor = re.search(r"speaker-helper\[[^\]]*\]>=([0-9][0-9.]*)", base)
    assert floor, f"the base names no speaker-helper floor: {base}"
    need = (0, 11, 0)
    got = tuple(int(n) for n in floor.group(1).split("."))
    assert got >= need, (
        f"the base pins speaker-helper>={floor.group(1)}, but this package "
        f"passes settings.lexicon, which landed in "
        f"{'.'.join(str(n) for n in need)}. Older releases accept the key "
        f"and ignore it, so the symptom is a mispronunciation, not an error."
    )
    # Every engine the router can answer, or the default path names one that
    # is not installed. Measured: `speaker_helper.router` holds no
    # `check_install`, no `find_spec` and no `importlib`, so it ranks on
    # quality and RTF alone and cannot route around an absence.
    for engine in ("kokoro", "chatterbox"):
        assert engine in base, (
            f"the router answers {engine} -- offline for chatterbox, "
            f"online_realtime for kokoro, in both languages -- and the base "
            f"does not name it, so the default path asks for a voice that is "
            f"not there"
        )

    scripts = PYPROJECT["project"]["scripts"]
    assert scripts["sprezzature-audio-narrate-kokoro"].endswith("narrate_kokoro:main")


def test_torch_in_the_base_is_a_floor_and_not_a_pin() -> None:
    """
    The one thing that made the old light/heavy split worth having.

    This test used to assert ``"torch" not in extras["narrate"]``, and the
    reason was an incident: installing ``chatterbox-tts`` into a working
    environment downgraded torch 2.8 to 2.6 and broke an unrelated package
    that depended on it. Reading an article aloud must not be able to do that.

    Putting chatterbox in the base on 2026-11-01 looks like it reopens exactly
    that. Measured, it does not, and the measurement is the test: the base
    reaches torch through ``speaker-helper[chatterbox]``, which declares
    ``torch>=2.0.0`` -- **a floor** -- and does not depend on
    ``chatterbox-tts`` at all. ``chatterbox-tts 0.1.7``, the package from the
    incident, declares ``torch==2.6.0``: an exact pin, which is what made a
    downgrade certain rather than possible. Two different packages with
    similar names and opposite dependency shapes.

    So what is asserted is the property that keeps the base safe rather than
    the old prohibition that no longer applies: nothing this manifest names
    may pin or cap torch. A resolved base gives torch 2.15.0 and numpy 2.5.4
    across 195 packages.
    """
    base = PYPROJECT["project"]["dependencies"]
    assert any("chatterbox" in req for req in base), (
        "no chatterbox in the base, so this test is checking a risk that is "
        "not being taken -- which is fine, and means it should be deleted "
        "rather than left looking like coverage"
    )
    offenders = [
        req
        for req in base
        if "torch" in req and ("==" in req or "<" in req or "~=" in req)
    ]
    assert offenders == [], (
        f"{offenders} pins or caps torch from this package's own manifest. "
        f"That is the shape that downgraded torch 2.8 to 2.6 once already, "
        f"and from the base it would do it to every install"
    )
    assert "chatterbox-tts" not in " ".join(base), (
        "chatterbox-tts declares torch==2.6.0, an exact pin. The engine is "
        "reached through speaker-helper[chatterbox], which declares a floor"
    )


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
    track = (
        np.full_like(t, hertz) if np.isscalar(hertz) else np.linspace(hertz[0], hertz[1], t.size)
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
