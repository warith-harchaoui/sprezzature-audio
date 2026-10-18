"""
Shared pytest configuration.

Two jobs, and the second is the one with teeth.

1. **Import path.** ``scripts/`` goes on ``sys.path`` so test modules can
   ``import captions_from_whisper`` directly, mirroring how the scripts
   import each other at run time. Several test files also insert it
   themselves, which was the only way before this file existed; the
   duplication is harmless and left alone.
2. **Keeping the content-safety scan out of unit tests that mock the
   transport** — see :func:`no_content_scan`.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    """Redirect the on-disk cache to a per-test temp directory."""
    monkeypatch.setenv("SPREZZATURE_CACHE_DIR", str(tmp_path / "sprezzature-skill"))
    monkeypatch.delenv("SPREZZATURE_NO_CACHE", raising=False)


@pytest.fixture(autouse=True)
def no_content_scan(monkeypatch):
    """
    Keep the content-safety scan out of unit tests that mock the transport.

    The model-backed tools here — the translator, the speaker namer, and now
    the two voices — call ``best_engine_ai_helper.llm.chat``, which since 1.4
    scans every prompt and response through an NSFW classifier before the
    request leaves. The classifier is an optional extra, so a bare install
    falls back to a keyword heuristic and nothing happens.

    But on a machine where ``transformers`` is installed for some other
    reason, the scan loads a 270 MB model from HuggingFace, and these tests go
    from "the model call is mocked" to "the suite downloads a model and needs
    the network". Measured elsewhere in this suite: 19.1 s instead of 1.1 s,
    and a CI job failing for a reason nothing here caused.
    """
    try:
        from best_engine_ai_helper import safety
    except ImportError:  # the dependency is absent — nothing to neutralise
        return
    for name in ("check_text", "check_image"):
        if hasattr(safety, name):
            monkeypatch.setattr(safety, name, lambda *a, **k: None)
