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
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

#: ``[project.scripts]`` is read with a regex rather than the ``tomllib``
#: module, which is stdlib only from 3.11 while these packages support 3.10 --
#: there the import alone failed collection of this entire file, and CI said so
#: on the first push that reached it. ``test_release_consistency.py`` already
#: reads pyproject.toml this way and explains why; this file had not followed.
_SCRIPTS_SECTION_RE = re.compile(r"^\[project\.scripts\]\s*$(.*?)(?=^\[|\Z)", re.M | re.S)
_SCRIPT_ENTRY_RE = re.compile(r'^\s*([A-Za-z0-9._-]+)\s*=\s*["\']([^"\']+)["\']', re.M)


def _console_scripts() -> dict[str, str]:
    """``{installed command: "module:attribute"}`` straight from pyproject.toml."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = _SCRIPTS_SECTION_RE.search(text)
    if section is None:
        return {}
    return dict(_SCRIPT_ENTRY_RE.findall(section.group(1)))


#: A ``prog=`` or Click ``name=`` argument spelling a suite command name.
_PROG_RE = re.compile(r'(?:prog|name)\s*=\s*["\'](sprezzature[a-z0-9-]*)["\']')


def _declared_console_scripts() -> set[str]:
    """The names ``pip install`` actually puts on a user's PATH."""
    return set(_console_scripts())


#: Directories the scan must not read. ``tests`` above all: fixtures in there
#: spell command names that are deliberately wrong, which is their job.
_UNSCANNED = frozenset({".git", ".venv", "build", "dist", "__pycache__", "tests", "node_modules"})


def _sources() -> list[Path]:
    """Every Python file this repository ships, wherever it keeps them."""
    return sorted(
        path
        for path in REPO_ROOT.rglob("*.py")
        if not _UNSCANNED & set(path.relative_to(REPO_ROOT).parts)
    )


def _advertised_names() -> list[tuple[str, str]]:
    """``(file, command it tells the reader to type)`` pairs, repo-wide.

    Read from the whole repository, not from ``scripts/`` alone. A front
    door's ``prog=`` lives wherever its package keeps sources: under
    ``scripts/`` in some bricks, in the importable package in
    sprezzature-cli-gui and sprezzature-figures. Scanning the one directory
    made this check **vacuous** in those two — an empty parameter set, which
    pytest reports as a skip and a reader takes for a pass. Measured on
    2026-10-31 across the six bricks carrying this file: the directory scan
    read 0 names in cli-gui and figures and missed 3 to 4 in each of the other
    four; the repository scan reads them all, and every name it finds is a
    command that is installed.
    """
    out: list[tuple[str, str]] = []
    for path in _sources():
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _PROG_RE.finditer(text):
            out.append((str(path.relative_to(REPO_ROOT)), match.group(1)))
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
    An empty advertised set means the scan went blind, not that nothing is named.

    When nothing spells a suite command the parametrised check above gets an
    empty set, pytest turns it into a skip, and the file reports green while
    testing nothing. Until 2026-10-31 this test accepted that outcome as long
    as ``scripts/`` existed and held Python — which is exactly the state
    sprezzature-cli-gui and sprezzature-figures were in while the check above
    ran on nothing at all, because their front doors live in the importable
    package and the scan only read ``scripts/``. The directory being populated
    said nothing about whether the scan had looked where the parsers are.

    What is asserted now is the result, not the premise: every one of these
    packages has a front door that names itself, so an empty set can only mean
    the scan stopped finding them.
    """
    sources = _sources()
    assert sources, (
        f"the scan read no Python at all under {REPO_ROOT}: the check above "
        f"would skip rather than fail, and a skip reads as a pass."
    )
    assert _advertised_names(), (
        f"not one of the {len(sources)} Python files here spells a suite "
        f"command in a prog= or name=. A package whose front door does not "
        f"name itself is the thing this file exists to catch, so an empty "
        f"result is a blind scan rather than a clean bill of health. Either "
        f"_PROG_RE stopped matching how the front doors are written, or the "
        f"front doors stopped naming themselves."
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

    scripts = _console_scripts()

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


#: Any ``prog=`` at all, not only one that already spells a suite command.
#: The check above reads ``_PROG_RE``, which matches ``prog="sprezzature-*"``
#: — so it catches a command named *wrongly* and is blind to one named after
#: nothing at all. Six scripts sat in that blind spot:
#: ``sprezzature-audio-narrate-kokoro --help`` printed ``usage:
#: narrate_kokoro``, and ``sprezzature-audio-benchmark --help`` printed
#: ``usage: benchmark_stt.py``. Both are module names: a reader who typed
#: what the help told them got "command not found", from the surface whose
#: whole job is to say how to run the thing.
_ANY_PROG_RE = re.compile(r'prog\s*=\s*["\']([^"\']+)["\']')


def _module_to_command() -> dict[str, str]:
    """``{scripts/<module>.py: the command pip installs for it}``."""
    out: dict[str, str] = {}
    for command, target in _console_scripts().items():
        module_name, _, _attribute = target.partition(":")
        if module_name.startswith("sprezzature_audio_scripts."):
            out[module_name.split(".")[-1]] = command
    return out


@pytest.mark.parametrize(
    "module_name,command",
    sorted(_module_to_command().items()),
    ids=lambda value: value,
)
def test_an_installed_script_names_its_own_command_in_prog(module_name: str, command: str) -> None:
    """A script that pip installs must say, in ``--help``, what pip called it.

    Only scripts that *have* a console script are checked, and only if they
    declare a ``prog=`` at all: a module with no parser of its own, or one
    reached solely as a sub-command, owes nothing here.
    """
    path = SCRIPTS_DIR / f"{module_name}.py"
    if not path.is_file():  # pragma: no cover - layout guard
        pytest.skip(f"{path} is not in this checkout")
    progs = _ANY_PROG_RE.findall(path.read_text(encoding="utf-8", errors="replace"))
    if not progs:
        pytest.skip(f"{module_name}.py declares no prog=")
    assert command in progs, (
        f"{module_name}.py sets prog={progs!r}, but pip installs it as "
        f"{command!r}. A reader who types what --help shows gets "
        f"'command not found'."
    )
