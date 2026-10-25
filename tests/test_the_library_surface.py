"""
The library surface is the one that is easiest to fake.

``pip install`` works, ``import sprezzature_audio`` works, and the caller
still has nothing to call: that was this package until now — an
``__init__.py`` holding a version string and a docstring while the engine
lived in ``sprezzature_audio_scripts``, a package named for how the code was
built rather than for what it does.

What these tests hold:

- every name in ``__all__`` resolves, and resolves to the right thing;
- the import costs nothing — with every optional dependency blocked at the
  meta-path, ``import sprezzature_audio`` still succeeds and the no-model
  half still works;
- a typo reads as a typo (``AttributeError``), not as a missing dependency;
- an install hint printed at run time names something a wheel user has.
  The last one is not hypothetical: three of them named
  ``requirements-narrate-*.txt``, a file that exists in a clone and nowhere
  else, so the one person who most needed the message — someone who ran
  ``pip install sprezzature-audio`` — was sent to a path they do not have.

Nothing here needs a model, a network or an extra.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 — tomllib landed in 3.11
    import tomli as tomllib

import sprezzature_audio

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
EXTRAS = set(PYPROJECT["project"].get("optional-dependencies", {}))

#: Top-level distributions that only an extra installs. Blocked wholesale in
#: the subprocess below, which is the only way to check the promise on a
#: machine where the extras happen to be installed — and this machine is one.
OPTIONAL_DISTRIBUTIONS = (
    "torch",
    "torchaudio",
    "numpy",
    "nemo",
    "nemo_toolkit",
    "vocal_helper",
    "audio_helper",
    "video_helper",
    "kokoro_onnx",
    "soundfile",
    "espeakng_loader",
    "best_engine_ai_helper",
    "resemble_perth",
    "onnxruntime",
    "fastapi",
    "uvicorn",
    "fastapi_mcp",
)


# ── The names ──────────────────────────────────────────────────────────────


def test_the_package_exports_an_engine_not_a_version_string() -> None:
    """``__all__`` has to carry callables, or it is not a library surface."""
    callables = [
        name
        for name in sprezzature_audio.__all__
        if not name.startswith("__") and callable(getattr(sprezzature_audio, name))
    ]
    assert len(callables) > 20, f"only {len(callables)} callable exports"


@pytest.mark.parametrize("name", sorted(sprezzature_audio.__all__))
def test_every_exported_name_resolves(name: str) -> None:
    """No export may be a promise the module cannot keep."""
    assert getattr(sprezzature_audio, name) is not None


def test_dir_sees_the_lazy_names_too() -> None:
    """Tab completion must show the half that is served on demand."""
    assert "narrate" in dir(sprezzature_audio)
    assert "transcribe" in dir(sprezzature_audio)


def test_an_unknown_name_is_an_attribute_error_not_an_import_error() -> None:
    """A typo should read as a typo, not as a missing dependency."""
    with pytest.raises(AttributeError):
        sprezzature_audio.definitely_not_a_tool


@pytest.mark.parametrize(
    ("name", "extra"),
    sorted((n, e) for n, (_m, e) in sprezzature_audio._LAZY.items()),
)
def test_every_lazy_name_names_a_real_extra(name: str, extra: str) -> None:
    """The install line in the error has to be one pip can actually run."""
    assert extra in EXTRAS, f"{name} points at `[{extra}]`, which pyproject does not declare"


def test_an_ambiguous_name_is_not_exported() -> None:
    """
    Two modules define ``extract_audio`` and they are not the same function.

    A single bare export would silently be whichever one was listed last,
    which is the quiet half of this failure: the import works, the call
    works, and the wrong code ran.
    """
    assert "extract_audio" not in sprezzature_audio.__all__


# ── The import costs nothing ───────────────────────────────────────────────


def _run_with_optional_deps_blocked(body: str) -> subprocess.CompletedProcess[str]:
    """Run `body` in a subprocess where no optional distribution can import."""
    code = textwrap.dedent(
        f"""
        import sys
        BLOCKED = {OPTIONAL_DISTRIBUTIONS!r}
        class Blocker:
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in BLOCKED:
                    raise ImportError("blocked optional dependency: " + name)
                return None
        sys.meta_path.insert(0, Blocker())
        """
    ) + textwrap.dedent(body)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def test_the_library_imports_with_no_extras_at_all() -> None:
    """
    ``import sprezzature_audio`` must work after a bare ``pip install``.

    Reading a VTT file, auditing it and scoring a transcript are stdlib work
    — that is why they are worth reaching for from a pre-commit hook — and an
    ``__init__`` that imported Whisper eagerly would take that away from
    everyone who only reads captions.
    """
    done = _run_with_optional_deps_blocked(
        """
        import sprezzature_audio as a
        cues = a.parse("WEBVTT\\n\\n00:00:00.000 --> 00:00:01.000\\nhello\\n")
        assert [c.text for c in cues] == ["hello"]
        assert a.write_vtt(cues).startswith("WEBVTT")
        assert all(f.rule for f in a.audit_cues(cues))
        assert a.word_error_rate(["a", "b"], ["a", "b"])["wer"] == 0
        assert a.detect_text_language("this is plainly written in english") == "en"
        print("OK")
        """
    )
    assert done.returncode == 0, done.stderr[-3000:]
    assert "OK" in done.stdout


def test_the_heavy_halves_are_not_pulled_in_by_the_import() -> None:
    """No model library may be in ``sys.modules`` after a bare import."""
    done = _run_with_optional_deps_blocked(
        """
        import sys
        import sprezzature_audio  # noqa: F401
        leaked = sorted(
            m for m in sys.modules
            if m.split(".")[0] in ("torch", "nemo", "kokoro_onnx", "vocal_helper")
        )
        assert not leaked, leaked
        print("OK")
        """
    )
    assert done.returncode == 0, done.stderr[-3000:]
    assert "OK" in done.stdout


# ── The install hints point at something a wheel user has ──────────────────


#: A hint that names a requirements file must name an extra in the same
#: message. The file ships in the repository and not in the wheel, so it is a
#: fine *second* line and a useless only one.
_REQUIREMENTS_HINT = re.compile(r"requirements-[a-z-]+\.txt")
_EXTRA_HINT = re.compile(r"sprezzature-audio\[[a-z-]+\]")

#: A raised error or a printed message, captured from `raise ...(` or
#: `print(` up to the closing paren. Deliberately per *message*: a module may
#: legitimately name the requirements file in its docstring while raising a
#: hint that names the extra, and a per-file check would conflate the two.
_MESSAGE = re.compile(r"(?:raise \w+Error\(|print\()(.*?)\)(?:\s*from\s|\s*\n)", re.S)


@pytest.mark.parametrize(
    "script",
    sorted(p.name for p in (Path(__file__).resolve().parent.parent / "scripts").glob("*.py")),
)
def test_a_runtime_install_hint_names_an_extra_not_only_a_clone_path(script: str) -> None:
    """
    Every ``pip install -r requirements-*.txt`` reachable at run time has to
    sit beside the extra that does the same job from a wheel.
    """
    source = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    offenders = [
        message.strip()[:160]
        for message in _MESSAGE.findall(source)
        if _REQUIREMENTS_HINT.search(message) and not _EXTRA_HINT.search(message)
    ]
    assert not offenders, f"{script}: hint names a clone-only path: {offenders}"
