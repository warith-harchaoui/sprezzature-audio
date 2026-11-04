# Coding standards: sprezzature-audio

## Language

Python 3.10 or newer. Every function and class carries full type annotations. Avoid the catch-all type `Any`; where it is truly unavoidable (an untyped third-party return value, for instance), leave a comment saying why.

## Docstrings

NumPy style: a short summary line, then a `Parameters` section, a `Returns` section, and at least one runnable example, in that order. Every public function and class gets one; see any script's module docstring in `scripts/` for the shape expected (`Usage`, then a fenced example, then `Notes`).

## Comments

Between a quarter and a third of non-blank lines carry a comment. A comment earns its place by explaining *why* a choice was made (a constraint, a workaround, a non-obvious trade-off), never by restating in English what the line already says in Python.

## Style

- `ruff` runs both the linter and the formatter; the line-length limit is 100 characters. `ruff format` applies the formatting automatically, so run it before committing rather than hand-fixing whitespace.
- No filler transitions in prose or comments ("Moreover," "Furthermore," "crucial," "game-changer," "delve into"): if a sentence needs one of these to sound weighty, cut the sentence back to what it actually says.
- No em dash or en dash used as a sentence aside. Use a comma, a colon, a semicolon, parentheses, or simply a second sentence instead.

## Tests

`pytest` runs the suite. Every public function gets at least one test. The suite needs no model, no network and no GPU: the heavy machine-learning libraries (NeMo, whisper.cpp through `vocal-helper`, torch) are installed with the package but never loaded by a test, and `tests/test_the_library_surface.py` blocks them in a subprocess to prove that `import sprezzature_audio` does not reach them.

## Deferred imports

Following on from the point above: `vocal-helper`, `nemo_toolkit`, `numpy` and the narration engines are always imported inside the function that uses them, never at the top of the module. They are base dependencies since 2026-11-01 (there are no feature extras), so this is not about a missing package any more. It is about cost: parsing a WebVTT file, auditing it or answering `--help` must not load a gigabyte of weights. The package's own `__init__` serves the model-backed names lazily for the same reason.

## Versioning

Semantic versioning (`major.minor.patch`): a change that breaks an existing command-line flag or argument bumps the minor version, not the patch version.
