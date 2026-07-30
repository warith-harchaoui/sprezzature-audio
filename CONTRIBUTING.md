# Contributing

## Setup

```sh
git clone https://github.com/warith-harchaoui/sprezzature-audio.git
cd sprezzature-audio
pip install -e ".[dev]"
```

## Run tests

```sh
pytest
```

## Lint

```sh
ruff check .
ruff format --check .
```

## Style

Follow [CODING.md](CODING.md): NumPy docstrings, full typing, 25-30% comments, no machine tells, no punctuation dashes.

## Submitting a patch

1. Fork the repo.
2. Create a branch named `feature/<short-description>` or `fix/<short-description>`.
3. Keep commits atomic.
4. Open a pull request against `main`.

Heavy ML dependencies (NeMo, pywhispercpp) are optional extras. New scripts must degrade gracefully when those extras are absent.
