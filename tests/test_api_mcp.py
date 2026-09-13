"""
Tests for the HTTP and MCP surfaces.

The metrics and renderers are covered by ``test_audio.py`` /
``test_scripts.py``; these guard the wiring, and one regression in
particular — see :func:`test_plain_captions_convert_without_a_speaker`.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sprezzature_audio.api import app  # noqa: E402

client = TestClient(app)

VTT = (
    "WEBVTT\n\n"
    "00:00:00.000 --> 00:00:03.000\nBonjour a tous\n\n"
    "00:00:03.000 --> 00:00:07.000\nParlons du budget\n"
)


def test_health() -> None:
    """The liveness probe answers."""
    assert client.get("/health").json() == {"status": "ok"}


def test_device_is_reported() -> None:
    """
    Every measurement carries its hardware.

    A GPU fallback is silent: a run that quietly drops to the CPU looks
    exactly like one that did not, only slower. A WER with no device beside
    it is not reproducible.
    """
    body = client.get("/v1/device").json()
    assert "whisper_backend" in body["device"]
    assert "threads" in body["device"]
    assert body["summary"]


def test_plain_captions_convert_without_a_speaker() -> None:
    """
    Captions that never went through attribution must still convert.

    The three renderers indexed ``cue["speaker"]`` directly, so converting
    plain captions raised KeyError and returned a 500 for a perfectly valid
    request. The command line never hit it because it always merges first.
    """
    for fmt in ("srt", "vtt", "text"):
        response = client.post("/v1/captions/convert", json={"captions": VTT, "to": fmt})
        assert response.status_code == 200, f"{fmt}: {response.text[:120]}"
        assert "Bonjour" in response.text


def test_merge_attaches_names() -> None:
    """Turns plus a name map produce attributed captions."""
    body = {
        "captions": VTT,
        "turns": [
            {"speaker": "spk0", "start": 0, "end": 3},
            {"speaker": "spk1", "start": 3, "end": 7},
        ],
        "speaker_names": {"spk0": "Alice", "spk1": "Bob"},
        "to": "text",
    }
    text = client.post("/v1/captions/merge", json=body).text
    assert "Alice" in text and "Bob" in text


def test_unparseable_captions_are_a_400() -> None:
    """Empty output for bad input would read as 'no captions found'."""
    assert client.post(
        "/v1/captions/convert", json={"captions": "not a vtt file", "to": "srt"}
    ).status_code == 400


def test_wer_counts_one_substitution() -> None:
    """A single changed word is one substitution, not a rewrite."""
    body = {"reference": VTT, "hypothesis": VTT.replace("budget", "budgets")}
    wer = client.post("/v1/metrics/wer", json=body).json()["wer"]
    assert wer["sub"] == 1
    assert wer["del"] == 0 and wer["ins"] == 0


def test_identical_transcripts_score_zero() -> None:
    """A metric that never returns 0 is not measuring what it claims."""
    body = {"reference": VTT, "hypothesis": VTT}
    assert client.post("/v1/metrics/wer", json=body).json()["wer"]["wer"] == 0.0


def test_der_ignores_speaker_naming() -> None:
    """
    Labels are arbitrary in diarization; only the partition matters.

    A system that segments perfectly but calls the speakers spk0/spk1 has
    made no error, and the optimal-permutation search is what says so.
    """
    body = {
        "reference": [
            {"speaker": "Alice", "start": 0, "end": 10},
            {"speaker": "Bob", "start": 10, "end": 20},
        ],
        "hypothesis": [
            {"speaker": "s0", "start": 0, "end": 10},
            {"speaker": "s1", "start": 10, "end": 20},
        ],
    }
    result = client.post("/v1/metrics/der", json=body).json()["der"]
    assert result["der"] == 0.0
    assert result["mapping"] == {"s0": "Alice", "s1": "Bob"}


def test_der_punishes_a_genuinely_bad_split() -> None:
    """Everything on one speaker must not score zero."""
    body = {
        "reference": [
            {"speaker": "Alice", "start": 0, "end": 10},
            {"speaker": "Bob", "start": 10, "end": 20},
        ],
        "hypothesis": [{"speaker": "s0", "start": 0, "end": 20}],
    }
    assert client.post("/v1/metrics/der", json=body).json()["der"]["der"] > 0.2


def test_transcription_is_not_exposed() -> None:
    """
    No route runs Whisper.

    It loads gigabytes and runs for minutes; behind a synchronous endpoint
    that is a timeout, and behind an unauthenticated one it is a way to make
    somebody else's GPU do your work. It belongs behind a job queue.
    """
    # The API SURFACE, not the prose. Scanning the whole schema blob used to
    # work, until the tool descriptions started saying what each tool is NOT
    # -- `convert_captions` telling an agent it "does not transcribe audio"
    # is exactly the guidance we want, and it tripped a substring scan.
    schema = client.get("/openapi.json").json()
    surface = [p.lower() for p in schema["paths"]]
    surface += [
        op.get("operationId", "").lower()
        for methods in schema["paths"].values()
        for op in methods.values()
    ]
    surface += [name.lower() for name in schema.get("components", {}).get("schemas", {})]
    for forbidden in ("transcribe", "whisper", "asr"):
        offenders = [entry for entry in surface if forbidden in entry]
        assert not offenders, f"{forbidden!r} names a route or schema: {offenders}"


def test_openapi_names_every_tool() -> None:
    """Each route carries an operation_id: that *is* the MCP tool name."""
    paths = client.get("/openapi.json").json()["paths"]
    for path, methods in paths.items():
        for verb, spec in methods.items():
            assert "operationId" in spec, f"{verb.upper()} {path} has no operation_id"


def test_mcp_mounts_and_publishes_the_tools() -> None:
    """The MCP endpoint exists and carries the expected tool names."""
    pytest.importorskip("fastapi_mcp")
    from sprezzature_audio.mcp import mcp

    assert mcp is not None
    mounted = {getattr(r, "path", "") for r in app.routes}
    assert any(p.startswith("/mcp") for p in mounted), sorted(mounted)
    names = {t.name for t in mcp.tools}
    for expected in ("measure_wer", "measure_der", "convert_captions"):
        assert expected in names, f"{expected} missing from {sorted(names)}"


def _documented_routes(app):
    """This package's own tools -- fastapi-mcp mounts its transport route on
    the same app, and that one is not ours to document."""
    return [
        route
        for route in app.routes
        if getattr(route, "operation_id", None)
        and not getattr(route, "path", "").startswith("/mcp")
    ]


def test_every_tool_has_a_written_summary() -> None:
    """The first line an MCP host shows is FastAPI's `summary`, and its
    default is the function name title-cased: `cvd` became "Cvd", `wer`
    became "Wer". An agent choosing between tools from several servers reads
    those headlines and little else, so each has to be a written phrase
    saying what the tool does -- not a restatement of the Python identifier.
    """
    from sprezzature_audio.api import app

    for route in _documented_routes(app):
        summary = (getattr(route, "summary", "") or "").strip()
        assert summary, f"{route.operation_id}: no summary, so the headline is a function name"
        derived = getattr(route, "name", "").replace("_", " ").title()
        assert summary != derived, (
            f"{route.operation_id}: summary {summary!r} is FastAPI's default (the "
            f"function name title-cased). Write one that says what the tool does."
        )
        assert " " in summary and len(summary) > 15, (
            f"{route.operation_id}: summary {summary!r} is too terse to route on."
        )


def test_every_tool_says_when_to_call_it() -> None:
    """A description that only restates the summary does not help an agent
    choose. Each route's docstring carries the deciding context: when to
    reach for it, what it needs first, or what it must not be used for.
    """
    from sprezzature_audio.api import app

    for route in _documented_routes(app):
        description = (getattr(route, "description", "") or "").strip()
        assert len(description) > 120, (
            f"{route.operation_id}: description is {len(description)} chars. Say when "
            f"to call it, not just what it is."
        )
