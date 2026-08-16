# Contributing

## Setup

```sh
git clone https://github.com/warith-harchaoui/sprezzature-audio.git
cd sprezzature-audio
pip install -e ".[dev]"
```

The `-e` flag installs the package in "editable" mode: your local checkout is used directly, so an edit to a `.py` file takes effect the next time you run the code, with no reinstall step.

## Run tests

```sh
pytest
```

## Lint

```sh
ruff check .
ruff format --check .
```

`ruff check` looks for actual problems (unused imports, undefined names); `ruff format --check` only reports whether the formatting already matches what `ruff format` would produce, without changing anything. Run `ruff format .` (no `--check`) to apply the formatting yourself before committing.

## Style

Follow [CODING.md](CODING.md): NumPy-style docstrings, full type annotations, a comment on roughly a quarter to a third of lines, no filler transitions, no dash used as a sentence aside.

## Submitting a patch

1. Fork the repository.
2. Create a branch named `feature/<short-description>` for a new capability, or `fix/<short-description>` for a bug fix.
3. Keep each commit atomic: one commit should correspond to one coherent change, not a mix of unrelated edits.
4. Open a pull request against `main`.

The heavy machine-learning dependencies (NeMo, pywhispercpp) are optional extras, not requirements. Any new script must still degrade gracefully, meaning it should give a clear error message rather than a confusing traceback, when those extras are not installed.
