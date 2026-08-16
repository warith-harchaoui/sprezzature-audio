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

`pytest` runs the suite. Every public function gets at least one test. The heavy machine-learning dependencies (NeMo, pywhispercpp) must be optional: importing them only inside the function that actually needs them, guarded so their absence does not crash anything, and the test suite must pass even on a machine where neither is installed.

## Optional imports

Following on from the point above: `vocal-helper`, `nemo_toolkit`, and `numpy` are always imported inside the function that uses them, never at the top of the module. That keeps the module itself importable on a bare Python 3.10 install, before any of the optional extras are added, which is what lets `pip install sprezzature-audio` (with no extras) still work for anything that does not touch machine learning.

## Versioning

Semantic versioning (`major.minor.patch`): a change that breaks an existing command-line flag or argument bumps the minor version, not the patch version.
