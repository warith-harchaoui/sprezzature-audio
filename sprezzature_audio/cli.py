"""
The argparse command line — ``make-audio``.

Fifteen tools ship here, each with its own command, and that is the right
shape for the work: `sprezzature-audio-audit` in a pre-commit hook,
`sprezzature-audio-install-voice` once when the machine is new. What fifteen
separate commands do not give you is a way to find out what this package does
without reading its README — and fifteen is well past the number anybody
keeps in their head.

So this is the front door. ``make-audio`` lists the tools, says what each one
is for, and dispatches to it — the same engine, reached by a name you can
guess. :mod:`sprezzature_audio.cli_click` is its twin, reading the same
arguments with click.

The table below carries the extra each tool needs, so that a tool whose
dependency is missing says which ``pip install`` fixes *it* — not which one
fixes the package in general. Reaching for `narrate` and being told to
install the captions extra is worse than no message at all.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import importlib
import sys

from sprezzature_audio_scripts._argparse import make_parser

#: Every tool: sub-command name → (module, extra, the one line that says when
#: to reach for it). The table is the dispatcher *and* the help text, so a
#: tool cannot be listed and unreachable, or reachable and undocumented.
#:
#: ``extra`` is the empty string for the tools that need nothing beyond a bare
#: install. Those are not the small ones by accident: reading a caption track,
#: auditing it, attributing speakers over an existing transcript and scoring
#: the result are exactly the jobs that should run in a hook, on any machine,
#: with no model anywhere near them.
TOOLS: dict[str, tuple[str, str, str]] = {
    "audit": (
        "audit_captions",
        "",
        "Report every cue that cannot be read as timed — too fast, too "
        "short, too long, too many lines. Standard library only.",
    ),
    "benchmark": (
        "benchmark_stt",
        "",
        "Word error rate, diarization error rate and real-time factor, so "
        "'it got better' stops being an opinion.",
    ),
    "captions": (
        "captions_from_whisper",
        "captions",
        "Recording → a timed transcript. The long job of this package: a "
        "multi-gigabyte model and minutes of work.",
    ),
    "diarize": (
        "diarize_from_nemo",
        "diarize",
        "Mark who spoke when, without yet knowing anyone's name.",
    ),
    "identify": (
        "identify_from_titanet",
        "diarize",
        "Match diarized speakers against labelled reference samples, so the "
        "turns get names.",
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
        "Ask a local model to name the speakers from what they say. Needs "
        "Ollama running; no extra to install.",
    ),
    "translate": (
        "translate_captions",
        "translate",
        "Translate a caption track with a local model, keeping its timings "
        "and dropping the <v> tags W3C reserves for one language.",
    ),
    "narrate": (
        "narrate_kokoro",
        "narrate",
        "Document → narration, with the timed track beside it. Kokoro, the "
        "default voice since 1.3.0.",
    ),
    "narrate-openvoice": (
        "narrate_openvoice",
        "narrate-openvoice",
        "The same narration through OpenVoice, when a cloned voice is what "
        "is wanted.",
    ),
    "narrate-chatterbox": (
        "narrate_chatterbox",
        "narrate-chatterbox",
        "The same narration through Chatterbox.",
    ),
    "voice": (
        "pick_voice",
        "narrate",
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


def build_parser() -> argparse.ArgumentParser:
    """The parser, built separately so a test can read it without running it."""
    width = max(len(name) for name in TOOLS)
    catalogue = "\n".join(
        f"  {name:<{width}}  {summary}" for name, (_, _, summary) in TOOLS.items()
    )
    parser = make_parser(
        prog="make-audio",
        description=(
            "Everything this package does with a recording and a voice. One "
            "front door over the fifteen tools it ships; each is also its own "
            "command, which is what a script should call."
        ),
        epilog=(
            f"Tools:\n{catalogue}\n"
            "\n"
            "Examples:\n"
            "  make-audio audit subtitles.vtt\n"
            "  make-audio captions talk.mp4 --out talk.vtt\n"
            "  make-audio narrate post.md --out post.mp3\n"
            "\n"
            "Every argument after the tool name belongs to that tool; run\n"
            "`make-audio <tool> --help` to see them.\n"
        ),
    )
    parser.add_argument(
        "tool",
        choices=sorted(TOOLS),
        help="Which tool to run. See the list below.",
    )
    # Everything after the tool name belongs to the tool, including flags this
    # parser also defines. Without REMAINDER, `make-audio audit --help` would
    # print *this* help rather than the audit's, which is the opposite of what
    # the reader asked for.
    parser.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the tool.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    Dispatch to one of the fifteen tools.

    Parameters
    ----------
    argv : list of str or None, optional
        Argument vector without ``argv[0]``. Reads ``sys.argv`` when ``None``.

    Returns
    -------
    int
        Whatever the dispatched tool returns.
    """
    args = build_parser().parse_args(argv)
    module_name, extra, _ = TOOLS[args.tool]
    try:
        module = importlib.import_module(f"sprezzature_audio_scripts.{module_name}")
    except ImportError as exc:  # pragma: no cover - dependency guard
        sys.stderr.write(_missing_extra_message(args.tool, extra, exc))
        return 2

    # The tools read sys.argv themselves — they were commands before they were
    # sub-commands, and they still are. Handing them a rewritten argv is what
    # lets both be true.
    saved = sys.argv
    try:
        sys.argv = [f"make-audio {args.tool}", *args.rest]
        return int(module.main() or 0)
    finally:
        sys.argv = saved


def _missing_extra_message(tool: str, extra: str, exc: Exception) -> str:
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
        f"{tool}: needs nothing optional, so this is not a missing extra — "
        f"something else failed to import.\n  ({exc})\n"
    )


if __name__ == "__main__":
    sys.exit(main())
