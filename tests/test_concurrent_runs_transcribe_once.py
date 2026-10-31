"""
Two runs that want the same transcription make one, not two.

The defect, measured
--------------------
Both cached tools in this package — captions and diarization — were written
as *read, miss, work, write*, and the gap between the read and the write was
wide open::

    key = _cache_key(audio_bytes, ...)
    if _cache_get(key) is not None:   # <- nothing stands between
        return ...                    #    these two lines and another
    out = <load the model, run it>    #    process doing exactly the
    _cache_set(key, out)              #    same thing

Three processes started together on a cold cache, all asking to transcribe
one file, made **three** real whisper runs 2.6 ms apart. That is three model
loads, three model-sized allocations and three runs of minutes, and then two
of the three results thrown away. With the ledger behind
:func:`_wallet.memoized` the same three produce one run and two waiters.

What is asserted here
---------------------
The four properties a result cache can have, one test each, because they fail
independently and three of them were holding before this file:

* content addressing — same bytes at a different path hit, different bytes do
  not, which is the property these two tools lean on hardest, since the thing
  being keyed is an extracted WAV in a temporary directory whose path is
  different on every single run;
* **cross-process single-flight** — the one that was missing;
* survival across a restart — a second process reuses the first's result;
* and the degradations, so none of the above can be bought with a crash.

Written with real subprocesses rather than threads on purpose: the absence
being guarded against was *between processes*, and a threading test passes
against the in-process ledger, which is the backend that does not fix it.

The sabotage that proves it has teeth
-------------------------------------
In ``scripts/_wallet.py``, make :func:`_wallet._ledger` return
``Ledger(cache_dir)`` — the JSON store — instead of the SQLite one. Nothing
else changes, every other test in this repository stays green, the cache
still works, and :func:`test_three_processes_make_one_transcription` reports
3.

Sabotaging the *key* proves nothing, and that is the trap this file was
written around: ``wallet_helper.ledger.make_key`` content-addresses a string
that names an existing file, so swapping a digest for a path can leave the
behaviour intact and the guard green. The property has to be broken, not the
identifier.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from _wallet import memoized, wallet_for

REPO_ROOT = Path(__file__).resolve().parent.parent

# The helper that provides the property under test. This package's CI installs
# `[api,mcp]` and the dev requirements and no heavy extra, on purpose — so
# `wallet-helper` is named in `requirements-dev.txt` as well as in the
# `[captions]` and `[diarize]` extras, precisely so this file runs in the one
# environment that gates the repository. Measured before declaring it: 8.7 MB
# and thirteen pure-Python wheels from an empty venv, no numpy (which would
# have broken `mypy` here, see mypy.ini), no torch.
pytest.importorskip(
    "wallet_helper",
    reason=(
        "wallet-helper is declared in requirements-dev.txt and in the "
        "[captions] / [diarize] extras. If this skips, the manifest and the "
        "install have come apart: pip install -r requirements-dev.txt"
    ),
)

#: A worker that memoizes one call, recording every real run in a shared file.
#: The sleep is what makes an overlap observable: without it a process can
#: finish before the next one starts, and three sequential runs would also
#: produce one call, for the wrong reason.
WORKER = textwrap.dedent(
    """
    import sys, os, time, pathlib
    scripts, cache_dir, counter, digest, naptime = sys.argv[1:6]
    sys.path.insert(0, scripts)
    from _wallet import memoized

    def work():
        with open(counter, "a") as handle:
            handle.write(f"{time.time():.6f} {os.getpid()}\\n")
        time.sleep(float(naptime))
        return "WEBVTT\\n\\n00:00:00.000 --> 00:00:01.000\\nhello\\n"

    out = memoized("guard", digest, work, cache_dir=pathlib.Path(cache_dir))
    assert out.startswith("WEBVTT"), out
    """
)


def _run(workers: int, cache_dir: Path, counter: Path, digest: str, nap: float) -> int:
    """Start ``workers`` processes at once and return how many did real work."""
    script = cache_dir.parent / "worker.py"
    script.write_text(WORKER, encoding="utf-8")
    argv = [
        sys.executable,
        str(script),
        str(REPO_ROOT / "scripts"),
        str(cache_dir),
        str(counter),
        digest,
        str(nap),
    ]
    running = [
        subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(workers)
    ]
    for process in running:
        _, err = process.communicate(timeout=120)
        assert process.returncode == 0, err.decode()
    return len(counter.read_text(encoding="utf-8").splitlines()) if counter.exists() else 0


@pytest.fixture
def arena(tmp_path):
    """A cold cache directory and the counter the workers append to."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    # Open the ledger once here, which is what every run after the first sees
    # anyway, so this test measures single-flight rather than the creation
    # race. That race has its own test below.
    wallet_for(cache_dir)
    return cache_dir, tmp_path / "calls.txt"


def test_three_processes_make_one_transcription(arena) -> None:
    """The measured defect: three concurrent asks, one real run.

    Three before this, 2.6 ms apart. The two followers are served the
    leader's result, so they also agree with it — which matters for the
    diarizer, whose output is not bit-identical from run to run on a GPU.
    """
    cache_dir, counter = arena
    assert _run(3, cache_dir, counter, "a1b2c3d4", nap=0.6) == 1


