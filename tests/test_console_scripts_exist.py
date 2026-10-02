"""
Every command the help text names has to be a command you can run.

Release 1.1.0 fixed one of these: ``caption_diarize.py`` called its own Click
command ``sprezzature-audio-caption-diarize`` while pyproject.toml installed
it as ``sprezzature-audio-pipeline``, so its usage line and every epilog
example named something that did not exist. The guard added then,
``test_click_command_name_matches_its_installed_console_script``, reads a
dict of the six Click commands kept in sync by hand, and the two argparse
installers were not in it: ``install_captions.py`` advertised
``sprezzature-audio-install`` and ``install_diarize.py``
``sprezzature-audio-install-diarize``, neither of them installed, while
EXAMPLES.md sent readers to ``python scripts/install_captions.py``, a path a
wheel does not have. Both are console scripts now.

This check derives both sides from the files instead of from a list, so the
next script is covered whether or not anyone remembers it. It complements the
Click test rather than replacing it: that one reads the command object, this
one reads what the source advertises.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

#: A ``prog=`` or Click ``name=`` argument spelling a suite command name.
_PROG_RE = re.compile(r'(?:prog|name)\s*=\s*["\'](sprezzature[a-z0-9-]*)["\']')


def _declared_console_scripts() -> set[str]:
    """The names ``pip install`` actually puts on a user's PATH."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return set(tomllib.load(handle)["project"].get("scripts", {}))


def _advertised_names() -> list[tuple[str, str]]:
    """``(script file name, command it tells the reader to type)`` pairs."""
    out: list[tuple[str, str]] = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _PROG_RE.finditer(text):
            out.append((path.name, match.group(1)))
    return out


@pytest.mark.parametrize(
    "script_name,advertised",
    _advertised_names(),
    ids=lambda value: value,
)
def test_the_command_the_help_names_is_a_command_that_exists(
    script_name: str, advertised: str
) -> None:
    """A ``prog=`` must match a console script pyproject.toml installs."""
    declared = _declared_console_scripts()
    assert advertised in declared, (
        f"{script_name} tells the reader to run {advertised!r}, which "
        f"[project.scripts] does not install. Installed: {sorted(declared)}. "
        f"Either declare it, or name the script after something that exists."
    )


def test_the_scan_that_feeds_the_check_actually_read_something() -> None:
    """
    An empty advertised set has to mean "none advertised", not "none read".

    When no script spells a suite command the parametrised check above gets an
    empty set, pytest turns it into a skip, and the file reports green while
    testing nothing. That is the right answer in a package whose scripts do
    not advertise suite commands, and the wrong one — indistinguishable from
    it — once ``scripts/`` moves, is renamed, or ships in a layout the glob no
    longer matches. This pins the difference: the directory is there and has
    Python in it, so an empty result is a fact about the scripts rather than
    about the scan.
    """
    assert SCRIPTS_DIR.is_dir(), (
        f"{SCRIPTS_DIR} is gone: the advertised-command scan has nothing to "
        f"read, and the check above would skip rather than fail."
    )
    assert list(SCRIPTS_DIR.glob("*.py")), (
        f"{SCRIPTS_DIR} holds no .py file: either the scripts moved or the "
        f"glob no longer matches how they are named."
    )


def test_every_console_script_points_at_something_importable() -> None:
    """The other direction: no entry point naming a module that is not there.

    Skipped on a checkout that was never installed. The mapped script package
    (``..._scripts``) only exists once pip has read ``[tool.setuptools]
    package-dir``, so on a bare clone this would fail for the environment
    rather than for the code. CI installs the package first, which is where
    the check is meant to bite.
    """
    import importlib
    import importlib.util

    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        scripts = tomllib.load(handle)["project"].get("scripts", {})

    for name, target in sorted(scripts.items()):
        module_name, _, attribute = target.partition(":")
        if importlib.util.find_spec(module_name.split(".")[0]) is None:
            pytest.skip(
                f"{module_name.split('.')[0]} is not importable here: this "
                f"checkout is not installed (pip install -e .)."
            )
        module = importlib.import_module(module_name)
        assert hasattr(module, attribute), (
            f"console script {name} points at {target}, but {module_name} has "
            f"no attribute {attribute!r}."
        )
