"""
A model download that restarts from zero is a download that never finishes.

``install_narrate._download`` goes through ``os_helper.download_file`` so a
dropped connection resumes with an HTTP ``Range`` request instead of fetching
the 325 MB Kokoro graph again. The call carries three arguments a later
tidy-up would delete for looking redundant, and this file is what says each
one was a finding rather than a habit.

``check_url=False`` is the one that looks worst. ``download_file``'s
precondition is ``os_helper.is_working_url``, which probes with
``requests.head`` — whose default is ``allow_redirects=False`` — and a GitHub
release asset answers 302 towards the CDN. Measured on 2026-10-31:
``is_working_url`` returns **False** for both ``kokoro-v1.0.onnx`` and
``voices-v1.0.bin``, while a followed HEAD on each returns 200 with the right
``Content-Length``. With the precondition on, the installer asserts away the
only two downloads that work.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import builtins
import sys
import types
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_the_download_resumes_rather_than_restarting(monkeypatch, tmp_path) -> None:
    """``_download`` hands the job to the suite's resumable primitive.

    Asserted on the call rather than on the bytes: a real transfer would need
    the network and 325 MB. What matters here is that the four arguments the
    measurement chose are still being passed.

    ``os_helper`` is **substituted into** ``sys.modules`` rather than imported
    and patched, and the difference is not stylistic. What is under test here
    is what *this* code asks for, which is true whether or not the helper is
    installed — and this package's CI installs ``[api,mcp]`` and no helper at
    all. The first version of this test did ``import os_helper`` to patch it,
    passed on a laptop, and failed in CI with ``ModuleNotFoundError`` on the
    one environment that installs nothing extra. Skipping there instead would
    have been the same silence: the three measured arguments are exactly what
    nothing else would notice going missing.
    """
    import install_narrate

    seen: dict[str, Any] = {}

    def fake_download_file(url: str, file_path: str = "", **kwargs: Any) -> dict[str, Any]:
        seen["url"] = url
        seen["file_path"] = file_path
        seen.update(kwargs)
        Path(file_path).write_bytes(b"weights")
        return {"path": file_path, "bytes": 7, "resumed": False}

    stub = types.ModuleType("os_helper")
    stub.download_file = fake_download_file  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "os_helper", stub)

    dest = tmp_path / "models" / "kokoro-v1.0.onnx"
    install_narrate._download("https://example.invalid/kokoro-v1.0.onnx", dest)

    assert dest.read_bytes() == b"weights"
    assert seen["url"] == "https://example.invalid/kokoro-v1.0.onnx"
    assert seen["file_path"] == str(dest)
    # Resume is the whole reason for the substitution.
    assert seen["resume"] is True
    assert seen["retries"] >= 1
    # is_working_url says False for both real model URLs — see the module
    # docstring. The precondition has to stay off.
    assert seen["check_url"] is False
    # install_kokoro calls _download precisely when the file on disk is the
    # wrong size; the idempotent fast path would hand that wrong file back.
    assert seen["overwrite"] is True


def test_the_download_names_the_extra_when_the_helper_is_missing(monkeypatch, tmp_path) -> None:
    """A missing os-helper has to read as an install line, not an ImportError."""
    import install_narrate

    real_import = builtins.__import__

    def refuse_os_helper(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "os_helper":
            raise ImportError("no os_helper for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse_os_helper)

    with pytest.raises(RuntimeError) as caught:
        install_narrate._download("https://example.invalid/x.bin", tmp_path / "x.bin")
    assert "sprezzature-audio[narrate]" in str(caught.value)
