# Changelog: sprezzature-audio

## Unreleased

### Changed

- `translate_captions.py` and `name_from_transcript.py` now call `best_engine_ai_helper.llm.chat()` instead of the earlier `sprezzature_local` client. The LLM endpoint and model are still configured via the `SPREZZATURE_LLM_*` environment variables; only the package that implements the call changed.
- The `scripts/` package installs under the `sprezzature_audio_scripts` distribution name, so it no longer collides with the `scripts` package of sibling `sprezzature-*` repositories on `pip install`. The console-script names (`sprezzature-audio-captions`, `sprezzature-audio-diarize`, and so on) are unchanged.

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
