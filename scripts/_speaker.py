"""
The narration engines, reached through ``speaker-helper``.

Why this file replaced three
----------------------------
This package used to carry its own copy of the voice: the espeak-ng
resolution, the Kokoro session, the OpenVoice checkpoint loading, the
Chatterbox dials — and, in each of the three wrappers, its own copy of the
loop that lays segments out and records where they landed. Three copies of a
loop is how one omission becomes three; it already had, once, with
``pause_before_ms`` computed everywhere and applied nowhere.

The voice is somebody else's job now. ``speaker-helper`` owns the engines, the
timeline, the cues and the refusals, and this module is the thin place where
this package's wire format meets that library's API. What is left here is
exactly what is *about captions and documents* rather than about speech:
the ``--segments`` JSON file, the ``--out-dir`` convention, and the one-line
JSON report ``sprezzature-publish`` reads back off stdout.

What crossed over, and what did not
-----------------------------------
Everything hard-won went with the voice: a block with no phoneme becoming a
silence that keeps its rank, ``say`` distinct from ``text``, the requested
pauses, the truncated-never-rounded timestamps, the invariant that refuses a
timeline disagreeing with its own audio. They are tested there now, against a
backend that needs no model, which is more coverage than they had here.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

#: What each engine is called on both sides. The names happen to match today;
#: naming the mapping anyway is what keeps a rename here from silently
#: selecting the wrong voice there.
BACKEND_FOR: dict[str, str] = {
    "kokoro": "kokoro",
    "kyutai": "kyutai",
    "openvoice": "openvoice",
    "chatterbox": "chatterbox",
}

#: The install line to print when ``speaker-helper`` is not there. Named per
#: engine, because the three do not cost the same: Kokoro is an ONNX runtime,
#: the other two pull torch.
INSTALL_HINT: dict[str, str] = {
    "kokoro": "pip install 'sprezzature-audio[narrate]'",
    "kyutai": "pip install 'sprezzature-audio[narrate-kyutai]'",
    "openvoice": "pip install 'sprezzature-audio[narrate-openvoice]'",
    "chatterbox": "pip install 'sprezzature-audio[narrate-chatterbox]'",
}


def check_narration_install(engine: str) -> int:
    """Return 0 when ``engine`` could actually synthesise, 1 otherwise.

    Asked of ``speaker-helper`` rather than answered here: whether a voice can
    run is a fact about the voice, and a second opinion that disagrees with
    the first is worse than no opinion.
    """
    try:
        if engine == "kokoro":
            from speaker_helper.backends.kokoro import check_install as probe
        elif engine == "kyutai":
            from speaker_helper.backends.kyutai import check_install as probe
        elif engine == "openvoice":
            from speaker_helper.backends.openvoice import check_install as probe
        elif engine == "chatterbox":
            from speaker_helper.backends.chatterbox import check_install as probe
        else:
            return 1
    except ImportError:
        return 1
    return probe()


def build_parser(engine: str) -> argparse.ArgumentParser:
    """The command line ``sprezzature-publish`` drives these wrappers with.

    Kept identical across the three engines on purpose: the orchestrator picks
    an engine by module name and then speaks the same flags to whichever it
    got, so a flag that exists on one and not another would fail only for the
    people who switched.
    """
    parser = argparse.ArgumentParser(
        prog=f"sprezzature-audio-narrate-{engine}",
        description=(
            f"Narrate a document with the {engine} voice, through "
            f"speaker-helper, and write the audio and its timed track."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Driven by sprezzature-publish-narrate when a page is being "
            "narrated, and runnable on its own:\n"
            f"  sprezzature-audio-narrate-{engine} --segments s.json --out-dir ./out\n"
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 when this engine could synthesise here, 1 otherwise.",
    )
    parser.add_argument("--segments", type=Path, help="JSON list of blocks to read.")
    parser.add_argument("--out-dir", type=Path, help="Where narration.wav and .vtt go.")
    parser.add_argument(
        "--voice",
        default="",
        help="A built-in voice. Empty means: detect the language and pick one.",
    )
    parser.add_argument(
        "--voice-sample",
        type=Path,
        default=None,
        help="Reference recording to clone (the cloning engines only).",
    )
    parser.add_argument("--lang", default="", help="Override the language. Rarely needed.")
    parser.add_argument(
        "--lexicon",
        type=Path,
        default=None,
        help=(
            "A pronunciation lexicon (YAML). State once how a word is said and "
            "every synthesis honours it -- which is what an acronym needs."
        ),
    )
    return parser


def narrate(
    engine: str,
    segments: list[dict[str, Any]],
    *,
    voice: str,
    voice_sample: Path | None,
    out_dir: Path,
    lang: str = "",
    lexicon: Path | None = None,
) -> dict[str, Any]:
    """Read ``segments`` aloud and write ``narration.wav`` beside its cues.

    Returns the report ``sprezzature-publish`` reads back, whose keys are the
    ones it already consumed before the voice moved out — this is a change of
    implementation, not of contract.
    """
    try:
        from speaker_helper import Settings, Speaker
    except ImportError as exc:
        raise RuntimeError(
            f"the voice lives in speaker-helper now. Install it with:\n"
            f"    {INSTALL_HINT.get(engine, INSTALL_HINT['kokoro'])}"
        ) from exc

    mapping: dict[str, Any] = {
        "backend": BACKEND_FOR[engine],
        "voice": voice,
        "voice_sample": str(voice_sample) if voice_sample else "",
    }
    # Only when asked. This used to say `lang or "fr"`, which restated
    # speaker-helper's own default in a second place -- and a default copied
    # is a default that drifts. `narrate(language=None)` detects anyway, so
    # the field is a fallback, and the fallback belongs to whoever owns the
    # voice.
    if lang:
        mapping["language"] = lang
    # An acronym is the whole reason this knob exists. "GMTED2010", "WebVTT",
    # "RTTM", "OKLCH" and "Qwen3-VL" are read letter-salad by every engine
    # that has to guess; stated once in the lexicon, they come out the same
    # way in every narration this suite produces. Kokoro splices the IPA
    # verbatim at the phonemisation step it already runs; the other engines
    # get the respelling tier.
    if lexicon is not None:
        mapping["lexicon"] = {"path": str(lexicon), "enabled": True}
    settings = Settings.from_mapping(mapping)

    async def run() -> Any:
        async with Speaker(settings) as speaker:
            return await speaker.narrate(segments, language=lang or None, voice=voice or None)

    result = asyncio.run(run())

    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / "narration.wav"
    cues_path = out_dir / "narration.vtt"
    audio_path.write_bytes(result.wav_bytes)
    cues_path.write_text(result.to_vtt(), encoding="utf-8")

    return {
        "audio": str(audio_path),
        "duration_seconds": result.duration_s,
        "cues": str(cues_path),
        "voice": result.voice_id,
        "language": result.language,
        "detected_language": result.detected_language,
        "language_fallback": result.language_fallback,
        "ignored_hints": result.ignored_hints,
    }


def main(engine: str, argv: list[str] | None = None) -> int:
    """Run one engine's wrapper; the three console scripts are one line each."""
    args = build_parser(engine).parse_args(argv)

    if args.check:
        return check_narration_install(engine)

    if not args.segments or not args.out_dir:
        sys.stderr.write("--segments and --out-dir are both required\n")
        return 2

    try:
        segments = json.loads(args.segments.read_text(encoding="utf-8"))
        report = narrate(
            engine,
            segments,
            voice=args.voice,
            voice_sample=args.voice_sample,
            out_dir=args.out_dir,
            lang=args.lang,
            lexicon=args.lexicon,
        )
    except (RuntimeError, ValueError, NotImplementedError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    # The last non-empty stdout line is the report, by the orchestrator's
    # contract. Nothing else may be printed after it.
    sys.stdout.write(json.dumps(report, ensure_ascii=False) + "\n")
    return 0
