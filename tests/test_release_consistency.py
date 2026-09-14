"""
The version is written in two places and read in a third, and nothing tied
them together.

``__version__`` is what ``api.py`` hands FastAPI, so it reaches
``/openapi.json`` and the headline an MCP host displays; ``pyproject.toml`` is
what pip installs. In ``sprezzature-figures`` those two drifted and the API
advertised 2.0.0 through the whole 2.1.0 release — a defect no test could see,
because neither number is used by any code path a test exercises.

The CHANGELOG is the third: a release whose top section names an older version
ships undocumented changes.

Read with a regex rather than ``tomllib``, which is stdlib only from 3.11 while
this package supports 3.10.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import re
from pathlib import Path

from sprezzature_audio import __version__

REPO_ROOT = Path(__file__).resolve().parent.parent

_PYPROJECT_VERSION_RE = re.compile(r'^\s*version\s*=\s*["\']([\d.]+)["\']', re.MULTILINE)
_RELEASE_HEADING_RE = re.compile(r"^##\s+\[?v?([\d.]+)\]?", re.MULTILINE)


def _pyproject_version() -> str:
    """The ``project.version`` pip installs, straight from pyproject.toml."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = _PYPROJECT_VERSION_RE.search(text)
    assert match, "pyproject.toml declares no project version"
    return match.group(1)


def test_package_version_matches_pyproject() -> None:
    """``__version__`` is what the surfaces advertise; pyproject is what pip installs."""
    declared = _pyproject_version()
    assert __version__ == declared, (
        f"version drift: sprezzature_audio.__version__ is {__version__!r} but "
        f"pyproject.toml declares {declared!r}."
    )


def test_changelog_leads_with_the_current_version() -> None:
    """The top release section of the CHANGELOG names the version being shipped."""
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = _RELEASE_HEADING_RE.findall(text)
    assert headings, "CHANGELOG.md has no release headings"
    assert headings[0] == __version__, (
        f"CHANGELOG.md leads with {headings[0]}, but the package is {__version__}. "
        "A release whose top section is an older version ships undocumented changes."
    )
