"""
What the Kokoro narrator must get right before it ever loads a model.

Everything here runs without the 340 MB of weights, without a network, and
without espeak-ng. That is deliberate: the expensive half is the model, and
none of the mistakes this file is written for live there. They live in the
tables — a voice name that does not exist, a language that maps to a voice
that does not speak it, an install hint naming an extra nobody declared.

The defect that shaped the file: an engine that accepts a hint it cannot act
on. Chatterbox takes `emotion` and `intensity`; Kokoro has no dial for
either. Silently dropping them produces a narration that is flat for a
reason nobody can find, so the engine reports what it ignored — and these
tests check that it reports neither too much nor too little, because a
report that cries wolf on every neutral sentence stops being read.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import narrate_kokoro
import pick_voice

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


# ── The tables agree with each other ───────────────────────────────────────


def test_every_default_voice_is_a_voice_this_engine_has() -> None:
    """
    A default voice that does not exist fails at the first narration, in a
    language nobody on the team may speak.
    """
    catalogue = set(pick_voice.BUILTIN_VOICES["kokoro"])
    for language, voice in narrate_kokoro.DEFAULT_VOICE_BY_LANG.items():
        assert voice in catalogue, f"{language} defaults to {voice!r}, which is not a voice"
    assert narrate_kokoro.FALLBACK_VOICE in catalogue


@pytest.mark.parametrize(
    ("language", "voice"), sorted(narrate_kokoro.DEFAULT_VOICE_BY_LANG.items())
)
def test_a_languages_default_voice_speaks_that_language(language: str, voice: str) -> None:
    """
    The pairing that matters, and the one a careless edit breaks silently.

    Kokoro encodes the language in the voice name's first letter, and the
    language is what the phonemiser works from. Pair ``fr`` with an ``a``
    voice and the result is not French in an American accent — it is an
    American reading French spelling aloud. It sounds like a bad voice
    rather than like a wrong setting, which is why it would be looked for in
    the wrong place.
    """
    implied = narrate_kokoro.language_for(voice)
    assert implied.split("-")[0].replace("cmn", "zh") == language


def test_every_voice_in_the_catalogue_names_a_language_we_know() -> None:
    """A prefix with no entry silently becomes American English."""
    for voice in pick_voice.BUILTIN_VOICES["kokoro"]:
        assert voice[:1] in narrate_kokoro.VOICE_PREFIX_LANG, voice


def test_the_catalogue_covers_every_language_the_model_ships() -> None:
    """
    Guards the direction the parametrised test above cannot: it only checks
    the languages already in the table, so a language dropped from it would
    take its own test with it and the suite would stay green.
    """
    prefixes = {voice[:1] for voice in pick_voice.BUILTIN_VOICES["kokoro"]}
    assert prefixes == set(narrate_kokoro.VOICE_PREFIX_LANG)
    spoken = {
        narrate_kokoro.language_for(v).split("-")[0].replace("cmn", "zh")
        for v in pick_voice.BUILTIN_VOICES["kokoro"]
    }
    assert spoken == set(narrate_kokoro.DEFAULT_VOICE_BY_LANG)


# ── Detection picks the voice ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Ralph loops are a way of making a model look at its own output, "
            "and then look at it again until the answer stops changing.",
            "en",
        ),
        (
            "Les boucles consistent à faire relire au modèle sa propre sortie, "
            "puis à recommencer jusqu'à ce que la réponse cesse de changer.",
            "fr",
        ),
    ],
)
def test_the_voice_follows_the_language_of_the_text(text: str, expected: str) -> None:
    """Nobody names a voice; the text does."""
    segments = [{"text": sentence} for sentence in text.split(", ")]
    voice, detected, fell_back = narrate_kokoro.voice_for_text(segments)
    assert detected == expected
    assert not fell_back
    assert voice == narrate_kokoro.DEFAULT_VOICE_BY_LANG[expected]


def test_a_language_with_no_voice_says_so_rather_than_pretending() -> None:
    """
    Kokoro speaks nine languages, and a site is not obliged to be in one of
    them. The honest outcome is a voice that does not speak the text *and a
    flag saying so* — whoever generated it may not speak the language either,
    and the audio alone will not tell them.
    """
    segments = [
        {"text": "모델이 자기 출력을 다시 읽게 만드는 방식입니다."},
        {"text": "그리고 답이 더 이상 바뀌지 않을 때까지 반복합니다."},
    ]
    voice, detected, fell_back = narrate_kokoro.voice_for_text(segments)
    assert detected not in narrate_kokoro.DEFAULT_VOICE_BY_LANG
    assert fell_back is True
    assert voice == narrate_kokoro.FALLBACK_VOICE


# ── What it refuses, and what it admits ────────────────────────────────────


def test_cloning_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    """
    ``--voice-sample`` is meaningful to the other two engines and meaningless
    here. Accepting it and reading in some unrelated built-in voice would be
    the worst answer: the caller asked to sound like themselves and got a
    stranger, with no error to explain it.
    """
    with pytest.raises(RuntimeError) as caught:
        narrate_kokoro.synthesise(
            [{"text": "hello"}],
            voice="af_heart",
            voice_sample=tmp_path / "me.wav",
            out_dir=tmp_path,
        )
    message = str(caught.value)
    assert "chatterbox" in message and "openvoice" in message


def test_a_neutral_segment_reports_nothing_ignored() -> None:
    """
    The hints carry defaults — ``emotion: neutral``, ``intensity: 0.5`` —
    which mean "nothing was asked for". Reporting those as ignored would put
    a complaint on every ordinary narration, and a report that fires every
    time is a report nobody reads.
    """
    neutral = {"text": "x", "emotion": "neutral", "intensity": 0.5, "pace": "normal"}
    assert all(
        neutral.get(hint) == value
        for hint, value in narrate_kokoro.NEUTRAL_HINTS.items()
    )
    assert "intensity" not in narrate_kokoro.NEUTRAL_HINTS


def test_pace_is_honoured_and_stays_within_hearing() -> None:
    """
    ``pace`` is the one hint this engine can act on. The range is narrow on
    purpose: past roughly ±20 % the vocoder sounds wound-up or drugged, and a
    narration that calls attention to its own speed has stopped narrating.
    """
    speeds = narrate_kokoro.PACE_SPEED
    assert speeds["slow"] < speeds["normal"] < speeds["fast"]
    assert all(0.8 <= s <= 1.2 for s in speeds.values())


# ── The packaging says what the code needs ─────────────────────────────────


def test_the_engine_has_its_own_extra_and_its_own_command() -> None:
    """
    An engine reachable only from a clone is not shipped. Both halves are
    checked because they fail apart: a missing extra installs nothing, a
    missing console script installs it and leaves no way to run it.
    """
    extras = PYPROJECT["project"]["optional-dependencies"]
    assert "narrate-kokoro" in extras
    packages = " ".join(extras["narrate-kokoro"])
    assert "kokoro-onnx" in packages
    assert "espeakng-loader" in packages
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
    assert extras["narrate"] == ["sprezzature-audio[narrate-kokoro]"]


def test_the_install_hint_names_an_extra_that_exists() -> None:
    """
    The failure this repository has shipped before, in another file: an
    install line that reads perfectly and resolves to nothing.
    """
    source = (ROOT / "scripts" / "narrate_kokoro.py").read_text(encoding="utf-8")
    assert "requirements-narrate-kokoro.txt" in source
    assert (ROOT / "scripts" / "requirements-narrate-kokoro.txt").is_file()


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
