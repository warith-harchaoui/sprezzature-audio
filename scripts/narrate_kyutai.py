#!/usr/bin/env python3
"""
narrate_kyutai — the kyutai voice, as sprezzature-publish drives it.

Added 2026-10-26, when ``speaker-helper`` 0.11 brought the backend in. It is
the one engine here that was chosen *for French*: Kyutai's ``tts-1.6b-en_fr``
comes from a Paris lab and renders French natively, where kokoro, openvoice
and chatterbox all reach French through an English-first pipeline. On a Mac
``speaker-helper`` serves it through Kyutai's own MLX implementation, which is
what makes it usable at all — RTF 0.84 against 7.8 on torch-CPU.

It is an extra and not the default, and the reason is the bar this package
already states in ``pyproject.toml``: Apache-2.0 in code *and* weights, which
is what kokoro has and what ruled out F5-TTS and XTTS-v2. Kyutai's code is
MIT and its weights are CC-BY-4.0 — permissive, and not the same promise. A
reader who wants the better French voice can ask for it by name; nobody gets
it by surprise.

See :mod:`_speaker` for the flags, which are identical across all four
engines on purpose.

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
    """Narrate with the kyutai voice; return a process exit code."""
    return _main("kyutai", argv)


if __name__ == "__main__":
    sys.exit(main())
