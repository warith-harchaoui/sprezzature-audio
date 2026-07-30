# Coding standards -- sprezzature-audio

## Language

Python 3.10+. Full type annotations. No `Any` unless unavoidable and documented.

## Docstrings

NumPy style. Every public function and class gets a docstring with Parameters, Returns, and at least one example.

## Comments

25-30% of non-blank lines carry a comment. Comments explain **why**, not what. No obvious restatements of the code.

## Style

- `ruff` for linting and formatting. Line length 100.
- `ruff format` for auto-formatting.
- No machine tells: no "Moreover", "Furthermore", "crucial", "game-changer", "delve into".
- No punctuation dashes used as asides.

## Tests

`pytest`. Every public function has at least one test. Heavy ML deps (NeMo, pywhispercpp) must be optional-import-guarded; tests must pass without them.

## Optional imports

Heavy dependencies (vocal-helper, nemo_toolkit, numpy) are always imported inside the function that needs them, never at module top level. The module must be importable on a bare Python 3.10 install.

## Versioning

Semantic versioning. Breaking CLI changes bump the minor version.
