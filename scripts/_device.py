"""
_device: find the fastest accelerator available, and say which one it is.

Why a whole module for this
---------------------------
The house rule is to use the GPU whenever there is one. The trouble with
that rule is that a GPU fallback is *silent*: a run that quietly drops to
the CPU looks exactly like a run that did not, only slower, and "slower"
is invisible unless you happened to time the fast one first. Every speed
number in this repository is meaningless without the device that produced
it, so the two are reported together, always.

What "GPU" means per backend
----------------------------
The two engines reach the hardware differently, and neither of them tells
you which it picked unless asked:

**whisper.cpp** (ASR, via ``vocal-helper`` → ``pywhispercpp``)
    Built with Metal on Apple silicon and with CUDA when compiled for it;
    ``use_gpu`` defaults to on. It does *not* announce the choice, so
    :func:`whisper_backend` probes the loaded binary instead of trusting
    the default. Its CPU thread count still matters even on GPU, for the
    mel front-end.

**torch** (NeMo diarization and speaker ID)
    ``cuda`` → ``mps`` → ``cpu``, which
    :func:`sprezzature_audio_scripts.diarize_from_nemo.pick_device`
    already implements; :func:`torch_device` is the same order, kept here
    so a caller that has no torch installed can still ask.

On thread counts
----------------
Apple silicon has two kinds of core, and handing whisper.cpp the *logical*
count is actively harmful: the efficiency cores run several times slower,
and whisper.cpp splits work evenly, so every batch waits on the slowest
thread. :func:`compute_threads` counts performance cores only. On a
uniform CPU it returns the core count, less one thread left for the
operating system so a long transcription does not make the machine
unusable.

Usage
-----
::

    from _device import describe, compute_threads

    print(describe())        # "Metal (Apple GPU) · 8 performance threads"
    stage = WhisperStage(model=..., threads=compute_threads())

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import os
import platform
import subprocess
from functools import lru_cache
from typing import Any, Dict


@lru_cache(maxsize=1)
def performance_cores() -> int:
    """
    Number of *fast* cores, not logical processors.

    On Apple silicon ``hw.perflevel0.logicalcpu`` is the performance
    cluster; the efficiency cluster is ``perflevel1`` and is deliberately
    excluded. On every other platform this is ``os.cpu_count()``, since
    there is no asymmetry to correct for.

    Returns
    -------
    int
        At least 1.
    """
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            out = subprocess.run(
                ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            count = int(out.stdout.strip())
            if count > 0:
                return count
        except (ValueError, OSError, subprocess.SubprocessError):
            pass  # fall through to the portable count
    return max(1, os.cpu_count() or 1)


def compute_threads(reserve: int = 0) -> int:
    """
    Thread count to hand a CPU-bound stage.

    Parameters
    ----------
    reserve : int, optional
        Threads to leave free for everything else. Defaults to 0 on an
        asymmetric CPU (the efficiency cores are already the reserve) and
        is worth setting to 1 on a uniform one.

    Returns
    -------
    int
        At least 1.
    """
    return max(1, performance_cores() - max(0, reserve))


@lru_cache(maxsize=1)
def whisper_backend() -> str:
    """
    Which accelerator the installed whisper.cpp will actually use.

    Probes rather than assumes: the answer depends on how the wheel was
    compiled, not on what the machine could support, and a CUDA-capable
    box running a CPU-only build is exactly the silent-fallback case this
    module exists to expose.

    Returns
    -------
    str
        ``"metal"``, ``"cuda"``, ``"cpu"``, or ``"unavailable"`` when
        pywhispercpp is not installed at all.
    """
    try:
        import pywhispercpp.constants  # noqa: F401
    except ImportError:
        return "unavailable"

    # ggml reports its chosen backend on stderr when a context is created.
    # Cheaper and more honest than reading build flags, which can disagree
    # with what the runtime actually managed to initialise.
    probe = (
        "import numpy as np;"
        "from pywhispercpp.model import Model;"
        "m = Model('tiny', redirect_whispercpp_logs_to=None);"
        "m.transcribe(np.zeros(1600, dtype=np.float32))"
    )
    try:
        out = subprocess.run(
            ["python3", "-c", probe], capture_output=True, text=True, timeout=180
        )
    except (OSError, subprocess.SubprocessError):
        return "cpu"
    noise = (out.stderr + out.stdout).lower()
    if "metal" in noise:
        return "metal"
    if "cuda" in noise or "cublas" in noise:
        return "cuda"
    return "cpu"


def torch_device(explicit: str = "") -> str:
    """
    Best torch device available: ``cuda`` → ``mps`` → ``cpu``.

    Parameters
    ----------
    explicit : str, optional
        A user-supplied device; returned unchanged when non-empty, so a
        ``--device`` flag always wins over auto-detection.

    Returns
    -------
    str
        ``"cuda"``, ``"mps"``, ``"cpu"``, or ``"unavailable"`` without torch.
    """
    if explicit:
        return explicit
    try:
        import torch
    except ImportError:
        return "unavailable"
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def report() -> Dict[str, Any]:
    """
    Everything a benchmark line needs to be reproducible.

    Returns
    -------
    dict
        Platform, both backends' chosen accelerators, and the thread count.
    """
    return {
        "platform": f"{platform.system()} {platform.machine()}",
        "whisper_backend": whisper_backend(),
        "torch_device": torch_device(),
        "performance_cores": performance_cores(),
        "threads": compute_threads(),
    }


#: Human labels for the accelerators, so a console line reads as prose.
_LABELS: Dict[str, str] = {
    "metal": "Metal (Apple GPU)",
    "cuda": "CUDA (NVIDIA GPU)",
    "mps": "MPS (Apple GPU)",
    "cpu": "CPU only",
    "unavailable": "backend not installed",
}


def describe() -> str:
    """One line naming the accelerator and thread count, for a report header."""
    info = report()
    asr = _LABELS.get(info["whisper_backend"], info["whisper_backend"])
    torch_label = _LABELS.get(info["torch_device"], info["torch_device"])
    line = f"ASR: {asr} · diarization: {torch_label} · {info['threads']} performance threads"
    if info["whisper_backend"] == "cpu":
        line += "\n  ⚠ whisper.cpp is on the CPU: a GPU build would be several times faster."
    return line


if __name__ == "__main__":
    print(describe())
