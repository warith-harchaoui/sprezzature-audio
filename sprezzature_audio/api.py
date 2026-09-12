"""
sprezzature-audio: the FastAPI HTTP surface.

Module summary
--------------
Exposes the parts of the speech pipeline that are *fast and pure*: caption
format conversion, speaker attribution, and the quality metrics. Every
route calls the same functions the command lines call, so an HTTP answer
and a terminal answer cannot disagree.

What is deliberately not here: transcription
---------------------------------------------
``captions_from_whisper`` loads a multi-gigabyte model and runs for minutes
on a long recording. Behind a synchronous HTTP route that is a timeout with
extra steps, and behind an unauthenticated one it is a way to make somebody
else's GPU do your work. Transcription belongs behind a job queue with a
result endpoint, which is a different piece of software; until that exists,
the command line is the honest interface for it.

What ships here
---------------
- ``GET  /health``: a liveness probe.
- ``GET  /v1/device``: which accelerator this host will actually use.
- ``POST /v1/captions/convert``: VTT ↔ SRT ↔ plain text.
- ``POST /v1/captions/merge``: captions + speaker turns → attributed captions.
- ``POST /v1/metrics/wer``: word error rate between two transcripts.
- ``POST /v1/metrics/der``: diarization error rate between two RTTMs.

Why ``/v1/device`` earns its place
-----------------------------------
A GPU fallback is silent: a run that quietly drops to the CPU looks exactly
like one that did not, only slower. Every speed number this project reports
carries the device that produced it, and this route is how a remote caller
gets that same answer before trusting a benchmark.

Install the extra to get the runtime dependencies::

    pip install 'sprezzature-audio[api]'

Then run the app with any ASGI server::

    uvicorn sprezzature_audio.api:app --host 0.0.0.0 --port 8000

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import PlainTextResponse, RedirectResponse
except ImportError as exc:  # pragma: no cover - dependency guard
    raise ImportError(
        "The FastAPI HTTP surface requires the [api] extra. "
        "Install with: pip install 'sprezzature-audio[api]'"
    ) from exc

from pydantic import BaseModel, Field

# The pipeline lives in the scripts package, which is where the command
# lines reach it too; importing rather than re-implementing is the point.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _device import describe as describe_device  # noqa: E402
from _device import report as device_report  # noqa: E402
from benchmark_stt import (  # noqa: E402
    diarization_error_rate,
    normalise_words,
    word_error_rate,
)
from caption_diarize import (  # noqa: E402
    attribute_speakers,
    parse_caption_cues,
    render_srt,
    render_text,
    render_vtt,
)

from . import __version__ as _VERSION  # noqa: E402

app = FastAPI(
    title="Sprezzature Audio API",
    description=(
        "HTTP surface for sprezzature-audio: caption conversion, speaker "
        "attribution, and the WER/DER quality metrics. Transcription itself "
        "stays on the command line — it is a minutes-long job, not a request."
    ),
    version=_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

_RENDERERS = {"vtt": render_vtt, "srt": render_srt, "text": render_text}


class ConvertRequest(BaseModel):
    """Body for ``POST /v1/captions/convert``."""

    captions: str = Field(description="A WebVTT or SRT document. The format is detected.")
    to: Literal["vtt", "srt", "text"] = Field(default="srt", description="Output format.")


class MergeRequest(BaseModel):
    """Body for ``POST /v1/captions/merge``."""

    captions: str = Field(description="A WebVTT or SRT document.")
    turns: list[dict[str, Any]] = Field(
        description='Speaker turns: [{"speaker": "spk0", "start": 0.0, "end": 12.4}, ...].'
    )
    speaker_names: dict[str, str] | None = Field(
        default=None, description='Optional label → real name map, e.g. {"spk0": "Alice"}.'
    )
    to: Literal["vtt", "srt", "text"] = Field(default="vtt", description="Output format.")


class WerRequest(BaseModel):
    """Body for ``POST /v1/metrics/wer``."""

    reference: str = Field(description="Ground-truth transcript: VTT, SRT, or plain text.")
    hypothesis: str = Field(description="System transcript, same accepted formats.")


class Segment(BaseModel):
    """One speaker segment for DER scoring."""

    speaker: str = Field(description="Speaker label. Names need not match across the two sets.")
    start: float = Field(ge=0, description="Onset in seconds.")
    end: float = Field(gt=0, description="End in seconds.")


class DerRequest(BaseModel):
    """Body for ``POST /v1/metrics/der``."""

    reference: list[Segment] = Field(description="Ground-truth speaker segments.")
    hypothesis: list[Segment] = Field(description="System speaker segments.")
    collar: bool = Field(
        default=True,
        description="Apply the standard 250 ms forgiveness collar around reference boundaries.",
    )


def _cues_or_400(text: str) -> list[dict[str, Any]]:
    """
    Parse captions, or explain why they could not be parsed.

    Returning an empty list for unparseable input would let a caller think
    their file had no captions rather than the wrong shape — the failure
    mode this whole project keeps running into.

    Parameters
    ----------
    text : str
        A VTT or SRT document.

    Returns
    -------
    list of dict
        The parsed cues.

    Raises
    ------
    fastapi.HTTPException
        400 when nothing parsed.
    """
    cues = parse_caption_cues(text)
    if not cues:
        raise HTTPException(
            status_code=400,
            detail="no cues parsed — is this a WebVTT or SRT document?",
        )
    return cues


@app.get("/health", tags=["meta"], operation_id="health")
def health() -> dict:
    """
    Liveness probe — no dependency check, just proves the app is up.

    Returns
    -------
    dict
        ``{"status": "ok"}``.
    """
    return {"status": "ok"}


@app.get("/v1/device", tags=["meta"], operation_id="get_device")
def device() -> dict:
    """
    Which accelerator this host will actually use, probed rather than assumed.

    Returns
    -------
    dict
        The machine-readable report plus a one-line human summary.
    """
    return {"device": device_report(), "summary": describe_device()}


@app.post("/v1/captions/convert", tags=["captions"], operation_id="convert_captions",
          response_class=PlainTextResponse)
def convert(request: ConvertRequest) -> PlainTextResponse:
    """
    Convert captions between WebVTT, SRT and plain text.

    Parameters
    ----------
    request : ConvertRequest
        The document and the format wanted.

    Returns
    -------
    fastapi.responses.PlainTextResponse
        The converted document.
    """
    return PlainTextResponse(_RENDERERS[request.to](_cues_or_400(request.captions)))


@app.post("/v1/captions/merge", tags=["captions"], operation_id="merge_speakers",
          response_class=PlainTextResponse)
def merge(request: MergeRequest) -> PlainTextResponse:
    """
    Attach speaker labels to captions, from a set of diarization turns.

    Parameters
    ----------
    request : MergeRequest
        Captions, turns, and an optional label → name map.

    Returns
    -------
    fastapi.responses.PlainTextResponse
        The attributed captions in the requested format.
    """
    attributed = attribute_speakers(
        _cues_or_400(request.captions), request.turns, request.speaker_names
    )
    return PlainTextResponse(_RENDERERS[request.to](attributed))


@app.post("/v1/metrics/wer", tags=["metrics"], operation_id="measure_wer")
def wer(request: WerRequest) -> dict:
    """
    Word error rate between a reference and a hypothesis transcript.

    Reports the substitution / deletion / insertion split, because the three
    fail differently: deletions mean the decoder gave up on a passage,
    insertions mean it invented through silence, and substitutions are
    ordinary mishearing.

    Parameters
    ----------
    request : WerRequest
        The two transcripts.

    Returns
    -------
    dict
        ``wer`` (0.0 is perfect), the edit counts, and the device the
        measurement ran on.
    """
    def tokens(text: str) -> list[str]:
        cues = parse_caption_cues(text)
        if cues:
            return [w for c in cues for w in normalise_words(str(c["text"]))]
        return normalise_words(text)

    return {
        "wer": word_error_rate(tokens(request.reference), tokens(request.hypothesis)),
        "device": device_report(),
    }


@app.post("/v1/metrics/der", tags=["metrics"], operation_id="measure_der")
def der(request: DerRequest) -> dict:
    """
    Diarization error rate between two sets of speaker segments.

    Speaker labels need not match between the two sets: the best permutation
    is found and reported, because a system that segments perfectly and names
    the speakers differently has made no error at all.

    Parameters
    ----------
    request : DerRequest
        Reference and hypothesis segments, and whether to apply the collar.

    Returns
    -------
    dict
        ``der`` plus the three error durations, and the winning label mapping.

    Raises
    ------
    fastapi.HTTPException
        400 when either set is empty, or the hypothesis names more speakers
        than the permutation search can enumerate.
    """
    if not request.reference or not request.hypothesis:
        raise HTTPException(status_code=400, detail="both segment sets must be non-empty")
    to_tuples = lambda rows: [(s.speaker, s.start, s.end) for s in rows]  # noqa: E731
    try:
        result = diarization_error_rate(
            to_tuples(request.reference), to_tuples(request.hypothesis),
            collar=request.collar,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"der": result, "device": device_report()}


@app.get("/docs-redirect", include_in_schema=False)
def docs_redirect() -> RedirectResponse:
    """Convenience redirect to the interactive API docs."""
    return RedirectResponse(url="/docs")
