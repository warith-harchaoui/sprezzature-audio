"""
Two small answers a caller reads and nothing else was checking.

The MCP handshake carries a ``version`` field. fastapi-mcp 0.4 builds its
server as ``Server(self.name, self.description)``, and the second positional
parameter of ``Server`` is the version, so every host was told this server's
version is a sentence. ``mcp.py`` puts both values back.

The narration commands take ``--segments`` as a path nobody validated: a
mistyped one fell past the handler, which only covers the engine's refusals,
and came out as a traceback. Every other tool here says ``No such file``.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sprezzature_audio_scripts import _speaker


def test_the_mcp_server_announces_its_version_as_a_version() -> None:
    """fastapi-mcp passes the description into the version slot."""
    pytest.importorskip("fastapi_mcp")
    from sprezzature_audio import __version__
    from sprezzature_audio.mcp import mcp

    options = mcp.server.create_initialization_options()
    assert options.server_version == __version__
    assert options.instructions == mcp.description


@pytest.mark.parametrize("engine", ["kokoro", "openvoice", "chatterbox"])
def test_a_missing_segments_file_is_a_sentence_not_a_traceback(
    engine: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 1 and the path named, before any engine is touched."""
    missing = tmp_path / "nope.json"
    code = _speaker.main(engine, ["--segments", str(missing), "--out-dir", str(tmp_path / "o")])
    assert code == 1
    assert f"No such file: {missing}" in capsys.readouterr().err
