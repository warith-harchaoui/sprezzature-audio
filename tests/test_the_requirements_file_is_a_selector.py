"""
``requirements.txt`` selects what the manifest declares; it does not copy it.

Two files stating one package's dependencies is two files that can disagree,
and the disagreement is silent in both directions: a missing requirement only
fails when something imports it, and a surplus one installs cleanly.

This one had disagreed. Until 2026-11-01 ``requirements.txt`` listed two
packages — ``click`` and ``langdetect`` — under the heading "Base runtime (no
ML)", while ``pyproject.toml`` declared sixteen. The heading described a
tiering that stopped existing the day the extras were folded into the base, so
``pip install -r requirements.txt`` built an environment that could not
transcribe, diarise or narrate while ``pip install sprezzature-audio`` built
one that could. Nothing compared them.

The cure is a form, not a comparison
------------------------------------
``sprezzature-figures`` has never had this problem because its
``requirements.txt`` is one line: ``-e .``. A selector cannot drift. So rather
than add a test that keeps two lists equal — which is a test that has to be
run, and a drift that has to be repaired — this asserts the *shape*: no
version specifier of its own.

Author
------
Project maintainers.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"

#: A line that pins something: a name followed by a comparison operator.
_PIN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*\s*(\[[^\]]*\])?\s*[<>=!~]")


def _lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_the_file_is_here_and_says_something() -> None:
    assert REQUIREMENTS.is_file(), "requirements.txt is gone"
    assert _lines(REQUIREMENTS), "requirements.txt declares nothing at all"


def test_it_selects_rather_than_pins() -> None:
    """The shape that cannot drift."""
    pinned = [line for line in _lines(REQUIREMENTS) if _PIN.match(line)]
    assert not pinned, (
        "requirements.txt names versions of its own, so it can disagree with "
        "pyproject.toml:\n  " + "\n  ".join(pinned)
    )
    assert any(line.startswith("-e") or line in (".", "-r pyproject.toml")
               for line in _lines(REQUIREMENTS)), (
        f"requirements.txt installs nothing recognisable: {_lines(REQUIREMENTS)}"
    )


def test_no_file_points_at_a_requirements_file_that_is_gone() -> None:
    """``requirements-captions.txt`` and ``requirements-diarize.txt`` described
    the two tiers folded into the base, and three docstrings went on naming the
    first one after it stopped being how anybody installs anything."""
    referenced: dict[str, list[str]] = {}
    for path in ROOT.rglob("*"):
        if path.is_dir() or any(p in path.parts for p in (".git", ".venv", "__pycache__")):
            continue
        if path.suffix not in (".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".cfg"):
            continue
        if path.name.startswith("requirements") or path.name == Path(__file__).name:
            continue      # this file names the removed ones on purpose, above
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name in set(re.findall(r"requirements[a-z-]*\.txt", text)):
            # Anywhere in the tree, not only at the root: the three narration
            # files live under `scripts/`, and looking only at the root
            # reported all three as missing — a guard that accuses is worse
            # than one that sleeps, because somebody acts on it.
            if not any(ROOT.rglob(name)):
                referenced.setdefault(name, []).append(str(path.relative_to(ROOT)))
    assert not referenced, (
        "these name a requirements file that does not exist:\n  "
        + "\n  ".join(f"{name} <- {', '.join(where)}" for name, where in referenced.items())
    )


def test_every_remaining_requirements_file_is_reachable() -> None:
    """A requirements file nobody mentions is an instruction nobody follows —
    and one that quietly describes an old shape of the package."""
    orphans = []
    for path in sorted(ROOT.glob("requirements*.txt")):
        if path.name == "requirements.txt":
            continue                      # the default; needs no reference
        needle = path.name
        found = any(
            needle in other.read_text(encoding="utf-8", errors="ignore")
            for other in ROOT.rglob("*")
            if other.is_file()
            and other != path
            and other.suffix in (".py", ".md", ".toml", ".yml", ".yaml", ".cfg")
            and not any(p in other.parts for p in (".git", ".venv", "__pycache__"))
        )
        if not found:
            orphans.append(path.name)
    assert not orphans, (
        "nothing in this repository mentions these, so they describe a shape "
        f"the package may no longer have: {', '.join(orphans)}"
    )


def test_the_dev_requirements_still_pin_their_tools() -> None:
    """The counterweight. ``requirements-dev.txt`` *should* pin: a linter that
    moves under a build is a build that fails for reasons the commit did not
    cause. Only the runtime file is a selector."""
    dev = ROOT / "requirements-dev.txt"
    if not dev.is_file():
        pytest.skip("this package declares no separate dev requirements")
    assert any(_PIN.match(line) for line in _lines(dev)), (
        "requirements-dev.txt pins nothing; a tool version that floats makes "
        "a build fail for reasons the commit did not cause"
    )
