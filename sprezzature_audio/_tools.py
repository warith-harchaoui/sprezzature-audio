#!/usr/bin/env python3
"""
The catalogue of tools this package ships, and the one sentence said about a
missing extra.

Lifted out of the command line on 2026-10-25, when the argparse front door was
removed and click became the only one. It lives here rather than in ``cli`` so
the catalogue owes nothing to whichever parser reads it — the previous
arrangement had the click module importing ``TOOLS`` from the argparse module,
which is why neither could be deleted without the other.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

#: Every tool: sub-command name → (module, extra, the one line that says when
#: to reach for it). The table is the dispatcher *and* the help text, so a
#: tool cannot be listed and unreachable, or reachable and undocumented.
#:
#: ``extra`` is now the empty string for **every** tool: the extras were
#: folded into the base install on 2026-11-01, so a tool whose import fails is
#: a broken install rather than a choice the reader did not make. The field is
#: kept rather than removed because the shape is shared with the click twin
#: and because an extra may legitimately come back -- and because the empty
#: string already meant exactly this for the tools that need nothing beyond a bare
#: install. Those are not the small ones by accident: reading a caption track,
#: auditing it, attributing speakers over an existing transcript and scoring
#: the result are exactly the jobs that should run in a hook, on any machine,
#: with no model anywhere near them.
TOOLS: dict[str, tuple[str, str, str]] = {
    "audit": (
        "audit_captions",
        "",
        "Report every cue that cannot be read as timed — too fast, too "
        "short, too long, too many lines. No model, no network.",
    ),
    "benchmark": (
        "benchmark_stt",
        "",
        "Word error rate, diarization error rate and real-time factor, so "
        "'it got better' stops being an opinion.",
    ),
    "captions": (
        "captions_from_whisper",
        "",
        "Recording → a timed transcript. The long job of this package: a "
        "multi-gigabyte model and minutes of work.",
    ),
    "diarize": (
        "diarize_from_nemo",
        "",
        "Mark who spoke when, without yet knowing anyone's name.",
    ),
    "identify": (
        "identify_from_titanet",
        "",
        "Match diarized speakers against labelled reference samples, so the turns get names.",
    ),
    "pipeline": (
        "caption_diarize",
        "",
        "Captions + speaker turns → one attributed track. Pure merge: both "
        "halves are already on disk.",
    ),
    "name": (
        "name_from_transcript",
        "",
        "Guess the speakers' names from what they say: introduction and "
        "vocative patterns, plus a local-model pass with --ollama.",
    ),
    "translate": (
        "translate_captions",
        "",
        "Translate a caption track with a local model, keeping its timings "
        "and dropping the <v> tags W3C reserves for one language.",
    ),
    "narrate": (
        "narrate_kokoro",
        "",
        "Document → narration, with the timed track beside it, in the Kokoro "
        "voice. Which engine reads a document is speaker-helper's router's call.",
    ),
    "narrate-openvoice": (
        "narrate_openvoice",
        "",
        "The same narration through OpenVoice, when a cloned voice is what is wanted.",
    ),
    "narrate-chatterbox": (
        "narrate_chatterbox",
        "",
        "The same narration through Chatterbox.",
    ),
    "voice": (
        "pick_voice",
        "",
        "Hear the available voices and measure how flat each one is, before "
        "committing a long document to one of them.",
    ),
    "install": (
        "install_captions",
        "",
        "Pre-download what transcription needs, so the first real run is not "
        "also the first download.",
    ),
    "install-diarize": (
        "install_diarize",
        "",
        "The same, for the diarization and identification models.",
    ),
    "install-voice": (
        "install_narrate",
        "",
        "The same, for a narration engine's weights — and it checks for the "
        "system espeak-ng that pip cannot supply.",
    ),
}


def missing_extra_message(tool: str, extra: str, exc: Exception) -> str:
    """What to say when a tool's dependency is not installed.

    Shared with the click twin so the two front doors cannot drift into
    saying different things about the same missing package.
    """
    if extra:
        return (
            f"{tool}: its dependencies are an optional extra, so a bare "
            f"install stays small. Add them with:\n"
            f"    pip install 'sprezzature-audio[{extra}]'\n"
            f"  ({exc})\n"
        )
    return (
        f"{tool}: everything it needs is in the base install, so this is not "
        f"a missing extra — something failed to import on a complete install. "
        f"Reinstall with:\n"
        f"    pip install sprezzature-audio\n"
        f"  ({exc})\n"
    )
