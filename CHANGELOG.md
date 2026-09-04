# Changelog: sprezzature-audio

## Unreleased

### Fixed

- `translate_captions.py` and `name_from_transcript.py` imported `best_engine_ai_helper.llm.chat` at module level, even though `best-engine-ai-helper` is only declared in the `translate` extra, not a base dependency. `pip install sprezzature-audio` with no extras broke both scripts' `--help` with a `ModuleNotFoundError`, before argument parsing even ran. The import now happens inside the function that needs it, matching the deferred-import policy every other script in this project already follows for NeMo, pywhispercpp, and numpy.
- `diarize_from_nemo.py`, `_normalise_predictions`: `nemo_toolkit` 2.4.0's `SortformerEncLabelModel.diarize` can return a third output shape (a compact `"0.000 5.840 speaker_0"` string form, distinct from both the RTTM-line and nested-tuple shapes already handled) that fell through every branch and was silently dropped. Running the diarization step against a real two-speaker recording on `nemo_toolkit` 2.4.0 produced this shape and printed "0 turn(s), 0 speaker(s)" on real speech, with no error. Added a third branch that parses it; verified against the same real output, now correctly producing 4 turns / 2 speakers matching the known ground truth.
- `caption_diarize.py`: its own Click command was hardcoded as `"sprezzature-audio-caption-diarize"`, a name nothing installs; `pyproject.toml` registers this script as `sprezzature-audio-pipeline`. Every other script's hardcoded name already matched its console-script entry; this one didn't, so its `--help` usage line and every epilog example command were unrunnable (`command not found`). Fixed to match, and added a regression test (`test_click_command_name_matches_its_installed_console_script`) parametrized over all six console scripts so this class of drift cannot recur silently.
- README.md's and LISEZMOI.md's "Quick start" sections showed `python scripts/caption_diarize.py meeting.mp4`, implying the combined pipeline takes a media file directly. It does not: `--captions` and `--diarization` are both required options pointing at files the two upstream steps must already have produced. Running the example as written fails immediately with `Error: Missing option '--captions'`. Fixed to show the real three-command sequence, matching what EXAMPLES.md's own "Full pipeline" section already correctly showed.

### Changed

- `translate_captions.py` and `name_from_transcript.py` now call `best_engine_ai_helper.llm.chat()` instead of the earlier `sprezzature_local` client. The LLM endpoint and model are still configured via the `SPREZZATURE_LLM_*` environment variables; only the package that implements the call changed.
- The `scripts/` package installs under the `sprezzature_audio_scripts` distribution name, so it no longer collides with the `scripts` package of sibling `sprezzature-*` repositories on `pip install`. The console-script names (`sprezzature-audio-captions`, `sprezzature-audio-diarize`, and so on) are unchanged.

### Added

- `tests/test_scripts.py`: grew from 7 to 76 tests across two prior passes plus this one, covering every previously-untested pure function in `caption_diarize.py`, `diarize_from_nemo.py`, `name_from_transcript.py`, `translate_captions.py`, `identify_from_titanet.py`, `_vocab.py`, `_argparse.py`, and `_click.py`, plus regression tests for the two functional bugs above (the NeMo third output shape, the `caption_diarize.py` prog-name mismatch).

## v1.0.0 (2026-07-29)

Initial standalone release, extracted from the `sprezzature` monorepo.

### Scripts included

- `captions_from_whisper.py`: WebVTT / SRT / plain transcript via local Whisper (vocal-helper backend).
- `diarize_from_nemo.py`: RTTM + JSON turns via NeMo Sortformer.
- `identify_from_titanet.py`: Speaker identity verification via NeMo TitaNet.
- `caption_diarize.py`: Combined captioning + diarization pipeline.
- `name_from_transcript.py`: Speaker name inference (regex pass + optional LLM pass).
- `translate_captions.py`: VTT/SRT translation via a local LLM.
- `install_captions.py`: Pre-download Whisper GGML weights.
- `install_diarize.py`: Pre-download NeMo Sortformer and TitaNet checkpoints.
- `_argparse.py`, `_click.py`, `_lang.py`, `_vocab.py`: Shared helpers.
