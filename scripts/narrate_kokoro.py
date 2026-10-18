#!/usr/bin/env python3
"""
narrate_kokoro
==============

Kokoro engine wrapper for ``narrate_post.py``. Same contract as its two
siblings: ``--check`` probes the install without paying for it, and synthesis
mode reads a segments JSON, writes one WAV plus its WebVTT cues, and prints a
single JSON object on stdout.

Why a third engine
------------------
The two that came first are voice-*cloning* engines, and that is a different
job from reading a page aloud. OpenVoice v2 and Chatterbox both want a
reference clip, both pull a multi-gigabyte torch stack, and Chatterbox's
checkpoint load fails outright without ``resemble-perth`` — a watermarker
nothing declares. For "this article should have a voice", that is a lot of
machinery between the text and the sound.

Kokoro is 82 M parameters, Apache-2.0 in both halves — code *and* weights,
which is the bar this suite set when it ruled out F5-TTS and XTTS-v2 for
non-commercial weights — and it runs through ONNX Runtime, so the whole
dependency is about 340 MB with no torch at all. On a laptop CPU it
synthesises at roughly a fifth of real time: an hour of narration costs about
twelve minutes. It ships 54 voices across nine languages, so there is nothing
to clone and nothing to record.

What it cannot do, stated plainly
---------------------------------
Kokoro has no emotion dial. The segments carry ``emotion`` and ``intensity``
because Chatterbox can act on them, and this engine cannot: there is no
parameter to map them onto. It applies ``pace`` — that one is real, it is the
speed control — and reports the rest as ignored in its result, under
``ignored_hints``. Silently accepting a hint and dropping it is how a
narration ends up flat with nobody able to say why.

It cannot clone a voice either. ``--voice-sample`` is refused rather than
accepted-and-ignored, with the two engines that do support it named.

A note on licences
------------------
Kokoro's code and weights are Apache-2.0, which is what lets this sit in a
BSD-3 repository. **espeak-ng is GPL**, and it is reached as a separate
binary through ``ctypes`` — the way a program calls ``ffmpeg`` — not linked
into anything here.

Stated precisely, because the tidy version of this sentence is wrong: the
``[narrate-kokoro]`` extra does declare ``espeakng-loader``, a wheel that
carries a built espeak-ng, so a container image built from that extra
contains a GPL binary. That is an ordinary dependency and not by itself a
problem, but it is a thing somebody shipping an image should know they are
shipping, rather than discover from a licence scan. The preferred path is
the machine's own espeak-ng; the wheel is the fallback, and on macOS it does
not work anyway (see :func:`espeak_config`).

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import wave
from pathlib import Path
from typing import Any

# Sibling module, loaded the way every script in this skill loads its
# neighbours: the directory is on `sys.path` when a script runs from here.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import _lang  # noqa: E402
import _vtt  # noqa: E402

# ── Module-level configuration ──────────────────────────────────────────────

#: Kokoro's native sample rate (24 kHz mono), the same as Chatterbox's.
SAMPLE_RATE_HZ: int = 24_000

#: Where `install_narrate.py --engine kokoro` puts the two model files.
CACHE_ROOT: Path = Path.home() / ".cache" / "sprezzature-skill" / "kokoro"

#: The ONNX graph and the voice bank, by the names their release uses.
MODEL_FILENAME: str = "kokoro-v1.0.onnx"
VOICES_FILENAME: str = "voices-v1.0.bin"

#: A voice *is* a language here — the name's first letter says which, and a
#: `lang` that disagrees with the voice produces an accent nobody asked for.
VOICE_PREFIX_LANG: dict[str, str] = {
    "a": "en-us",   # American English
    "b": "en-gb",   # British English
    "e": "es",      # Spanish
    "f": "fr-fr",   # French
    "h": "hi",      # Hindi
    "i": "it",      # Italian
    "j": "ja",      # Japanese
    "p": "pt-br",   # Brazilian Portuguese
    "z": "cmn",     # Mandarin Chinese
}

#: What `langdetect` answers → the voice that reads it. The default voice is
#: not a constant, because the language is not a constant: the house rule
#: (`_lang`) is that nothing here hard-codes one, and a narrator is the last
#: place to start — an American voice reading French does not produce an
#: accent, it produces nonsense, because the phonemiser is told the wrong
#: language and spells the words out as if they were English.
#:
#: Within a language the pick is the model card's highest-graded voice.
DEFAULT_VOICE_BY_LANG: dict[str, str] = {
    "en": "af_heart",     # graded A — the only one the card grades that high
    "fr": "ff_siwis",     # the sole French voice
    "es": "ef_dora",
    "it": "if_sara",
    "pt": "pf_dora",
    "hi": "hf_alpha",
    "ja": "jf_alpha",
    "zh": "zf_xiaoxiao",
}

#: Fallback when the text is in a language Kokoro has no voice for. Reported
#: in the result as `language_fallback` rather than passed off as a choice.
FALLBACK_VOICE: str = "af_heart"

#: `pace` → Kokoro's speed multiplier. Deliberately narrow: past about ±20 %
#: the vocoder starts sounding wound-up or drugged rather than paced, and a
#: narration that calls attention to its own speed has stopped narrating.
PACE_SPEED: dict[str, float] = {
    "slow":   0.85,
    "normal": 1.00,
    "fast":   1.15,
}

#: Whether a segment has anything a voice could say. Punctuation alone does
#: not: a French page closing a quotation on its own line gives a sentence
#: that is one `»`, which is a mark on the page and silence in the ear.
_SPEAKABLE = re.compile(r"[^\W_]", re.UNICODE)

#: How long such a sentence lasts. Short, because the pause around it is
#: already carried by its neighbours -- but not zero, because the cue has
#: to have somewhere to sit.
PUNCTUATION_PAUSE_MS: int = 120

#: The neutral value of each hint this engine has no dial for — what the
#: segment carries when nothing was asked for. A hint is reported as ignored
#: only when it differs from this, because "you asked for something I cannot
#: do" and "you asked for nothing" must not read the same.
#:
#: `intensity` is deliberately absent: it scales an emotion rather than
#: meaning anything alone, so a segment with intensity 0.5 and no emotion has
#: requested nothing. Listing it cost one line of noise on every neutral
#: narration, which is how a report stops being read.
NEUTRAL_HINTS: dict[str, object] = {"emotion": "neutral"}


# ── espeak-ng resolution ───────────────────────────────────────────────────

def espeak_config() -> Any:
    """Where this machine's working espeak-ng lives.

    Kokoro phonemises through espeak-ng, and the copy bundled in the
    ``espeakng-loader`` wheel does not find its own data on macOS. It was
    built on a CI runner and resolves to that machine's home directory::

        Error processing file '/Users/runner/work/espeakng-loader/.../phontab'

    Handing it the data directory explicitly does not rescue it: espeak looks
    for ``<path>/espeak-ng-data`` and falls back to ``<path>`` itself, and
    with the wheel's layout neither candidate holds a readable ``phontab``.
    The failure is also not catchable — espeak reports it from C and calls
    ``exit(1)``, so there is no traceback, only a path belonging to somebody
    else's computer and a dead process.

    A system espeak-ng is built against its own prefix and initialises first
    try, so that is what this prefers, with the wheel's copy as the fallback
    for machines that have no system install.
    """
    from kokoro_onnx.config import EspeakConfig

    for prefix in (Path("/opt/homebrew"), Path("/usr/local"), Path("/usr")):
        library = prefix / "lib" / "libespeak-ng.dylib"
        if not library.is_file():
            library = prefix / "lib" / "libespeak-ng.so"
        data = prefix / "share" / "espeak-ng-data"
        if library.is_file() and (data / "phontab").is_file():
            return EspeakConfig(lib_path=str(library), data_path=str(data))

    import espeakng_loader

    return EspeakConfig(
        lib_path=espeakng_loader.get_library_path(),
        data_path=espeakng_loader.get_data_path(),
    )


# ── Capability probe ───────────────────────────────────────────────────────

def check_install() -> int:
    """
    Exit 0 when this engine could actually synthesise, 1 otherwise.

    Both halves are checked, because they fail at different times and only
    one of them is a ``pip install``. The package being importable says
    nothing about whether the 340 MB of weights were ever fetched, and
    discovering that at the first sentence of a long narration is the wrong
    moment.
    """
    try:
        importlib.import_module("kokoro_onnx")
    except ImportError:
        return 1
    return 0 if model_paths() else 1


def model_paths() -> tuple[Path, Path] | None:
    """The ONNX graph and voice bank, or ``None`` when they are not fetched."""
    model = CACHE_ROOT / MODEL_FILENAME
    voices = CACHE_ROOT / VOICES_FILENAME
    return (model, voices) if model.is_file() and voices.is_file() else None


def language_for(voice: str) -> str:
    """The language a voice name implies — see :data:`VOICE_PREFIX_LANG`."""
    return VOICE_PREFIX_LANG.get(voice[:1], "en-us")


def voice_for_text(segments: list[dict[str, Any]]) -> tuple[str, str, bool]:
    """Pick the voice from the language the segments are actually written in.

    Returns ``(voice, detected_iso_code, fell_back)``.

    The detection is `_lang.detect_text_language`, which is `langdetect`
    behind a shared wrapper the whole suite uses — so a narration names a
    language the same way an alt text or a caption does, and gets the same
    answer. All the segments are joined first on purpose: `langdetect` is
    unreliable on a single short sentence, and an article gives it plenty.

    The consequence of guessing wrong here is worse than an accent. The
    language is what Kokoro phonemises with, so French read as `en-us` is not
    French in an American accent — it is an American reading French spelling
    aloud, letter patterns and all.
    """
    text = " ".join(seg.get("text", "") for seg in segments).strip()
    code = _lang.detect_text_language(text, fallback="en")
    # langdetect distinguishes zh-cn from zh-tw; Kokoro does not.
    base = code.split("-")[0].lower()
    voice = DEFAULT_VOICE_BY_LANG.get(base)
    return (voice, base, False) if voice else (FALLBACK_VOICE, base, True)


# ── Synthesis ──────────────────────────────────────────────────────────────

def synthesise(
    segments: list[dict[str, Any]],
    *,
    voice: str,
    voice_sample: Path | None,
    out_dir: Path,
    lang: str = "",
) -> dict[str, Any]:
    """
    Run Kokoro over the segments and write the concatenated audio.

    Imports happen inside this function so ``--check`` never pays for the
    ONNX Runtime import.

    Parameters
    ----------
    segments : list of dict
        Same shape as ``Segment`` as sprezzature-publish writes it.
    voice : str
        One of the engine's 54 built-in voices, e.g. ``af_heart``. Empty
        means "read the segments, detect the language, pick the voice".
    voice_sample : Path or None
        Must be ``None``. Kokoro does not clone; see :func:`main`.
    out_dir : Path
        Where to write ``narration.wav`` and ``narration.vtt``.
    lang : str
        Overrides the language implied by the voice. Normally empty.

    Returns
    -------
    dict
        ``{"audio", "duration_seconds", "cues", "voice", "ignored_hints"}``.

    Raises
    ------
    RuntimeError
        On a missing install, an unknown voice, or no usable segment. The
        orchestrator prints the message and stops.
    """
    if voice_sample is not None:
        raise RuntimeError(
            "kokoro does not clone voices; it reads with one of its 54 "
            "built-in ones. Use --engine chatterbox or --engine openvoice "
            "for a voice sample, or drop --voice-sample and pick --voice."
        )

    try:
        from kokoro_onnx import Kokoro
    except ImportError as e:
        raise RuntimeError(
            "kokoro-onnx not installed. From a wheel:\n"
            "    pip install 'sprezzature-audio[narrate]'\n"
            "From a clone:\n"
            "    pip install -r requirements-narrate-kokoro.txt"
        ) from e

    paths = model_paths()
    if paths is None:
        raise RuntimeError(
            f"kokoro's weights are not in {CACHE_ROOT}; "
            f"run sprezzature-audio-install-voice --engine kokoro"
        )
    model_path, voices_path = paths

    import numpy as np

    kokoro = Kokoro(str(model_path), str(voices_path), espeak_config=espeak_config())

    available = set(kokoro.get_voices())
    detected = ""
    fallback = False
    if not voice:
        voice, detected, fallback = voice_for_text(segments)
    if voice not in available:
        raise RuntimeError(
            f"unknown voice {voice!r}; this engine has "
            f"{', '.join(sorted(available))}"
        )
    language = lang or language_for(voice)

    out_dir.mkdir(parents=True, exist_ok=True)
    final_path: Path = out_dir / "narration.wav"

    # One timeline for both jobs: it applies the pauses the segments ask for
    # and records where every segment lands, so the narration can be followed
    # in a page. See `_vtt.Timeline`.
    timeline = _vtt.Timeline(SAMPLE_RATE_HZ)
    pieces: list[np.ndarray] = []
    ignored: set[str] = set()

    for index, seg in enumerate(segments):
        text: str = seg.get("text", "").strip()
        if not text:
            continue
        # What the page shows and what the voice says are not always the
        # same string. A formula is notation on the page and a sentence in
        # the ear; a footnote marker is a signpost on the page and a stray
        # number in the ear. The caller resolves that and puts the result in
        # `say`; `text` stays the page's words, because that is what the
        # cue carries and what a read-along highlights.
        spoken: str = (seg.get("say") or text).strip() or text

        for hint, neutral in NEUTRAL_HINTS.items():
            value = seg.get(hint)
            if value not in (None, "", neutral):
                ignored.add(hint)
                # Intensity only matters once an emotion was asked for.
                if seg.get("intensity") not in (None, ""):
                    ignored.add("intensity")

        # Skipped on the first piece: a "pause before" with nothing before it
        # is just dead air at the head of the file.
        if pieces:
            lead = timeline.silence(seg.get("pause_before_ms", 0))
            if lead > 0:
                pieces.append(np.zeros(lead, dtype=np.int16))

        # A segment with nothing speakable in it. A French page closing a
        # quotation on its own line gives a sentence that is one `»`, and
        # the engine refuses it: "nothing to synthesize, produced no
        # phonemes". It cannot simply be dropped -- the page shows it, so
        # the cue has to exist or every later sentence lights up one place
        # out -- so it becomes a short silence that still takes its turn.
        if not _SPEAKABLE.search(spoken):
            quiet = timeline.silence(PUNCTUATION_PAUSE_MS)
            if quiet > 0:
                pieces.append(np.zeros(quiet, dtype=np.int16))
            timeline.speech(0, index=index, text=text)
            continue

        speed: float = PACE_SPEED.get(seg.get("pace", "normal"), 1.0)
        # `trim` cuts the leading and trailing silence the vocoder leaves on
        # every clip. Without it each sentence carries its own padding and
        # the pauses the segments asked for arrive on top of it — the
        # narration drifts slower and slower against its own cues.
        samples, rate = kokoro.create(
            spoken, voice=voice, speed=speed, lang=language, trim=True
        )
        if rate != SAMPLE_RATE_HZ:  # pragma: no cover - the model is fixed at 24 kHz
            raise RuntimeError(
                f"kokoro returned {rate} Hz but this wrapper lays the file out "
                f"at {SAMPLE_RATE_HZ} Hz; every cue after the first would be wrong"
            )

        speech = (np.clip(samples, -1.0, 1.0) * 32_767).astype(np.int16)
        timeline.speech(len(speech), index=index, text=text)
        pieces.append(speech)

        trail = timeline.silence(seg.get("pause_after_ms", 0))
        if trail > 0:
            pieces.append(np.zeros(trail, dtype=np.int16))

    if not pieces:
        raise RuntimeError("no non-empty segments to synthesise")

    full = np.concatenate(pieces)
    with wave.open(str(final_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE_HZ)
        wf.writeframes(full.astype(np.int16).tobytes())

    duration_s: float = len(full) / float(SAMPLE_RATE_HZ)

    # The cues cost nothing to keep -- the offsets were already computed to
    # lay the audio out -- and they are what lets a page follow the reading.
    cues_path: Path = out_dir / "narration.vtt"
    cues_path.write_text(_vtt.speech_to_vtt(timeline.cues), encoding="utf-8")

    # The timeline counted exactly what was appended, so disagreeing with the
    # file it describes means a piece was added behind its back.
    if abs(timeline.total_seconds - duration_s) > 1e-6:
        raise RuntimeError(
            f"timeline says {timeline.total_seconds:.6f}s but the audio is "
            f"{duration_s:.6f}s -- a piece was appended without being recorded"
        )

    return {
        "audio": str(final_path),
        "duration_seconds": duration_s,
        "cues": str(cues_path),
        "voice": voice,
        "language": language,
        # What the text turned out to be written in, when nobody named a
        # voice. Empty when the caller chose one — this is the detector's
        # answer, not a restatement of the request.
        "detected_language": detected,
        # True when the text is in a language Kokoro has no voice for, so it
        # is being read by a voice that does not speak it. Said out loud,
        # because the audio alone will not make it obvious to whoever
        # generated it and does not speak the language either.
        "language_fallback": fallback,
        # Empty on a plain narration. Non-empty means the segments asked for
        # something this engine has no dial for, and the caller should know
        # which engine does.
        "ignored_hints": sorted(ignored),
    }


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Parse the wrapper's command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="sprezzature-audio-narrate-kokoro",
        description=(
            "Kokoro narration engine. Driven by sprezzature-publish-narrate "
            "when a page is being narrated, and runnable on its own."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 when the package and its weights are both present.",
    )
    parser.add_argument("--segments", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument(
        "--voice",
        default="",
        help="A built-in voice. Left empty, the language of the text is "
             "detected and the voice that reads it is chosen for you.",
    )
    parser.add_argument("--voice-sample", type=Path, default=None)
    parser.add_argument(
        "--lang",
        default="",
        help="Override the language the voice implies. Rarely needed.",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="Print the built-in voices, one per line, and exit.",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    if args.check:
        return check_install()
    if args.list_voices:
        paths = model_paths()
        if paths is None:
            print(
                f"FAIL kokoro's weights are not in {CACHE_ROOT}; "
                f"run sprezzature-audio-install-voice --engine kokoro",
                file=sys.stderr,
            )
            return 1
        from kokoro_onnx import Kokoro

        kokoro = Kokoro(str(paths[0]), str(paths[1]), espeak_config=espeak_config())
        for name in sorted(kokoro.get_voices()):
            print(f"{name}\t{language_for(name)}")
        return 0
    if not args.segments or not args.out_dir:
        print("FAIL --segments and --out-dir are required", file=sys.stderr)
        return 1
    segments: list[dict[str, Any]] = json.loads(
        args.segments.read_text(encoding="utf-8"),
    )
    try:
        result = synthesise(
            segments,
            voice=args.voice,
            voice_sample=args.voice_sample,
            out_dir=args.out_dir,
            lang=args.lang,
        )
    except RuntimeError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
