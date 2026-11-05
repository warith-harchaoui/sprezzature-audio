"""
The server ``--url`` names is the server the model call reaches.

``translate`` and ``name`` probe ``--url`` (default ``OLLAMA_URL``) before
calling a model. Until 2026-11-05 the call itself went through
``best_engine_ai_helper.llm.chat`` with no endpoint, so it reached whatever
best-engine-ai-helper was configured with (``SPREZZATURE_LLM_BASE_URL``,
default localhost) -- a probe that gated a call it never reached. In the
compose stack that meant the probe passed against the ``ollama`` service and
the translation went to localhost, inside the API container, and failed.

These tests replace ``chat`` with a stub that records its arguments, so they
need no server and no model, and assert the probed URL is in the call.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any

import pytest

URL = "http://ollama.example:11434"
MODEL = "qwen3-vl:8b"


def _stub_chat(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[dict[str, Any]]:
    """Put a recording ``chat`` where both modules import it from.

    A stand-in module rather than a patched attribute, so the test does not
    depend on best-engine-ai-helper being importable, and cannot reach a real
    server if it is.
    """
    calls: list[dict[str, Any]] = []

    def chat(prompt: str, **kwargs: Any) -> str:
        calls.append({"prompt": prompt, **kwargs})
        return reply

    package = types.ModuleType("best_engine_ai_helper")
    llm = types.ModuleType("best_engine_ai_helper.llm")
    llm.chat = chat  # type: ignore[attr-defined]
    package.llm = llm  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "best_engine_ai_helper", package)
    monkeypatch.setitem(sys.modules, "best_engine_ai_helper.llm", llm)
    return calls


def _assert_reaches(call: dict[str, Any]) -> None:
    engine = call.get("engine")
    assert isinstance(engine, dict), (
        "chat() was called without an engine descriptor, so it goes to "
        "best-engine-ai-helper's own endpoint and not to the --url just probed"
    )
    assert engine["backend"] == "ollama"
    assert engine["base_url"] == URL
    assert engine["llm"]["model"] == MODEL
    assert call["model"] == MODEL


def test_the_translator_calls_the_url_it_was_given(monkeypatch: pytest.MonkeyPatch) -> None:
    import translate_captions

    calls = _stub_chat(monkeypatch, json.dumps({"1": "Bonjour.", "2": "Merci."}))
    translate = translate_captions.make_ollama_translator(
        url=URL, model=MODEL, source_lang="en", target_lang="fr"
    )
    assert translate(["Hello.", "Thank you."]) == ["Bonjour.", "Merci."]
    assert len(calls) == 1
    _assert_reaches(calls[0])


def test_the_name_guesser_calls_the_url_it_was_given(monkeypatch: pytest.MonkeyPatch) -> None:
    import name_from_transcript

    calls = _stub_chat(monkeypatch, json.dumps({"0": "Alice"}))
    cues = [{"start": 0.0, "end": 2.0, "text": "Hi, I'm Alice.", "speaker_id": "0"}]
    name_from_transcript._llm_pass(cues, url=URL, model=MODEL, seed_names={})
    assert len(calls) == 1
    _assert_reaches(calls[0])
