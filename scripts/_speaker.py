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
the ``--segments`` JSON file, the ``--out-dir`` convention, the container the
caller asks for, and the one-line JSON report ``sprezzature-publish`` reads
back off stdout.

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

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import click  # noqa: E402
from _click import run_command, sprezzature_command  # noqa: E402
from _provenance import tag_audio, vtt_note  # noqa: E402

#: What each engine is called on both sides. The names happen to match today;
#: naming the mapping anyway is what keeps a rename here from silently
#: selecting the wrong voice there.
BACKEND_FOR: dict[str, str] = {
    "kokoro": "kokoro",
    "openvoice": "openvoice",
    "chatterbox": "chatterbox",
}

#: The install line to print when ``speaker-helper`` is not there. One line
#: for all three since 2026-11-01: the engines moved into the base install, so
#: there is no extra left to name and no choice left for the reader to get
#: wrong. The mapping is kept rather than collapsed to a constant because
#: ``openvoice`` needs a second step nothing else does -- its weights come
#: from GitHub, fetched by ``sprezzature-audio-install-voice``.
#:
#: ``tests/test_the_kokoro_voice.py`` checks every ``sprezzature-audio[...]``
#: string in this file against the manifest's real extras, which is what
#: caught the three stale hints the day the extras were folded in.
INSTALL_HINT: dict[str, str] = {
    "kokoro": "pip install sprezzature-audio",
    "chatterbox": "pip install sprezzature-audio",
    "openvoice": (
        "pip install sprezzature-audio && sprezzature-audio-install-voice --engine openvoice"
    ),
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
        elif engine == "openvoice":
            from speaker_helper.backends.openvoice import check_install as probe
        elif engine == "chatterbox":
            from speaker_helper.backends.chatterbox import check_install as probe
        else:
            return 1
    except ImportError:
        return 1
    return probe()


def build_command(engine: str) -> click.Command:
    """The command line ``sprezzature-publish`` drives these wrappers with.

    Kept identical across the three engines on purpose: the orchestrator picks
    an engine by module name and then speaks the same flags to whichever it
    got, so a flag that exists on one and not another would fail only for the
    people who switched. Built per engine because the program name and the
    help text name the engine.
    """

    @sprezzature_command(
        f"sprezzature-audio-narrate-{engine}",
        help=(
            f"Narrate a document with the {engine} voice, through "
            f"speaker-helper, and write the audio and its timed track."
        ),
        epilog=(
            "\b\n"
            "Driven by sprezzature-publish-narrate when a page is being\n"
            "narrated, and runnable on its own:\n"
            f"  sprezzature-audio-narrate-{engine} --segments s.json --out-dir ./out\n"
        ),
    )
    @click.option(
        "--check",
        is_flag=True,
        help="Exit 0 when this engine could synthesise here, 1 otherwise.",
    )
    @click.option(
        "--segments", type=click.Path(path_type=Path), help="JSON list of blocks to read."
    )
    @click.option(
        "--out-dir",
        type=click.Path(path_type=Path),
        help="Where the narration and its .vtt go.",
    )
    @click.option(
        "--audio-format",
        default="wav",
        help=(
            "Container for the narration: wav (the default, lossless) or a "
            "lossy one such as mp3. A forty-minute reading is over a hundred "
            "megabytes as WAV and under twenty as a 64 kb/s mp3, and the page "
            "that plays it downloads whichever was written."
        ),
    )
    @click.option(
        "--bitrate",
        default="",
        help=(
            "Bitrate for a lossy --audio-format, e.g. 64k. Left empty, "
            "speaker-helper's own default applies; restating it here is how a "
            "default drifts."
        ),
    )
    @click.option(
        "--voice",
        default="",
        help="A built-in voice. Empty means: detect the language and pick one.",
    )
    @click.option(
        "--voice-sample",
        type=click.Path(path_type=Path),
        default=None,
        help="Reference recording to clone (the cloning engines only).",
    )
    @click.option("--lang", default="", help="Override the language. Rarely needed.")
    @click.option(
        "--lexicon",
        type=click.Path(path_type=Path),
        default=None,
        help=(
            "A pronunciation lexicon (YAML). State once how a word is said and "
            "every synthesis honours it -- which is what an acronym needs."
        ),
    )
    @click.option(
        "--eardrum/--no-eardrum",
        default=True,
        help=(
            "Before reading, run speaker-helper's Ralph Eardrum Loop on the "
            "document: every word at risk (names, acronyms, brands) is said, "
            "heard back by a phoneme recogniser and respelled until it comes "
            "out right. What passes is kept beside the lexicon and applies to "
            "every later narration by this engine. On by default; without the "
            "ear installed the narration goes on and says so."
        ),
    )
    @click.option(
        "--select",
        type=click.IntRange(min=0),
        default=3,
        show_default=True,
        help=(
            "Draw each block up to N times and keep the take whose intonation "
            "and energy agree with the text (speaker-helper's take selector). "
            "Draws are only spent where something can go wrong: a question, a "
            "block tagged with an emotion. 0 or 1: one draw per block."
        ),
    )
    def _cli(
        check: bool,
        segments: Path | None,
        out_dir: Path | None,
        audio_format: str,
        bitrate: str,
        voice: str,
        voice_sample: Path | None,
        lang: str,
        lexicon: Path | None,
        eardrum: bool,
        select: int,
    ) -> int:
        """Click command body: check the install, or narrate the segments."""
        if check:
            return check_narration_install(engine)

        if not segments or not out_dir:
            sys.stderr.write("--segments and --out-dir are both required\n")
            return 2

        # The neighbours' wording and exit code. Without this a mistyped path
        # was a FileNotFoundError traceback, since only the engine's own
        # refusals are caught below.
        if not segments.is_file():
            sys.stderr.write(f"No such file: {segments}\n")
            return 1

        try:
            blocks = json.loads(segments.read_text(encoding="utf-8"))
            report = narrate(
                engine,
                blocks,
                voice=voice,
                voice_sample=voice_sample,
                out_dir=out_dir,
                lang=lang,
                lexicon=lexicon,
                audio_format=audio_format,
                bitrate=bitrate,
                eardrum=eardrum,
                select=select,
            )
        except (RuntimeError, ValueError, NotImplementedError) as exc:
            sys.stderr.write(f"{exc}\n")
            return 1

        # The last non-empty stdout line is the report, by the orchestrator's
        # contract. Nothing else may be printed after it.
        sys.stdout.write(json.dumps(report, ensure_ascii=False) + "\n")
        return 0

    return _cli


def narrate(
    engine: str,
    segments: list[dict[str, Any]],
    *,
    voice: str,
    voice_sample: Path | None,
    out_dir: Path,
    lang: str = "",
    lexicon: Path | None = None,
    audio_format: str = "wav",
    bitrate: str = "",
    eardrum: bool = False,
    select: int = 0,
) -> dict[str, Any]:
    """Read ``segments`` aloud and write the narration beside its cues.

    Returns the report ``sprezzature-publish`` reads back, whose keys are the
    ones it already consumed before the voice moved out — this is a change of
    implementation, not of contract. Two keys were added with the ear:
    ``eardrum`` (what the pronunciation pass heard and fixed) and
    ``selection`` (how many blocks the take selector judged, and agreed).

    ``eardrum`` and ``select`` default to off here and on in the command line:
    a library call keeps doing exactly what it did, a narration asked for at
    the command line gets the ear.
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
    out_dir.mkdir(parents=True, exist_ok=True)

    heard = _eardrum_pass(settings, segments, out_dir) if eardrum else None
    chooser = _take_selector(select)

    async def run() -> Any:
        # The Speaker is built after the ear has spoken: the lexicon, and the
        # verified sidecar the loop just wrote beside it, load with it.
        async with Speaker(settings) as speaker:
            if chooser is None:
                return await speaker.narrate(segments, language=lang or None, voice=voice or None)
            return await speaker.narrate(
                segments, language=lang or None, voice=voice or None, choose=chooser
            )

    result = asyncio.run(run())

    audio_path = out_dir / f"narration.{audio_format.lstrip('.')}"
    cues_path = out_dir / "narration.vtt"
    # `result.write_audio` and not `write_bytes`: the extension then decides
    # the container instead of merely labelling a WAV, and the encoding is
    # `audio-helper`'s craft, reached through speaker-helper rather than by an
    # ffmpeg command line written here. Every caller of this wrapper used to
    # re-encode downstream, each with its own flags.
    #
    # The bitrate is forwarded only when asked. speaker-helper holds the
    # default for speech, and a default restated in a second place is a
    # default that drifts -- the same reason `--lang` is passed through rather
    # than given a fallback here.
    options: dict[str, Any] = {"bitrate": bitrate} if bitrate else {}
    if hasattr(result, "write_audio"):
        result.write_audio(audio_path, **options)
    elif audio_path.suffix.lower() == ".wav":
        # An older speaker-helper, and a WAV asked for: the bytes ARE the file,
        # so this is the same result by a shorter road.
        audio_path.write_bytes(result.wav_bytes)
    else:
        # Refused rather than written, because the silent version of this is
        # the bug being removed: a WAV under an MP3 name plays, so nothing
        # complains, and only its size tells.
        raise RuntimeError(
            f"--audio-format {audio_format} needs speaker-helper 0.14.0 or later, "
            "which is where a result learned to land in the container it is "
            "asked for. Installed here: "
            f"{getattr(__import__('speaker_helper'), '__version__', 'unknown')}.\n"
            "    pip install --upgrade 'speaker-helper>=0.14.0'\n"
            "Or ask for --audio-format wav, which needs no encoder."
        )
    cues_path.write_text(vtt_note(result.to_vtt()), encoding="utf-8")
    # The voice is a model's: say so in the audio file's own metadata (a
    # NOTE block does the same in the .vtt above). Never fatal: a container
    # that cannot take the tag keeps its audio.
    if not tag_audio(audio_path):
        sys.stderr.write(
            f"provenance: could not write the AI mention into {audio_path.name}\n"
        )

    report: dict[str, Any] = {
        "audio": str(audio_path),
        "duration_seconds": result.duration_s,
        "cues": str(cues_path),
        "voice": result.voice_id,
        "language": result.language,
        "detected_language": result.detected_language,
        "language_fallback": result.language_fallback,
        "ignored_hints": result.ignored_hints,
    }
    if heard is not None:
        report["eardrum"] = heard
    selection = getattr(result, "selection", None)
    if chooser is not None and selection:
        judged = [r for r in selection if r.get("agrees") is not None]
        report["selection"] = {
            "blocks": len(selection),
            "judged": len(judged),
            "agree": sum(1 for r in judged if r.get("agrees")),
            "draws": sum(int(r.get("draws", 1)) for r in selection),
        }
    return report


def _eardrum_pass(settings: Any, segments: list[Any], out_dir: Path) -> dict[str, Any]:
    """Run the Ralph Eardrum Loop on the words of ``segments`` before reading.

    The loop is speaker-helper's: it finds the words at risk in the text, says
    each one in carrier sentences with *this* engine, hears it back with a
    phoneme recogniser and has the local model respell it until it comes out
    right. What passes goes to the verified sidecar beside the lexicon, which
    the Speaker built next loads -- so the narration that follows reads the
    fixed spellings, and so does every later one by the same engine.

    It runs on what will be *spoken* (a block's ``say`` when it has one), with
    the very settings of the narration: same engine, same language, same
    lexicon. A word verified on another engine proves nothing here.

    Never fatal. A missing ear, a missing model or a failure inside the loop
    leaves the narration exactly as it would have been, and the report says
    why, so the page still gets its voice.
    """
    try:
        from speaker_helper.eardrum import run_eardrum_async
        from speaker_helper.narration import coerce_segments
    except ImportError as exc:
        sys.stderr.write(
            "eardrum: speaker-helper has no Ralph Eardrum Loop here (0.16.0 or later, "
            f"with its [eardrum] extra); narrating without it ({exc})\n"
        )
        return {"ran": False, "reason": f"not installed: {exc}"}

    text = "\n".join(
        seg.spoken for seg in coerce_segments(segments) if seg.is_speakable and seg.spoken.strip()
    )
    try:
        found = asyncio.run(run_eardrum_async(settings, text=text, out_dir=out_dir / "eardrum"))
    except Exception as exc:  # noqa: BLE001 - the ear must never cost the page its voice
        sys.stderr.write(f"eardrum: the loop failed ({exc}); narrating without it\n")
        return {"ran": False, "reason": f"failed: {exc}"}

    verdicts: dict[str, int] = {}
    for word in found.results:
        verdicts[word.verdict] = verdicts.get(word.verdict, 0) + 1
    still_wrong = [w.word for w in found.results if w.verdict not in ("ok", "fixed")]
    sys.stderr.write(
        f"eardrum: {len(found.results)} word(s) checked ({verdicts}); report {found.html}\n"
    )
    return {
        "ran": True,
        "words": len(found.results),
        "verdicts": verdicts,
        "still_wrong": still_wrong,
        "report": str(found.html),
        "verified": str(found.verified_path) if found.verified_path else None,
    }


def _take_selector(select: int) -> Any:
    """speaker-helper's take selector for ``select`` draws, or ``None``.

    One draw is no choice, so 0 and 1 both mean "the engine's first take", and
    an install without the selector reads one take per block as before.
    """
    if select <= 1:
        return None
    try:
        from speaker_helper.eardrum.expressive import TakeSelector
    except ImportError as exc:
        sys.stderr.write(f"select: no take selector in this speaker-helper ({exc}); one draw\n")
        return None
    return TakeSelector(select)


def main(engine: str, argv: list[str] | None = None) -> int:
    """Run one engine's wrapper; the three console scripts are one line each."""
    return run_command(build_command(engine), argv)
