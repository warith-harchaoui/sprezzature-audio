"""
test_the_front_door_answers_both_version_flags — `-V` and `--version` both work.

Every per-tool command (scripts/_click.py) answered `-V` and `--version`,
while the front door `sprezzature-audio` took `--version` only, so
`sprezzature-audio -V` was a usage error. The version printed is compared with
the installed metadata, not a literal that ages with each release.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from importlib.metadata import version

import pytest
from click.testing import CliRunner

from sprezzature_audio.cli import main


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_the_front_door_answers_both_version_flags(flag: str) -> None:
    result = CliRunner().invoke(main, [flag])
    assert result.exit_code == 0, result.output
    assert version("sprezzature-audio") in result.output, result.output
