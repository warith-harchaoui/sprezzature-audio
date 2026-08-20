#!/usr/bin/env python3
"""
install_captions
================

A one-command installer, working the same way on macOS, Linux, and
Windows, that gets everything `captions_from_whisper.py` needs ready
*before* the first real transcription is attempted, so that first run is
not slowed down by an unexpected download.

It relies on **vocal-helper** (this project author's own wrapper around
whisper.cpp, described in `captions_from_whisper.py`'s own docstring),
which in turn pulls in **pywhispercpp**: that package ships as "wheels,"
Python's name for a pre-built, ready-to-install package file, with
separate wheels already compiled for macOS, Linux, and Windows, so
nothing needs to compile from source on the user's machine.
`captions_from_whisper.py` drives ``vocal-helper``'s ``WhisperStage`` to
do the actual transcription; this installer's job is only to make sure
that engine, and its model weights, are already in place beforehand.

The script does two things:

1. Checks whether the ``vocal-helper`` package (a specific, pinned
   version from PyPI, Python's public package index) is already
   installed. If ``import vocal_helper`` fails, it installs the package
   into the current Python environment; ``pywhispercpp`` comes along
   automatically as one of its dependencies.
2. Downloads the requested model weights ahead of time, in GGML format
   (the compact file format whisper.cpp reads), into
   ``~/.cache/sprezzature-skill/whisper/``, using ``pywhispercpp.utils``.
   Doing this now means the first real transcription later does not have
   to wait on a model download. The default model is ``large-v3-turbo``.

Usage
-----
::

    python install_captions.py                          # default: large-v3-turbo
    python install_captions.py --model small            # smaller / faster

Notes
-----
* Python 3.10+. The installer itself is stdlib + pip.
* ``pywhispercpp.utils.download_model`` (available via vocal-helper's
  ``pywhispercpp`` dependency) is the canonical way to pre-fetch weights;
  pointing the generator at a local file with ``SPREZZATURE_WHISPER_MODEL=<path>``
  is also supported.
* Audio extraction (video → WAV) is handled by the generator, not the
  installer; install ``ffmpeg`` or the author's audio-helper /
  video-helper packages separately if needed.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path as _PathHelper

sys.path.insert(0, str(_PathHelper(__file__).resolve().parent))
from pathlib import Path

from _argparse import make_parser  # noqa: E402

#: Where the GGML weights are cached. Override the parent dir via
#: ``SPREZZATURE_CACHE_DIR``; the trailing ``whisper`` subfolder is fixed so
#: every helper agrees on the lookup path.
WHISPER_DIR: Path = (
    Path(
        os.environ.get("SPREZZATURE_CACHE_DIR")
        or os.environ.get("FRONT_CACHE_DIR")
        or Path.home() / ".cache" / "sprezzature-skill"
    )
    / "whisper"
)

#: Aliases that pywhispercpp understands directly via the model registry.
SUPPORTED_MODELS: tuple[str, ...] = (
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large-v1",
    "large-v2",
    "large-v3",
    "large-v3-turbo",
)

#: Default when no ``--model`` flag is provided.
DEFAULT_MODEL: str = "large-v3-turbo"


#: Import name of the captions STT engine and its pinned pip install spec.
#: ``vocal-helper`` is published on PyPI; its base install declares
#: ``pywhispercpp`` (+ ``silero-vad`` / ``audio-helper`` / ``os-helper``) as
#: dependencies, so this one install provides both the engine and the
#: ``pywhispercpp.utils.download_model`` used below, with no extras needed.
CAPTIONS_ENGINE_IMPORT: str = "vocal_helper"
CAPTIONS_ENGINE_SPEC: str = "vocal-helper>=0.6.0"


# ── captions engine install (vocal-helper → pywhispercpp) ─────────────────


def _is_installed(pkg: str) -> bool:
    """
    Return ``True`` when ``pkg`` is importable in the active interpreter.

    Uses :func:`importlib.util.find_spec` so the check has no side effects:
    nothing is actually imported, no exception is swallowed.

    Parameters
    ----------
    pkg : str
        Top-level package name to probe.

    Returns
    -------
    bool
        ``True`` when ``find_spec`` resolves to a real spec.
    """
    return importlib.util.find_spec(pkg) is not None


def ensure_captions_engine() -> None:
    """
    Install ``vocal-helper`` (the whisper.cpp over-layer) if it is missing.

    Calls ``pip install`` with the pinned PyPI spec in the current
    interpreter when :func:`_is_installed` reports ``vocal_helper`` missing.
    ``pywhispercpp`` (pre-compiled wheels for the three major desktop
    platforms) is pulled in as a dependency, so the STT engine and the
    ``pywhispercpp.utils.download_model`` used by :func:`download_model`
    both land in one step.

    Raises
    ------
    SystemExit
        When ``pip`` is unavailable, the install command exits
        non-zero, or the post-install check still cannot find the package.
    """
    if _is_installed(CAPTIONS_ENGINE_IMPORT):
        print("→ vocal-helper already installed.")
        return

    print("→ Installing vocal-helper (whisper.cpp over-layer) via pip…")
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", CAPTIONS_ENGINE_SPEC],
    )
    if proc.returncode != 0:
        sys.exit(
            f"pip install vocal-helper failed (exit {proc.returncode}).\n"
            "Make sure pip and git are available in this Python environment "
            "and try again."
        )
    # Post-install probe: fail fast if pip reported success but the
    # package is not on the active import path.
    if not _is_installed(CAPTIONS_ENGINE_IMPORT):
        sys.exit(
            "vocal-helper installed by pip but cannot be located in the "
            "active interpreter's import path. Check virtualenv / PYTHONPATH."
        )


# ── Model download ───────────────────────────────────────────────────────


def download_model(name: str) -> Path:
    """
    Pre-fetch the requested GGML model file into :data:`WHISPER_DIR`.

    Delegates to ``pywhispercpp.utils.download_model`` which handles the
    Hugging Face mirror, checksum validation, and resume-on-interruption.

    Parameters
    ----------
    name : str
        Model alias from :data:`SUPPORTED_MODELS`.

    Returns
    -------
    Path
        Local path to the downloaded GGML weights.

    Raises
    ------
    SystemExit
        On unknown model or download failure.
    """
    if name not in SUPPORTED_MODELS:
        sys.exit(f"Unknown model: {name}. Known: {', '.join(SUPPORTED_MODELS)}.")

    WHISPER_DIR.mkdir(parents=True, exist_ok=True)

    # ``download_model`` exists in pywhispercpp >= 1.x. The function takes
    # (model_name, download_dir) and returns the absolute path to the file.
    from pywhispercpp.utils import download_model as _download_model

    print(f"→ Pre-downloading model `{name}` into {WHISPER_DIR}…")
    try:
        path: str = _download_model(name, str(WHISPER_DIR))
    except Exception as e:
        sys.exit(f"Model download failed: {e}")

    file_path = Path(path)
    size_mb: int = file_path.stat().st_size // (1024 * 1024)
    print(f"→ Wrote {file_path} ({size_mb} MB).")
    return file_path


# ── CLI entry point ─────────────────────────────────────────────────────


def main() -> int:
    """Run the pip-install + model-prefetch pipeline."""
    p = make_parser(
        prog="sprezzature-audio-install",
        description="Install vocal-helper (whisper.cpp over-layer) and "
        "pre-download a GGML caption model so `sprezzature-audio-captions` "
        "runs offline.",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=list(SUPPORTED_MODELS),
        help=f"Model alias to pre-download (default: {DEFAULT_MODEL}).",
    )
    args = p.parse_args()

    ensure_captions_engine()
    download_model(args.model)
    print()
    print("→ Ready. Test with:")
    print("    python scripts/captions_from_whisper.py path/to/audio-or-video")
    return 0


if __name__ == "__main__":
    sys.exit(main())
