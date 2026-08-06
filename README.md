# sprezzature-audio

Local-first speech processing for the [sprezzature](https://harchaoui.org/warith/sprezzature/) stack.

This package handles **what was said, by whom, and in which language** -- it does not process audio files at the signal level. For format conversion, waveform slicing, and source separation, see [audio-helper](https://github.com/warith-harchaoui/audio-helper).

## What it does

| Script | What it produces |
|---|---|
| `captions_from_whisper.py` | WebVTT / SRT / plain transcript via local Whisper (vocal-helper) |
| `diarize_from_nemo.py` | RTTM + JSON turn list via NeMo Sortformer (up to 4 speakers) |
| `identify_from_titanet.py` | Speaker identity from a voice sample via NeMo TitaNet |
| `caption_diarize.py` | Combined pipeline: captions + diarization in one pass |
| `name_from_transcript.py` | Guess speaker names from diarized transcript (regex + optional LLM) |
| `translate_captions.py` | Translate a VTT/SRT file to another language via local LLM |

All heavy inference runs on-device. No cloud. No API key.

## Install

```sh
# Base (no ML)
pip install sprezzature-audio

# Add captioning (Whisper via vocal-helper)
pip install "sprezzature-audio[captions]"

# Add diarization and speaker ID (NeMo -- torch required first)
pip install torch  # pick CUDA / MPS / CPU build for your machine
pip install "sprezzature-audio[diarize]"

# Add LLM translation (best-engine-ai-helper + ollama)
pip install "sprezzature-audio[translate]"

# Everything
pip install "sprezzature-audio[all]"
```

## Quick start

```sh
# Transcribe a video to WebVTT
python scripts/captions_from_whisper.py talk.mp4

# Same, plain text output
python scripts/captions_from_whisper.py podcast.mp3 --format text

# Diarize an audio file (who spoke when)
python scripts/diarize_from_nemo.py interview.wav

# Full pipeline: captions + speaker labels in one shot
python scripts/caption_diarize.py meeting.mp4

# Guess speaker names from the diarized transcript
python scripts/name_from_transcript.py meeting.speakers.vtt

# Translate captions to French
python scripts/translate_captions.py talk.vtt --lang fr
```

## The distinction from audio-helper

`audio-helper` operates at the **signal level**: it converts formats, slices waveforms, resamples, and separates sources with Demucs. It does not know words.

`sprezzature-audio` operates at the **content level**: it reads speech, attributes it to speakers, and translates it. The two packages complement each other; `captions_from_whisper.py` uses `audio-helper` internally to extract a 16 kHz mono WAV before invoking Whisper.

## Models used

| Task | Model | Backend |
|---|---|---|
| ASR | `large-v3-turbo` (default) or any GGML alias | vocal-helper / pywhispercpp |
| Diarization | `nvidia/diar_sortformer_4spk-v1` | NeMo |
| Speaker ID | `nvidia/speakerverification_en_titanet_large` | NeMo |
| Translation | Configured via `SPREZZATURE_LLM_*` env vars | best-engine-ai-helper |

## Environment variables

| Variable | Purpose |
|---|---|
| `SPREZZATURE_WHISPER_MODEL` | Override the Whisper model path or alias |
| `SPREZZATURE_CACHE_DIR` | Cache directory for Whisper weights and transcripts |
| `SPREZZATURE_NO_CACHE` | Set to any value to disable the transcript cache |
| `NEMO_DIAR_MODEL` | Override the NeMo diarization checkpoint |
| `SPREZZATURE_LLM_*` | LLM backend config (see best-engine-ai-helper) |

## License

BSD 3-Clause. See [LICENSE](https://github.com/warith-harchaoui/sprezzature-audio/blob/main/LICENSE).

## Author

Warith Harchaoui -- [harchaoui.org/warith](https://harchaoui.org/warith/)
