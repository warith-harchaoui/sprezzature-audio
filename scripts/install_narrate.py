#!/usr/bin/env python3
"""
install_narrate
===============

One-stop install / model-pull helper for the narration engines
(``openvoice``, ``chatterbox``). Mirrors the pattern of
``install_alt_ai.py`` and ``install_captions.py`` from sprezzature-accessibility:
the script does the boring downloads so the user does not have to
read the upstream README.

What it does, per engine
------------------------
``openvoice``
    1. Verifies the package is importable (``pip install`` instructions
       on the bare-machine path).
    2. Downloads the OpenVoice v2 base-speaker and tone-converter
       checkpoints from the official release artifact into
       ``~/.cache/sprezzature-skill/openvoice/``.
    3. Writes a tiny ``config.json`` pointing at the local files so
       ``narrate_openvoice.py`` finds them.

``chatterbox``
    1. Verifies the package is importable.
    2. Triggers the model's lazy ``from_pretrained`` so the
       Hugging Face weights cache (under ``~/.cache/huggingface/``)
       is populated.
    3. Creates the voices library directory
       ``~/.cache/sprezzature-skill/chatterbox/voices/`` ready to receive
       custom WAVs for built-in-by-filename voice selection.

The script never installs the heavy ML library itself — pip is the
canonical channel and we don't want to wrap it. Install with:

::

    pip install -r requirements-narrate-openvoice.txt
    # or
    pip install -r requirements-narrate-chatterbox.txt

Then run:

::

    sprezzature-audio-install-voice --engine openvoice
    sprezzature-audio-install-voice --engine chatterbox

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import zipfile
from pathlib import Path

# ── Module-level configuration ──────────────────────────────────────────────

#: Where engine checkpoints / configs live, per-user. Mirrors the
#: ``~/.cache/sprezzature-skill/`` convention used by alt_from_ollama.
CACHE_ROOT: Path = Path.home() / ".cache" / "sprezzature-skill"

#: OpenVoice v2 checkpoint bundle. Tagged stable release on GitHub.
#: Kept as a single configurable URL so the maintainer can pin a new
#: version without editing logic.
OPENVOICE_CHECKPOINT_URL: str = (
    "https://myshell-public-repo-host.s3.amazonaws.com/openvoice/"
    "checkpoints_v2_0417.zip"
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _download(url: str, dest: Path) -> None:
    """
    Download ``url`` to ``dest``, resuming a partial transfer rather than
    restarting it.

    Through ``os_helper.download_file``, which is this suite's one download
    primitive: bytes accumulate in a ``<dest>.part`` sidecar, an interrupted
    transfer is continued with an HTTP ``Range`` request, transient failures
    are retried with exponential backoff, and only a *finished* sidecar is
    renamed onto ``dest``.

    That last property is the reason this stopped being a hand-rolled loop.
    The Kokoro graph below is 325 MB and the loop wrote straight into
    ``dest``: a dropped connection left a short file that exists, the only
    thing telling it apart from a good one was the byte count hardcoded in
    :data:`KOKORO_FILES`, and the repair was the whole 325 MB again from zero.
    Resuming is the difference between finishing on a bad connection and
    never finishing on one.

    ``check_url=False`` is deliberate, and measured. ``download_file``'s
    precondition is ``os_helper.is_working_url``, which answers **False** for
    both Kokoro URLs: it probes with ``requests.head``, whose default is
    ``allow_redirects=False``, and a GitHub release asset answers 302 towards
    the CDN — a followed HEAD on each returns 200 with the right
    ``Content-Length``. Leaving the precondition on would assert away the two
    downloads that work.

    (It also answers False for :data:`OPENVOICE_CHECKPOINT_URL`, and there it
    is right for a different reason: that S3 object is a plain 404 today, with
    or without redirects. Separate problem, upstream, and not one a
    precondition would have fixed — it would only have renamed the failure.)

    ``overwrite=True`` because the callers below have already decided to
    fetch — ``install_kokoro`` calls this precisely when the file on disk is
    the wrong size, and the idempotent fast path would hand that wrong file
    back.
    """
    try:
        from os_helper import download_file
    except ImportError as exc:
        raise RuntimeError(
            "os-helper is missing, so there is no resumable download. It comes "
            "with any of the narration extras:\n"
            "    pip install 'sprezzature-audio[narrate]'"
        ) from exc

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"→ downloading {url}")
    print(f"  into {dest}")
    # progress=True draws a tqdm bar on a terminal and suppresses itself off
    # one, which is the other thing the old loop got wrong: its `\r`
    # percentage line wrote one record per megabyte into a CI log.
    download_file(
        url,
        str(dest),
        check_url=False,
        resume=True,
        retries=3,
        overwrite=True,
        progress=True,
    )


def _check_importable(modules: tuple[str, ...]) -> bool:
    """Return True iff every ``modules`` entry imports cleanly."""
    for name in modules:
        try:
            importlib.import_module(name)
        except ImportError:
            return False
    return True


# ── OpenVoice v2 installer ─────────────────────────────────────────────────

def install_openvoice() -> int:
    """
    Download OpenVoice v2 checkpoints into the local cache.

    Returns
    -------
    int
        ``0`` on success; ``1`` when the package isn't installed yet
        (the script prints the pip command and exits).
    """
    if not _check_importable(("openvoice",)):
        print(
            "openvoice not installed. From a wheel:\n"
            "    pip install 'sprezzature-audio[narrate-openvoice]'\n"
            "From a clone:\n"
            "    pip install -r requirements-narrate-openvoice.txt",
            file=sys.stderr,
        )
        return 1

    target_dir: Path = CACHE_ROOT / "openvoice"
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path: Path = target_dir / "checkpoints_v2.zip"

    if not zip_path.is_file():
        _download(OPENVOICE_CHECKPOINT_URL, zip_path)
    else:
        print(f"→ checkpoint archive already present: {zip_path}")

    extract_dir: Path = target_dir / "checkpoints"
    if not extract_dir.is_dir():
        print(f"→ extracting into {extract_dir}")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
    else:
        print(f"→ checkpoints already extracted: {extract_dir}")

    # The exact directory layout of the OpenVoice v2 zip is documented
    # in the upstream README; we point the wrapper config at the
    # canonical filenames.
    base_speakers_dir: Path = extract_dir / "checkpoints_v2" / "base_speakers" / "ses"
    converter_ckpt: Path = (
        extract_dir / "checkpoints_v2" / "converter" / "checkpoint.pth"
    )
    config: dict[str, object] = {
        "device": "cpu",
        "default_language": "English",
        "base_speakers_dir": str(base_speakers_dir),
        "converter_ckpt": str(converter_ckpt),
        "default_source_se": str(base_speakers_dir / "en-default.pth"),
        "sdp_ratio": 0.2,
        "tau": 0.3,
    }
    (target_dir / "config.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8",
    )
    print(f"✓ openvoice ready (config: {target_dir / 'config.json'})")
    return 0


# ── ChatterboxTTS installer ────────────────────────────────────────────────

def install_chatterbox() -> int:
    """
    Trigger ChatterboxTTS' lazy weight pull + set up the voices dir.

    Returns
    -------
    int
        ``0`` on success; ``1`` when the package isn't installed yet.
    """
    try:
        mod = importlib.import_module("chatterbox.tts")
    except ImportError:
        try:
            mod = importlib.import_module("chatterbox_tts")
        except ImportError:
            print(
                "chatterbox-tts not installed. From a wheel:\n"
                "    pip install 'sprezzature-audio[narrate-chatterbox]'\n"
                "From a clone:\n"
                "    pip install -r requirements-narrate-chatterbox.txt",
                file=sys.stderr,
            )
            return 1

    target_dir: Path = CACHE_ROOT / "chatterbox" / "voices"
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"→ voices library: {target_dir}")
    print("  drop custom WAVs here to use them as --voice <filename-no-ext>")

    # Trigger the lazy download. ``from_pretrained`` populates
    # ~/.cache/huggingface and prints HF's own progress.
    print("→ pulling ChatterboxTTS weights (first time only, ~1 GB)")
    mod.ChatterboxTTS.from_pretrained(device="cpu")
    print("✓ chatterbox ready")
    return 0


# ── Kokoro ─────────────────────────────────────────────────────────────────

#: The ONNX graph and the voice bank, from the kokoro-onnx release that
#: publishes them. Pinned to a tagged release rather than a floating "latest"
#: so two machines installing a week apart get the same narrator.
KOKORO_RELEASE: str = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)
KOKORO_FILES: tuple[tuple[str, int], ...] = (
    ("kokoro-v1.0.onnx", 325_532_387),
    ("voices-v1.0.bin", 28_214_398),
)


def install_kokoro() -> int:
    """
    Fetch Kokoro's two model files into the cache.

    Returns
    -------
    int
        ``0`` on success; ``1`` when the package isn't installed yet.

    Unlike the other two engines this one has nothing lazy to trigger:
    kokoro-onnx is handed the paths to its files, so if they are not on disk
    nothing downloads them later. Which is the better arrangement — the wait
    happens here, where the command is named "install", instead of in the
    middle of the first narration.

    Already-downloaded files are skipped by size. The size check used to be
    the only thing standing between a dropped connection and a short file
    trusted forever; :func:`_download` now writes through a sidecar and
    renames only a finished one, so a truncated file can no longer appear
    here at all. What the check still catches is the other case — a file of
    the wrong length because the upstream release was re-tagged under the
    same name — and re-running the command then replaces it.
    """
    if not _check_importable(("kokoro_onnx",)):
        print(
            "kokoro-onnx not installed. From a wheel:\n"
            "    pip install 'sprezzature-audio[narrate]'\n"
            "From a clone:\n"
            "    pip install -r requirements-narrate-kokoro.txt",
            file=sys.stderr,
        )
        return 1

    target_dir: Path = CACHE_ROOT / "kokoro"
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename, expected_bytes in KOKORO_FILES:
        dest = target_dir / filename
        if dest.is_file() and dest.stat().st_size == expected_bytes:
            print(f"✓ {filename} already here")
            continue
        if dest.is_file():
            print(
                f"→ {filename} is {dest.stat().st_size} bytes, expected "
                f"{expected_bytes} — downloading again"
            )
        _download(f"{KOKORO_RELEASE}/{filename}", dest)
        if dest.stat().st_size != expected_bytes:
            print(
                f"FAIL {filename} downloaded {dest.stat().st_size} bytes, "
                f"expected {expected_bytes}",
                file=sys.stderr,
            )
            return 1

    # espeak-ng is the half pip cannot supply. Kokoro phonemises through it,
    # and the copy inside the `espeakng-loader` wheel does not find its own
    # data on macOS — it resolves to the CI runner's home directory and the
    # process dies from C with no traceback. Saying so here, while the person
    # is still at the install step, is cheaper than letting them meet that
    # message during a narration.
    if not _espeak_is_usable():
        print(
            "→ no system espeak-ng found. Kokoro needs it to turn text into "
            "phonemes.\n"
            "    macOS:         brew install espeak-ng\n"
            "    Debian/Ubuntu: sudo apt install espeak-ng",
            file=sys.stderr,
        )
        return 1

    print("✓ kokoro ready")
    return 0


def _espeak_is_usable() -> bool:
    """Whether a system espeak-ng with readable data is installed."""
    for prefix in (Path("/opt/homebrew"), Path("/usr/local"), Path("/usr")):
        libraries = (
            prefix / "lib" / "libespeak-ng.dylib",
            prefix / "lib" / "libespeak-ng.so",
        )
        data = prefix / "share" / "espeak-ng-data"
        if any(lib.is_file() for lib in libraries) and (data / "phontab").is_file():
            return True
    return False


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Parse the command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="sprezzature-audio-install-voice",
        description=(
            "Download model checkpoints for the narration engines "
            "(kokoro, openvoice, chatterbox). The Python packages themselves "
            "are installed via pip — see the per-engine requirements "
            "files in ."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--engine",
        choices=("kokoro", "openvoice", "chatterbox", "all"),
        default="all",
        help="Engine to install (default: all).",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    engines = (
        ("kokoro", "openvoice", "chatterbox")
        if args.engine == "all" else (args.engine,)
    )
    installers = {
        "kokoro": install_kokoro,
        "openvoice": install_openvoice,
        "chatterbox": install_chatterbox,
    }
    failed: int = 0
    for engine in engines:
        failed += installers[engine]()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
