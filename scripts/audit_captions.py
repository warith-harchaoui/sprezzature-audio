#!/usr/bin/env python3
"""
audit_captions — are these captions readable at the speed they go by?

This package drafts captions, diarizes speakers and translates tracks. What it
never asked is whether the result can be *read*. That question is not the same
as whether the transcription is accurate: a perfectly accurate caption that
holds 90 characters on screen for half a second is unreadable, and a
perfectly accurate track whose cues overlap renders as two lines fighting for
the same space.

Whether a ``<track>`` element exists at all is the HTML linter's question, and
``sprezzature-accessibility`` answers it. Whether what is inside that track is
usable is this package's, and nothing asked it until now.

The rules are static — they need the caption file and nothing else — and they
come from the published style guides rather than from taste:

================  =========================================================
``cue-overlap``   A cue starts before the previous one ends. Renderers
                  either stack them or drop one; neither is what was meant.
``cue-reversed``  End before start, or cues out of order.
``cue-empty``     A timed cue with no text: a blank box, on screen, timed.
``cue-too-fast``  Above the reading-speed ceiling (Netflix TTSG: 17
                  characters per second for adult content).
``cue-too-brief`` Under the minimum duration (Netflix TTSG: 5/6 second).
                  Below that the eye registers a flash, not a sentence.
``cue-too-long``  Over the maximum duration (Netflix TTSG: 7 seconds). A cue
                  that lingers has usually swallowed a sentence boundary.
``line-too-wide`` Over the per-line character budget (Netflix TTSG: 42).
                  Wider lines wrap unpredictably across players.
``too-many-lines``More than two lines in one cue (BBC and Netflix agree).
================  =========================================================

Every threshold is a flag, because the numbers are conventions rather than
laws and a children's programme or a dense technical talk justifies different
ones. The defaults are named so nobody has to guess where they came from.

Usage
-----
::

    sprezzature-audio-audit talk.vtt
    sprezzature-audio-audit talk.srt --cps 20 --format json

Exits 1 when any finding is reported, so it gates a build the way the lint
half of every sibling brick does.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _argparse import make_parser  # noqa: E402
from _vtt import Cue, parse  # noqa: E402

#: Netflix Timed Text Style Guide, adult content. Named rather than inlined
#: so the next reader knows these are conventions with a source, not numbers
#: somebody liked.
DEFAULT_CPS: float = 17.0
DEFAULT_MIN_SECONDS: float = 5 / 6
DEFAULT_MAX_SECONDS: float = 7.0
DEFAULT_LINE_CHARS: int = 42
DEFAULT_MAX_LINES: int = 2


@dataclass(frozen=True)
class Finding:
    """One caption that cannot be read as timed."""

    rule: str
    cue: int
    start: float
    message: str

    def __str__(self) -> str:
        return f"cue {self.cue} @ {self.start:7.3f}s  {self.rule}: {self.message}"


def _characters(cue: Cue) -> int:
    """Visible characters, which is what a reader actually processes."""
    return len(re.sub(r"\s+", " ", cue.text).strip())


def audit(
    cues: list[Cue],
    *,
    cps: float = DEFAULT_CPS,
    min_seconds: float = DEFAULT_MIN_SECONDS,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    line_chars: int = DEFAULT_LINE_CHARS,
    max_lines: int = DEFAULT_MAX_LINES,
) -> list[Finding]:
    """Report every cue that cannot be read as timed."""
    findings: list[Finding] = []
    previous: Cue | None = None
    previous_index = 0

    # The shared reader returns cues in time order without numbering them —
    # a cue's identity is its position in the track, which is what a reader
    # scrubbing a timeline actually counts.
    for index, cue in enumerate(cues, start=1):
        if cue.end <= cue.start:
            findings.append(Finding(
                "cue-reversed", index, cue.start,
                f"ends at {cue.end:.3f}s, which is not after it starts",
            ))
        if previous is not None and cue.start < previous.end:
            findings.append(Finding(
                "cue-overlap", index, cue.start,
                f"starts {previous.end - cue.start:.3f}s before cue "
                f"{previous_index} ends; players either stack the two or drop "
                f"one, and neither is what was meant",
            ))
        if not cue.text.strip():
            findings.append(Finding(
                "cue-empty", index, cue.start,
                "a timed cue with no text: a blank caption box, on screen, "
                "for its full duration",
            ))
            previous, previous_index = cue, index
            continue

        duration = max(cue.duration, 0.0)
        if 0 < duration < min_seconds:
            findings.append(Finding(
                "cue-too-brief", index, cue.start,
                f"{duration:.3f}s on screen, under the {min_seconds:.3f}s "
                f"floor; the eye registers a flash, not a sentence",
            ))
        if duration > max_seconds:
            findings.append(Finding(
                "cue-too-long", index, cue.start,
                f"{duration:.1f}s on screen, over the {max_seconds:.0f}s "
                f"ceiling; a cue that lingers has usually swallowed a "
                f"sentence boundary",
            ))
        if duration > 0:
            speed = _characters(cue) / duration
            if speed > cps:
                findings.append(Finding(
                    "cue-too-fast", index, cue.start,
                    f"{speed:.1f} characters per second, over the {cps:.0f} "
                    f"ceiling: accurate and still unreadable at the speed it "
                    f"goes by",
                ))
        for line in cue.lines:
            if len(line) > line_chars:
                findings.append(Finding(
                    "line-too-wide", index, cue.start,
                    f"a line of {len(line)} characters, over the "
                    f"{line_chars}-character budget; wider lines wrap "
                    f"differently in every player",
                ))
                break
        if len(cue.lines) > max_lines:
            findings.append(Finding(
                "too-many-lines", index, cue.start,
                f"{len(cue.lines)} lines in one cue, over {max_lines}; the "
                f"extra lines cover the picture they are describing",
            ))
        previous, previous_index = cue, index

    return findings


def main(argv: list[str] | None = None) -> int:
    """Audit one caption file. Returns the process exit code."""
    parser = make_parser(
        prog="sprezzature-audio-audit",
        description=(
            "Check that a caption track can be read at the speed it goes by: "
            "no overlapping or reversed cues, nothing too fast, too brief, "
            "too long, too wide or too tall. Reads WebVTT or SubRip."
        ),
        epilog=(
            "Examples:\n"
            "  sprezzature-audio-audit talk.vtt\n"
            "  sprezzature-audio-audit talk.srt --cps 20\n"
            "  sprezzature-audio-audit talk.vtt --format json\n"
            "\n"
            "Defaults follow the Netflix Timed Text Style Guide for adult "
            "content (17 cps, 5/6 s minimum, 7 s maximum, 42 characters per "
            "line) and the two-line convention BBC and Netflix share. They "
            "are conventions, not laws: a children's programme or a dense "
            "technical talk justifies different numbers, which is why each "
            "one is a flag.\n"
        ),
    )
    parser.add_argument("track", type=Path, help="A .vtt or .srt file.")
    parser.add_argument(
        "--cps", type=float, default=DEFAULT_CPS, metavar="N",
        help=f"Reading-speed ceiling, characters per second (default: {DEFAULT_CPS:.0f}).",
    )
    parser.add_argument(
        "--min-seconds", type=float, default=DEFAULT_MIN_SECONDS, metavar="S",
        help="Shortest a cue may stay on screen (default: 5/6 s).",
    )
    parser.add_argument(
        "--max-seconds", type=float, default=DEFAULT_MAX_SECONDS, metavar="S",
        help=f"Longest a cue may stay on screen (default: {DEFAULT_MAX_SECONDS:.0f} s).",
    )
    parser.add_argument(
        "--line-chars", type=int, default=DEFAULT_LINE_CHARS, metavar="N",
        help=f"Characters per line (default: {DEFAULT_LINE_CHARS}).",
    )
    parser.add_argument(
        "--max-lines", type=int, default=DEFAULT_MAX_LINES, metavar="N",
        help=f"Lines per cue (default: {DEFAULT_MAX_LINES}).",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text",
        help="Output shape (default: text).",
    )
    args = parser.parse_args(argv)

    if not args.track.is_file():
        sys.stderr.write(f"{args.track}: no such file\n")
        return 2

    cues = parse(args.track.read_text(encoding="utf-8", errors="replace"))
    if not cues:
        sys.stderr.write(
            f"{args.track}: no cues found — is this a WebVTT or SubRip file?\n"
        )
        return 2

    findings = audit(
        cues,
        cps=args.cps,
        min_seconds=args.min_seconds,
        max_seconds=args.max_seconds,
        line_chars=args.line_chars,
        max_lines=args.max_lines,
    )

    if args.format == "json":
        json.dump(
            {
                "cues": len(cues),
                "findings_total": len(findings),
                "findings": [
                    {
                        "rule": f.rule, "cue": f.cue,
                        "start": round(f.start, 3), "message": f.message,
                    }
                    for f in findings
                ],
            },
            sys.stdout, indent=2, ensure_ascii=False,
        )
        sys.stdout.write("\n")
    else:
        for finding in findings:
            print(finding)
        print(
            f"{len(cues)} cue(s), {len(findings)} finding(s)." if findings
            else f"{len(cues)} cue(s), all readable."
        )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
