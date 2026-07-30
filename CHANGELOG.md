# Changelog -- sprezzature-audio

## v1.0.0 (2026-07-29)

Initial standalone release, extracted from the `sprezzature` monorepo.

### Scripts included

- `captions_from_whisper.py` -- WebVTT / SRT / plain transcript via local Whisper (vocal-helper backend).
- `diarize_from_nemo.py` -- RTTM + JSON turns via NeMo Sortformer.
- `identify_from_titanet.py` -- Speaker identity verification via NeMo TitaNet.
- `caption_diarize.py` -- Combined captioning + diarization pipeline.
- `name_from_transcript.py` -- Speaker name inference (regex pass + optional LLM pass).
- `translate_captions.py` -- VTT/SRT translation via sprezzature-local LLM.
- `install_captions.py` -- Pre-download Whisper GGML weights.
- `install_diarize.py` -- Pre-download NeMo Sortformer and TitaNet checkpoints.
- `_argparse.py`, `_click.py`, `_lang.py`, `_vocab.py` -- Shared helpers.

### Architecture change

`translate_captions.py` and `name_from_transcript.py` now call `sprezzature_local.llm.chat()` instead of the old direct Ollama HTTP client. The LLM endpoint is configured via `SPREZZATURE_LLM_*` env vars.
