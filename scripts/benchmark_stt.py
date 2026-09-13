"""
benchmark_stt — measure transcription quality and speed, and say so in numbers.

Why this exists
---------------
"The transcription got better" is an opinion until something measures it.
This script turns the two questions that actually matter into numbers you
can put side by side across models, backends and settings:

**How good is it?**
    *Word Error Rate* (WER) against a reference transcript — the share of
    reference words that had to be substituted, deleted or inserted to reach
    the hypothesis. 0.0 is perfect; 0.15 means roughly one word in seven is
    wrong. Reported with its substitution / deletion / insertion split,
    because the three fail differently: deletions usually mean the decoder
    gave up on a passage, insertions usually mean it hallucinated through
    silence, and substitutions are ordinary mishearing.

**How good is *who spoke when*?**
    *Diarization Error Rate* (DER) against a reference RTTM — missed speech,
    false alarm and speaker confusion, over total reference speech. Computed
    on 10 ms frames with the standard 250 ms collar around every reference
    boundary (annotators do not agree to the millisecond, and scoring a
    boundary to the millisecond measures the annotator, not the system), and
    with the optimal speaker permutation, since a system that gets every turn
    right but names the speakers differently has made no error.

**How fast is it?**
    *Real-Time Factor* (RTF) — processing seconds per audio second. 0.25 means
    a one-hour recording is done in fifteen minutes. Below 1.0 is faster than
    real time.

On the algorithms
-----------------
WER is Levenshtein distance with the edit counts carried through the dynamic
program; DER is the NIST definition with a collar. Both are standard, decades
old, and implemented here directly so a benchmark run needs no extra
dependency: a measurement tool that is hard to install does not get used, and
one nobody runs is worse than none, because it lets "it feels faster" stand
unchallenged.

The caption parser is the one in :mod:`caption_diarize`, not a second copy —
a benchmark that parsed its input differently from the pipeline would measure
the parser.

Usage
-----
::

    # Quality of a transcript against a reference
    python benchmark_stt.py --reference truth.vtt --hypothesis whisper.vtt

    # Quality of speaker attribution
    python benchmark_stt.py --reference-rttm truth.rttm --hypothesis-rttm out.rttm

    # Speed: time a command over a known audio duration
    python benchmark_stt.py --audio-seconds 3600 --time-command \\
        "python captions_from_whisper.py meeting.mp4"

    # Everything, as JSON for a spreadsheet or a CI job
    python benchmark_stt.py --reference truth.vtt --hypothesis out.vtt --json

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import itertools
import json
import re
import shlex
import subprocess
import sys
import time
import unicodedata
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _argparse import make_parser  # noqa: E402
from _device import describe as describe_device  # noqa: E402
from _device import report as device_report  # noqa: E402
from caption_diarize import parse_caption_cues  # noqa: E402

#: Frame length for DER scoring, in seconds. 10 ms is the NIST convention.
FRAME: float = 0.010

#: Forgiveness collar around each reference boundary, in seconds. Also the
#: NIST convention: human annotators do not agree to the millisecond, so
#: scoring a boundary that finely measures the annotator, not the system.
COLLAR: float = 0.250

#: Above this many hypothesis speakers the optimal-permutation search stops
#: being free. Brute force over 8! is 40 320 mappings, which is still fast;
#: past that the script says so rather than appearing to hang.
MAX_PERMUTATION_SPEAKERS: int = 8


# ── Text normalisation ────────────────────────────────────────────────────


def normalise_words(text: str) -> list[str]:
    """
    Split `text` into the tokens WER should compare.

    Case, punctuation and Unicode form are removed because a system is not
    wrong for writing "Bonjour," where the reference has "bonjour". The
    apostrophe is kept as a *separator* so a French clitic stays its own
    token on both sides ("l'éthyle" → ``["l'", "éthyle"]``): applied to
    reference and hypothesis alike, the convention cancels out, and it stops
    a single elision from counting as a whole wrong word.

    Parameters
    ----------
    text : str
        Raw transcript text.

    Returns
    -------
    list of str
        Lower-case tokens, punctuation stripped.
    """
    text = unicodedata.normalize("NFC", text).lower()
    text = text.replace("’", "'")
    text = re.sub(r"'", "' ", text)
    text = re.sub(r"[^\w' -]", " ", text, flags=re.UNICODE)
    return [w for w in text.split() if w.strip("'-")]


# ── Word Error Rate ───────────────────────────────────────────────────────


def word_error_rate(reference: Sequence[str], hypothesis: Sequence[str]) -> dict[str, Any]:
    """
    WER between two token sequences, with its edit breakdown.

    Levenshtein distance, carrying the substitution / deletion / insertion
    counts through the dynamic program so the result says *how* it went wrong
    and not only how much. The three are not interchangeable: a run of
    deletions is a decoder that stopped, a run of insertions is one that
    invented, and either is a different bug from ordinary mishearing.

    Parameters
    ----------
    reference : sequence of str
        Ground-truth tokens, from :func:`normalise_words`.
    hypothesis : sequence of str
        System output tokens, normalised the same way.

    Returns
    -------
    dict
        ``wer`` (0.0 = perfect), ``sub``, ``del``, ``ins``, ``hits``,
        ``n_ref``, ``n_hyp``.

    Examples
    --------
    >>> word_error_rate(["a", "b", "c"], ["a", "x", "c"])["sub"]
    1
    >>> word_error_rate(["a", "b"], ["a", "b"])["wer"]
    0.0
    """
    n, m = len(reference), len(hypothesis)
    # Each cell is (cost, substitutions, deletions, insertions); comparing
    # tuples orders by cost first, so ``min`` picks the cheapest path and
    # breaks ties consistently.
    previous: list[tuple[int, int, int, int]] = [(j, 0, 0, j) for j in range(m + 1)]
    for i in range(1, n + 1):
        current: list[Any] = [(i, 0, i, 0)] + [None] * m
        for j in range(1, m + 1):
            if reference[i - 1] == hypothesis[j - 1]:
                current[j] = previous[j - 1]
            else:
                sub = (previous[j - 1][0] + 1, previous[j - 1][1] + 1, previous[j - 1][2], previous[j - 1][3])
                dele = (previous[j][0] + 1, previous[j][1], previous[j][2] + 1, previous[j][3])
                ins = (current[j - 1][0] + 1, current[j - 1][1], current[j - 1][2], current[j - 1][3] + 1)
                current[j] = min(sub, dele, ins)
        previous = current

    cost, substitutions, deletions, insertions = previous[m]
    return {
        "wer": cost / max(n, 1),
        "sub": substitutions,
        "del": deletions,
        "ins": insertions,
        "hits": n - substitutions - deletions,
        "n_ref": n,
        "n_hyp": m,
    }


# ── Reading the standard formats ──────────────────────────────────────────


def read_transcript(path: Path) -> list[str]:
    """
    Tokens from a ``.vtt``, ``.srt`` or plain-text transcript.

    Captions go through :func:`caption_diarize.parse_caption_cues`, the same
    parser the pipeline uses, so the benchmark cannot disagree with the tool
    it is benchmarking about what the file says.

    Parameters
    ----------
    path : pathlib.Path
        Transcript file.

    Returns
    -------
    list of str
        Normalised tokens in reading order.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".vtt", ".srt"):
        cues = parse_caption_cues(text)
        return [w for cue in cues for w in normalise_words(str(cue["text"]))]
    return normalise_words(text)


