# Contributing

## Setup

```sh
git clone https://github.com/warith-harchaoui/sprezzature-audio.git
cd sprezzature-audio
pip install -e . -r requirements-dev.txt
git config core.hooksPath .githooks
```

The `-e` flag installs the package in "editable" mode: your local checkout is used directly, so an edit to a `.py` file takes effect the next time you run the code, with no reinstall step. `requirements-dev.txt` is what CI (continuous integration, the checks GitHub runs on every push) installs: pytest, ruff, mypy and the test-only helpers. The `[dev]` extra carries only pytest and ruff. The second line turns on the pre-push hook, which runs ruff, mypy and pytest before every push: the steps of CI, plus mypy.

## Run tests

```sh
pytest -q
```

## Lint and types

The same steps as the pre-push hook (`.githooks/pre-push`), in the same order:

```sh
ruff check .
mypy sprezzature_audio
mypy scripts
pytest -q
```

CI (`.github/workflows/ci.yml`) runs `ruff check .` and `pytest -q` on Python 3.12, and a second job that only installs and imports the package on Python 3.10, the oldest version it promises. mypy runs in the hook and not in CI. `ruff check` looks for actual problems (unused imports, undefined names). mypy runs twice because the modules in `scripts/` import each other by bare name, which only resolves when that directory is the root of the check.

Format the files you changed, and only those: `ruff format path/to/file.py`. CI does not run `ruff format --check`, and several files are not in ruff's format today, so `ruff format .` would rewrite code nobody meant to touch.

## Style

Follow [CODING.md](CODING.md): NumPy-style docstrings, full type annotations, a comment on roughly a quarter to a third of lines, no filler transitions, no dash used as a sentence aside.

## Submitting a patch

1. Fork the repository.
2. Create a branch named `feature/<short-description>` for a new capability, or `fix/<short-description>` for a bug fix.
3. Keep each commit atomic: one commit should correspond to one coherent change, not a mix of unrelated edits.
4. Open a pull request against `main`.

The heavy machine-learning dependencies (NeMo, whisper.cpp through `vocal-helper`, the narration engines) are part of the base install; there are no feature extras. A new script still imports them inside the function that needs them, so that `--help` and the model-free paths stay instant, and it gives a clear error message rather than a confusing traceback when one of them fails to import.

A new command goes in three places: a `[project.scripts]` line in `pyproject.toml`, an entry in `TOOLS` in `sprezzature_audio/_tools.py` (which gives it a front-door sub-command), and a row in `README.md`, `LISEZMOI.md`, `TRIGGERS.md` and the skill's `sprezzature_audio/skill/SKILL.md`, which ships inside the package. Two parts of the skill belong to the sprezzature hub: `sprezzature_audio/skill/references/triggers.md` is generated there, and the `description:` in the front matter of `SKILL.md` is where the hub's `scripts/build_triggers.py` reads the trigger phrases, so a change to either one is a hub change too. Command lines use click.
