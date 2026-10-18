#!/usr/bin/env python3
"""
narrate_kokoro — the kokoro voice, as sprezzature-publish drives it.

This file used to hold the engine: the model loading, the segment loop, the
silence arithmetic, the WebVTT writing. All of that is `speaker-helper`'s now,
and the reasons are written where the code is. What survives here is the
module name the orchestrator resolves (`sprezzature_audio_scripts.narrate_kokoro`)
and the flags it speaks — see :mod:`_speaker`.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _speaker import main as _main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Narrate with the kokoro voice; return a process exit code."""
    return _main("kokoro", argv)


if __name__ == "__main__":
    sys.exit(main())