def read_rttm(path: Path) -> list[tuple[str, float, float]]:
    """
    Speaker segments from an RTTM file.

    RTTM is the NIST rich-transcription format the diarizer already writes:
    whitespace-separated fields, one ``SPEAKER`` line per turn, with onset
    and duration in fields 4 and 5 and the speaker label in field 8.

    Parameters
    ----------
    path : pathlib.Path
        ``.rttm`` file.

    Returns
    -------
    list of tuple
        ``(label, start_seconds, end_seconds)``, in file order.

    Raises
    ------
    ValueError
        If the file holds no usable ``SPEAKER`` line, which almost always
        means the wrong file was passed rather than that diarization failed.
    """
    segments: list[tuple[str, float, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[0].upper() != "SPEAKER":
            continue
        try:
            onset, duration = float(fields[3]), float(fields[4])
        except ValueError:
            continue
        segments.append((fields[7], onset, onset + duration))
    if not segments:
        raise ValueError(f"{path}: no SPEAKER lines — is this an RTTM file?")
    return segments


# ── Diarization Error Rate ────────────────────────────────────────────────


def _frame_count(total: float) -> int:
    """Number of scoring frames covering `total` seconds."""
    return max(1, int(round(total / FRAME)))


def _to_frames(
    segments: Iterable[tuple[str, float, float]],
    total: float,
    labels: Sequence[str],
) -> list[set[int]]:
    """Per-frame sets of active speaker indices; overlap is a set of size > 1."""
    count = _frame_count(total)
    out: list[set[int]] = [set() for _ in range(count)]
    for label, start, end in segments:
        index = labels.index(label)
        for frame in range(max(0, int(start / FRAME)), min(count, int(end / FRAME) + 1)):
            out[frame].add(index)
    return out


def _collar_mask(segments: Iterable[tuple[str, float, float]], total: float) -> list[bool]:
    """Frames within COLLAR of any reference boundary, which scoring skips."""
    count = _frame_count(total)
    mask = [False] * count
    for _, start, end in segments:
        for boundary in (start, end):
            lo = max(0, int((boundary - COLLAR) / FRAME))
            hi = min(count, int((boundary + COLLAR) / FRAME) + 1)
            for frame in range(lo, hi):
                mask[frame] = True
    return mask


def diarization_error_rate(
    reference: Sequence[tuple[str, float, float]],
    hypothesis: Sequence[tuple[str, float, float]],
    total: float | None = None,
    *,
    collar: bool = True,
) -> dict[str, Any]:
    """
    DER between two sets of speaker segments.

    Missed speech, false alarm and speaker confusion, summed over frames and
    divided by total reference speech. The hypothesis labels are mapped onto
    the reference labels by whichever permutation scores best, because a
    system that segments perfectly and calls the speakers ``spk0``/``spk1``
    where the reference says ``Alice``/``Bob`` has made no error at all.

    Parameters
    ----------
    reference, hypothesis : sequence of tuple
        ``(label, start, end)`` triples, as :func:`read_rttm` returns.
    total : float, optional
        Scored duration in seconds. Defaults to the last end time seen.
    collar : bool, optional
        Apply the 250 ms forgiveness collar. Pass ``False`` for the stricter
        no-collar number; report both when comparing against a paper, since
        which one was used moves the figure a great deal.

    Returns
    -------
    dict
        ``der``, the three error durations in seconds, ``speech_s``, and the
        winning ``mapping`` from hypothesis label to reference label.

    Raises
    ------
    ValueError
        If the hypothesis names more speakers than the permutation search
        can enumerate.
    """
    reference_labels = sorted({s[0] for s in reference})
    hypothesis_labels = sorted({s[0] for s in hypothesis})
    if len(hypothesis_labels) > MAX_PERMUTATION_SPEAKERS:
        raise ValueError(
            f"{len(hypothesis_labels)} hypothesis speakers is past the "
            f"{MAX_PERMUTATION_SPEAKERS}-speaker brute-force limit."
        )

    if total is None:
        total = max(
            [s[2] for s in reference] + [s[2] for s in hypothesis] or [0.0]
        )

    reference_frames = _to_frames(reference, total, reference_labels)
    hypothesis_frames = _to_frames(hypothesis, total, hypothesis_labels)
    excluded = _collar_mask(reference, total) if collar else [False] * len(reference_frames)

    # A hypothesis speaker mapped to -1 is one the reference never had: its
    # frames can only ever be false alarms, never hits.
    candidates = list(range(len(reference_labels))) + [-1] * max(len(hypothesis_labels), 1)
    best: dict[str, Any] | None = None
    for permutation in set(itertools.permutations(candidates, len(hypothesis_labels))):
        missed = false_alarm = confusion = speech = 0
        for frame in range(len(reference_frames)):
            if excluded[frame]:
                continue
            ref_active = reference_frames[frame]
            hyp_active = {permutation[i] for i in hypothesis_frames[frame]}
            speech += len(ref_active)
            correct = len(ref_active & hyp_active)
            missed += max(0, len(ref_active) - len(hyp_active))
            false_alarm += max(0, len(hyp_active) - len(ref_active))
            confusion += min(len(ref_active), len(hyp_active)) - correct
        rate = (missed + false_alarm + confusion) / max(speech, 1)
        if best is None or rate < best["der"]:
            best = {
                "der": rate,
                "missed_s": missed * FRAME,
                "false_alarm_s": false_alarm * FRAME,
                "confusion_s": confusion * FRAME,
                "speech_s": speech * FRAME,
                "mapping": {
                    hypothesis_labels[i]: (reference_labels[p] if p >= 0 else None)
                    for i, p in enumerate(permutation)
                },
            }
    assert best is not None  # at least the empty permutation is always scored
    best["n_ref_speakers"] = len(reference_labels)
    best["n_hyp_speakers"] = len(hypothesis_labels)
    return best


# ── Speed ─────────────────────────────────────────────────────────────────


def time_command(command: str, audio_seconds: float) -> dict[str, Any]:
    """
    Run `command` and report how long it took per second of audio.

    Wall-clock, not CPU time: a GPU run that spends its time waiting on the
    device is genuinely that fast for the person waiting, and CPU time would
    flatter it.

    Parameters
    ----------
    command : str
        Shell-style command, split with :mod:`shlex`.
    audio_seconds : float
        Duration of the audio the command processes.

    Returns
    -------
    dict
        ``elapsed_s``, ``audio_s``, ``rtf`` (processing per audio second),
        ``speedup`` (its reciprocal) and the command's ``returncode``.
    """
    started = time.perf_counter()
    completed = subprocess.run(shlex.split(command), capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    return {
        "elapsed_s": round(elapsed, 3),
        "audio_s": audio_seconds,
        "rtf": round(elapsed / max(audio_seconds, 1e-9), 4),
        "speedup": round(max(audio_seconds, 1e-9) / max(elapsed, 1e-9), 2),
        "returncode": completed.returncode,
        "stderr_tail": completed.stderr.strip().splitlines()[-3:] if completed.stderr else [],
    }


# ── Reporting ─────────────────────────────────────────────────────────────


def format_report(results: dict[str, Any]) -> str:
    """Render `results` as the console block, numbers aligned for comparison."""
    lines: list[str] = []
    if "device" in results:
        lines.append("Hardware")
        lines.append("  " + describe_device().replace("\n", "\n  "))
        lines.append("")
    if "wer" in results:
        w = results["wer"]
        lines.append("Transcription quality")
        lines.append(f"  WER            {w['wer'] * 100:6.2f} %   (lower is better)")
        lines.append(f"  substitutions  {w['sub']:6d}")
        lines.append(f"  deletions      {w['del']:6d}     decoder gave up on a passage")
        lines.append(f"  insertions     {w['ins']:6d}     decoder invented through silence")
        lines.append(f"  reference      {w['n_ref']:6d} words")
        lines.append("")
    if "der" in results:
        d = results["der"]
        lines.append("Speaker attribution")
        lines.append(f"  DER            {d['der'] * 100:6.2f} %   (250 ms collar, optimal mapping)")
        lines.append(f"  missed         {d['missed_s']:6.1f} s")
        lines.append(f"  false alarm    {d['false_alarm_s']:6.1f} s")
        lines.append(f"  confusion      {d['confusion_s']:6.1f} s")
        lines.append(f"  speakers       {d['n_hyp_speakers']} found / {d['n_ref_speakers']} real")
        if d["n_hyp_speakers"] != d["n_ref_speakers"]:
            lines.append("                 ^ wrong count: over- or under-segmentation,")
            lines.append("                   not merely fuzzy boundaries")
        lines.append("")
    if "speed" in results:
        s = results["speed"]
        lines.append("Speed")
        lines.append(f"  elapsed        {s['elapsed_s']:6.1f} s for {s['audio_s']:.0f} s of audio")
        lines.append(f"  RTF            {s['rtf']:6.3f}     processing seconds per audio second")
        lines.append(f"  speed-up       {s['speedup']:6.2f} x  faster than real time")
        if s["returncode"] != 0:
            lines.append(f"  ⚠ command exited {s['returncode']} — the timing is of a failure")
        lines.append("")
    measured = any(k in results for k in ("wer", "der", "speed"))
    if not measured:
        lines.append("Nothing measured: pass --reference/--hypothesis or --time-command.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = make_parser(
        "benchmark_stt.py",
        "Measure transcription quality (WER), speaker attribution (DER) and speed (RTF).",
        epilog=(
            "Examples:\n"
            "  benchmark_stt.py --reference truth.vtt --hypothesis whisper.vtt\n"
            "  benchmark_stt.py --reference-rttm truth.rttm --hypothesis-rttm out.rttm\n"
            "  benchmark_stt.py --audio-seconds 3600 --time-command 'python captions_from_whisper.py a.mp4'\n"
        ),
    )
    parser.add_argument("--reference", type=Path, help="Reference transcript (.vtt, .srt or .txt).")
    parser.add_argument("--hypothesis", type=Path, help="System transcript to score.")
    parser.add_argument("--reference-rttm", type=Path, help="Reference diarization (.rttm).")
    parser.add_argument("--hypothesis-rttm", type=Path, help="System diarization to score.")
    parser.add_argument("--no-collar", action="store_true", help="Score DER without the 250 ms collar.")
    parser.add_argument("--time-command", help="Command to run and time.")
    parser.add_argument("--audio-seconds", type=float, help="Audio duration, for the real-time factor.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of the console report.")
    args = parser.parse_args(argv)

    results: dict[str, Any] = {}
    # Recorded on every run, not only timed ones: a WER is reproducible only
    # if the model and the hardware that produced it are written down beside
    # it, and a silent CPU fallback is invisible in the number itself.
    results["device"] = device_report()

    if bool(args.reference) != bool(args.hypothesis):
        parser.error("--reference and --hypothesis go together.")
    if bool(args.reference_rttm) != bool(args.hypothesis_rttm):
        parser.error("--reference-rttm and --hypothesis-rttm go together.")
    if args.time_command and not args.audio_seconds:
        parser.error("--time-command needs --audio-seconds to compute a real-time factor.")

    if args.reference:
        results["wer"] = word_error_rate(
            read_transcript(args.reference), read_transcript(args.hypothesis)
        )
    if args.reference_rttm:
        results["der"] = diarization_error_rate(
            read_rttm(args.reference_rttm),
            read_rttm(args.hypothesis_rttm),
            collar=not args.no_collar,
        )
    if args.time_command:
        results["speed"] = time_command(args.time_command, args.audio_seconds)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(format_report(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