def test_different_audio_is_a_different_entry(arena) -> None:
    """Content addressing: the single-flight does not merge unrelated files.

    The property that already held, kept because the fix had every chance to
    break it: a ledger keyed on the namespace alone would pass the test above
    and return one file's captions for another's.
    """
    cache_dir, counter = arena
    assert _run(1, cache_dir, counter, "aaaaaaaa", nap=0.0) == 1
    assert _run(1, cache_dir, counter, "bbbbbbbb", nap=0.0) == 2


def test_the_transcription_survives_the_process_that_made_it(arena) -> None:
    """Persistence: a second process reuses the first one's result."""
    cache_dir, counter = arena
    assert _run(1, cache_dir, counter, "deadbeef", nap=0.0) == 1
    assert _run(1, cache_dir, counter, "deadbeef", nap=0.0) == 1


def test_the_same_bytes_at_a_different_path_still_hit(tmp_path) -> None:
    """The key is the audio's content, not where the audio happens to live.

    Asserted at the tools' own ``_cache_key``, because this is the property
    their whole caching rests on and the one that is easiest to lose: the file
    they key on is a WAV extracted into a fresh temporary directory, so its
    *path* is different on every run and keying on it would mean never hitting
    at all.
    """
    import captions_from_whisper as cfw
    import diarize_from_nemo as dn

    first = tmp_path / "a.wav"
    second = tmp_path / "elsewhere" / "b.wav"
    second.parent.mkdir()
    first.write_bytes(b"RIFF....the same bytes")
    second.write_bytes(b"RIFF....the same bytes")
    third = tmp_path / "c.wav"
    third.write_bytes(b"RIFF....different bytes")

    assert cfw._cache_key(first.read_bytes(), "m", "en", "vtt", "") == cfw._cache_key(
        second.read_bytes(), "m", "en", "vtt", ""
    )
    assert cfw._cache_key(first.read_bytes(), "m", "en", "vtt", "") != cfw._cache_key(
        third.read_bytes(), "m", "en", "vtt", ""
    )
    assert dn._cache_key(first.read_bytes(), "sortformer", 0) == dn._cache_key(
        second.read_bytes(), "sortformer", 0
    )
    assert dn._cache_key(first.read_bytes(), "sortformer", 0) != dn._cache_key(
        third.read_bytes(), "sortformer", 0
    )


def test_processes_creating_the_ledger_at_once_all_succeed(tmp_path) -> None:
    """The creation race, which cost a sibling repository a red run.

    ``SqliteLedger`` collides with itself at construction: several processes
    released onto the same missing database file raise ``sqlite3.
    OperationalError: database is locked`` from inside its own ``PRAGMA
    journal_mode=WAL`` — the statement that makes concurrent use possible is
    not itself safe on a file nobody has created yet. Reproduced at 6
    processes behind a barrier: two rounds in six. ``_ledger`` retries, and
    this is the test that its budget is enough.
    """
    cache_dir = tmp_path / "cold"
    cache_dir.mkdir()
    counter = tmp_path / "calls.txt"
    # No `wallet_for` first: the children race to create the database.
    assert _run(4, cache_dir, counter, "c0ffee00", nap=0.2) == 1


def test_a_refused_sqlite_store_degrades_instead_of_raising(tmp_path, monkeypatch) -> None:
    """When the SQLite store cannot be opened at all, the tool still answers.

    The deterministic twin of the test above: the race is timing-dependent and
    the fallback is not, so the fallback is asserted by refusing every attempt
    rather than by hoping a lock lands. What is lost is cross-process
    single-flight; what is kept is the memoization and the result.
    """
    import sqlite3

    import _wallet

    def always_locked(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("wallet_helper.sqlite_ledger.SqliteLedger", always_locked)
    monkeypatch.setattr(_wallet, "OPEN_ATTEMPTS", 2)
    monkeypatch.setattr(_wallet, "OPEN_BACKOFF", 0.0)
    monkeypatch.setattr(_wallet, "_WALLETS", {})

    runs: list[int] = []

    def work() -> str:
        runs.append(1)
        return "answered anyway"

    assert memoized("guard", "fallback", work, cache_dir=tmp_path) == "answered anyway"
    assert memoized("guard", "fallback", work, cache_dir=tmp_path) == "answered anyway"
    assert len(runs) == 1, "the JSON fallback still has to memoize"


def test_without_wallet_helper_the_work_still_happens(tmp_path, monkeypatch) -> None:
    """A missing helper degrades to an uncached call, not to an ImportError.

    Asserted by blocking the import rather than by uninstalling anything, so
    it says the same thing in a full environment and in a bare one — which is
    this package's whole CI arrangement.
    """
    import builtins

    import _wallet

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("wallet_helper"):
            raise ImportError("No module named 'wallet_helper'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    monkeypatch.setattr(_wallet, "_WALLETS", {})
    monkeypatch.setattr(_wallet, "_WARNED_MISSING", False)

    runs: list[int] = []

    def work() -> str:
        runs.append(1)
        return "uncached but answered"

    assert memoized("guard", "nohelper", work, cache_dir=tmp_path) == "uncached but answered"
    # Twice, because the degradation is "no cache", and a silent cache that
    # returns the first answer forever would be the worse failure.
    assert memoized("guard", "nohelper", work, cache_dir=tmp_path) == "uncached but answered"
    assert len(runs) == 2
