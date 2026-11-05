# Contributing

## Setup

```sh
git clone https://github.com/warith-harchaoui/sprezzature-audio.git
cd sprezzature-audio
pip install -e . -r requirements-dev.txt
git config core.hooksPath .githooks
```

The `-e` flag installs the package in "editable" mode: your local checkout is used directly, so an edit to a `.py` file takes effect the next time you run the code, with no reinstall step. `requirements-dev.txt` is what CI installs: pytest, ruff, mypy and the test-only helpers. The `[dev]` extra carries only pytest and ruff. The second line turns on the pre-push hook, which runs the same steps as CI.

## Run tests

```sh
pytest -q
```

## Lint and types

The same steps as CI (`.github/workflows/ci.yml`), in the same order:

```sh
ruff check .
mypy sprezzature_audio
mypy scripts
```

`ruff check` looks for actual problems (unused imports, undefined names). mypy runs twice because the modules in `scripts/` import each other by bare name, which only resolves when that directory is the root of the check.

Format the files you changed, and only those: `ruff format path/to/file.py`. CI does not run `ruff format --check`, and several files are not in ruff's format today, so `ruff format .` would rewrite code nobody meant to touch.

## Style

Follow [CODING.md](CODING.md): NumPy-style docstrings, full type annotations, a comment on roughly a quarter to a third of lines, no filler transitions, no dash used as a sentence aside.

## Submitting a patch

1. Fork the repository.
2. Create a branch named `feature/<short-description>` for a new capability, or `fix/<short-description>` for a bug fix.
3. Keep each commit atomic: one commit should correspond to one coherent change, not a mix of unrelated edits.
4. Open a pull request against `main`.

The heavy machine-learning dependencies (NeMo, whisper.cpp through `vocal-helper`, the narration engines) are part of the base install; there are no feature extras. A new script still imports them inside the function that needs them, so that `--help` and the model-free paths stay instant, and it gives a clear error message rather than a confusing traceback when one of them fails to import.

A new command goes in three places: a `[project.scripts]` line in `pyproject.toml`, an entry in `TOOLS` in `sprezzature_audio/_tools.py` (which gives it a front-door sub-command), and a row in `README.md`, `LISEZMOI.md` and `TRIGGERS.md`. Command lines use click.
