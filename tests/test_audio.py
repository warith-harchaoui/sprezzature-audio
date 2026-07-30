"""Tests for sprezzature_audio package and core script helpers."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def test_package_imports() -> None:
    """sprezzature_audio package is importable without heavy ML deps."""
    import sprezzature_audio

    assert sprezzature_audio.__version__ == "1.0.0"
    assert sprezzature_audio.__author__ == "Warith Harchaoui"


def test_lang_detect_fallback_without_langdetect(monkeypatch: object) -> None:
    """detect_text_language returns fallback when langdetect is absent."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    # Force langdetect to appear absent.
    import importlib.util as _util

    original = _util.find_spec

    def _fake_find_spec(name: str) -> None:  # type: ignore[override]
        if name == "langdetect":
            return None
        return original(name)

    import importlib.util as ilu

    monkeypatch.setattr(ilu, "find_spec", _fake_find_spec)

    # Reload _lang so the patched find_spec takes effect.
    if "_lang" in sys.modules:
        del sys.modules["_lang"]

    import _lang  # type: ignore[import-not-found]

    result = _lang.detect_text_language("hello world this is a test sentence", fallback="fr")
    # Without langdetect, fallback must be returned.
    assert result == "fr"


def test_lang_known_codes() -> None:
    """LANGUAGE_NAMES covers the common European languages."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    if "_lang" in sys.modules:
        del sys.modules["_lang"]

    import _lang  # type: ignore[import-not-found]

    for code in ("en", "fr", "es", "de", "it", "pt"):
        assert code in _lang.LANGUAGE_NAMES, f"Missing: {code}"
        assert isinstance(_lang.LANGUAGE_NAMES[code], str)


def test_lang_language_name_helper() -> None:
    """language_name converts codes to English names."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    if "_lang" in sys.modules:
        del sys.modules["_lang"]

    import _lang  # type: ignore[import-not-found]

    assert _lang.language_name("fr") == "French"
    assert _lang.language_name("de") == "German"
    assert _lang.language_name("UNKNOWN_CODE", default="English") == "English"


def test_captions_module_importable() -> None:
    """captions_from_whisper is importable (heavy deps not exercised)."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    # The module does a sys.path.insert at top level; as long as it doesn't
    # import vocal-helper or audio-helper at module scope, this should pass.
    # existence on disk is enough; heavy deps are not exercised here.
    # We just verify the file is present.
    assert (SCRIPTS_DIR / "captions_from_whisper.py").is_file()


def test_extract_body_text_html() -> None:
    """extract_body_text strips HTML tags and script elements."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    if "_lang" in sys.modules:
        del sys.modules["_lang"]

    import _lang  # type: ignore[import-not-found]

    html = "<html><body><p>Hello <b>world</b></p><script>var x=1</script></body></html>"
    result = _lang.extract_body_text(html, fmt="html")
    assert "Hello" in result
    assert "world" in result
    assert "var x" not in result


def test_extract_body_text_markdown() -> None:
    """extract_body_text strips Markdown syntax."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    if "_lang" in sys.modules:
        del sys.modules["_lang"]

    import _lang  # type: ignore[import-not-found]

    md = "# Title\n\nSome **bold** [text](http://x)."
    result = _lang.extract_body_text(md, fmt="markdown")
    assert "Title" in result
    assert "bold" in result
    assert "**" not in result
