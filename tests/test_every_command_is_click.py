"""
Every command this package installs is a click command, and answers ``--help``.

On 2026-11-04 the last argparse parsers went: seven scripts, the narration
wrapper the three ``narrate`` commands share, and the MCP server's ``main``.
The decision is the author's, for the whole suite: one parser library, so
every command reads the same way, ``-h`` and ``-V`` included.

A static scan alone would not hold that line. A parser can be click and still
fail ``--help`` (a module that does not import, a ``main`` that ignores its
argv), and an ``import argparse`` can come back in a file nobody runs. So
this file checks both: each console script, called the way pip calls it,
must print a click usage line under its own name and exit 0; and no module
of the package may import argparse.

The one exception is ``scripts/_argparse.py``. This repository holds the
canonical copy the sprezzature hub syncs into the other bricks, so it stays
here even though nothing in this package imports it any more.

The front door is checked too: ``sprezzature-audio audit --help`` used to
print the sub-command stub, one line and a ``REST`` argument, because the
group answered ``--help`` before the tool could; only ``-- --help`` got
through. The sub-commands now leave ``--help`` to the tool.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import re
from importlib.metadata import distribution
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Kept for the suite, imported by nothing here; see the module docstring.
_CANONICAL_HELPER = REPO_ROOT / "scripts" / "_argparse.py"

#: The front-door group's usage line names whatever ``sys.argv[0]`` is, which
#: under pytest is pytest. Its name is checked through the tools instead.
_FRONT_DOORS = frozenset({"sprezzature-audio", "make-audio"})

_ARGPARSE_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+argparse\b|from\s+argparse\s+import|from\s+_argparse\s+import"
    r"|import\s+_argparse\b)",
    re.M,
)


def _console_scripts() -> list[tuple[str, str]]:
    """``(command, "module:attribute")`` from the installed metadata."""
    try:
        dist = distribution("sprezzature-audio")
    except Exception:  # pragma: no cover - a bare clone
        return []
    return sorted((ep.name, ep.value) for ep in dist.entry_points if ep.group == "console_scripts")


def test_the_installed_metadata_lists_the_commands() -> None:
    """An empty list would turn the check below into a skip that reads as a pass."""
    scripts = _console_scripts()
    if not scripts:
        pytest.skip("sprezzature-audio is not installed here (pip install -e .)")
    assert len(scripts) >= 18, scripts


@pytest.mark.parametrize(("command", "target"), _console_scripts(), ids=lambda v: v)
def test_every_console_script_answers_help_the_click_way(
    command: str, target: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """``COMMAND --help`` exits 0 and prints a click ``Usage:`` line under its name."""
    import importlib

    module_name, _, attribute = target.partition(":")
    entry = getattr(importlib.import_module(module_name), attribute)
    # Either way out is a success: ``run_command`` returns click's exit code
    # on the click releases that hand it back, and raises SystemExit on the
    # older ones; the front-door group always exits.
    try:
        code = entry(["--help"])
    except SystemExit as exc:
        code = exc.code
    assert code in (0, None), (command, code)

    out = capsys.readouterr().out
    assert out.startswith("Usage: "), (
        f"{command} --help did not print a click usage line; argparse prints "
        f"'usage:' in lower case. First line: {out.splitlines()[:1]!r}"
    )
    if command not in _FRONT_DOORS:
        assert out.startswith(f"Usage: {command} "), (
            f"{command} --help names another program: {out.splitlines()[0]!r}"
        )


def test_no_module_of_the_package_imports_argparse() -> None:
    """Static half: argparse does not come back in a file nobody runs."""
    sources = sorted(
        path
        for folder in ("sprezzature_audio", "scripts")
        for path in (REPO_ROOT / folder).glob("*.py")
        if path != _CANONICAL_HELPER
    )
    assert sources, "the scan read no Python at all"
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in sources
        if _ARGPARSE_IMPORT_RE.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"argparse is imported by {offenders}; use scripts/_click.py"


@pytest.mark.parametrize("front_door", sorted(_FRONT_DOORS))
def test_the_front_door_passes_help_to_the_tool(front_door: str) -> None:
    """``sprezzature-audio audit --help`` shows the audit's own flags, not a stub."""
    from click.testing import CliRunner

    from sprezzature_audio.cli import main

    result = CliRunner().invoke(main, ["audit", "--help"], prog_name=front_door)
    assert result.exit_code == 0, result.output
    assert "Usage: sprezzature-audio-audit " in result.output, result.output
    for flag in ("--cps", "--min-seconds", "--line-chars", "--format"):
        assert flag in result.output, (flag, result.output)
    assert "REST" not in result.output, result.output


def test_the_front_door_still_answers_its_own_help() -> None:
    """Before a tool is named, ``--help`` is the catalogue's."""
    from click.testing import CliRunner

    from sprezzature_audio.cli import main

    result = CliRunner().invoke(main, ["--help"], prog_name="sprezzature-audio")
    assert result.exit_code == 0, result.output
    assert "audit" in result.output and "narrate" in result.output
