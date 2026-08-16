# sprezzature-audio

Local-first speech processing for the [sprezzature](https://harchaoui.org/warith/sprezzature/) stack.

Point it at a recording (a meeting, an interview, a lecture) and it hands back a transcript that says not just *what* was said, but *who* said it and *in which language*. Everything runs on your own machine: no audio leaves it, and no API key is needed. If you instead need to cut, resample, or clean up the audio signal itself (trim silence, separate a voice from background music), that is a different job, handled by a sibling package, [audio-helper](https://github.com/warith-harchaoui/audio-helper); this package starts once the audio is already usable and asks what was said in it.

## What it does

Six scripts, each one stage of the pipeline. A few terms recur throughout the table below, so here they are once, up front, rather than repeated at every mention:

- **ASR** (automatic speech recognition) is the technical name for speech-to-text: turning a sound wave into written words.
- **WebVTT** and **SRT** are two competing plain-text file formats for storing subtitles: a list of `[start time, end time, text]` triples. WebVTT is the web-standard one (what a `<video>` tag expects); SRT is older and more universally supported by video players.
- **RTTM** is a plain-text format from the speech-research world for recording *who spoke when*: one line per speaker turn, with a start time, a duration, and a speaker label.
- **NeMo** is NVIDIA's open-source toolkit for speech models; **Sortformer** and **TitaNet** are two specific NeMo models used here (diarization and speaker fingerprinting, explained below).

| Script | What it produces |
|---|---|
| `captions_from_whisper.py` | WebVTT, SRT, or a plain transcript, via a local Whisper model (through `vocal-helper`) |
| `diarize_from_nemo.py` | An RTTM file plus a JSON turn list, via NeMo's Sortformer model (up to 4 speakers) |
| `identify_from_titanet.py` | A speaker's identity, matched against a reference voice sample, via NeMo's TitaNet model |
| `caption_diarize.py` | The combined pipeline: transcript and speaker turns merged in one pass |
| `name_from_transcript.py` | A guess at each speaker's real name, read off the diarized transcript (pattern matching, with an optional LLM assist) |
| `translate_captions.py` | A translated copy of a VTT/SRT file, via a local LLM |

## Install

```sh
# Base (no ML dependencies)
pip install sprezzature-audio

# Add captioning (Whisper via vocal-helper)
pip install "sprezzature-audio[captions]"

# Add diarization and speaker ID (NeMo; install torch first, since the right
# build depends on your hardware: CUDA, Apple-silicon MPS, or plain CPU)
pip install torch
pip install "sprezzature-audio[diarize]"

# Add LLM translation (best-engine-ai-helper + a local Ollama server)
pip install "sprezzature-audio[translate]"

# Everything
pip install "sprezzature-audio[all]"
```

## Quick start

```sh
# Transcribe a video to WebVTT
python scripts/captions_from_whisper.py talk.mp4

# Same, as a plain-text transcript
python scripts/captions_from_whisper.py podcast.mp3 --format text

# Diarize an audio file: who spoke when
python scripts/diarize_from_nemo.py interview.wav

# Full pipeline: transcript and speaker labels in one shot
python scripts/caption_diarize.py meeting.mp4

# Guess speaker names from the diarized transcript
python scripts/name_from_transcript.py meeting.speakers.vtt

# Translate captions to French
python scripts/translate_captions.py talk.vtt --lang fr
```

## How this differs from audio-helper

`audio-helper` works at the **signal level**: converting formats, slicing a waveform, resampling, separating a voice from background music with Demucs. It has no notion of words; a silence and a sentence look the same to it.

`sprezzature-audio` works at the **content level**: it reads speech, attributes it to a speaker, and translates it. The two packages are meant to be used together, not as alternatives; `captions_from_whisper.py` in fact calls `audio-helper` internally, to extract a 16 kHz mono WAV file (the format Whisper expects) before it ever runs the speech model.

## Models used

| Task | Model | Backend |
|---|---|---|
| ASR (speech to text) | `large-v3-turbo` by default, or any other GGML-format Whisper weights (the compact file format `vocal-helper`'s underlying engine, whisper.cpp, expects) | vocal-helper / pywhispercpp |
| Diarization (who spoke when) | `nvidia/diar_sortformer_4spk-v1` | NeMo |
| Speaker ID (matching a voice to a reference sample) | `nvidia/speakerverification_en_titanet_large` | NeMo |
| Translation | Configured through the `SPREZZATURE_LLM_*` environment variables | best-engine-ai-helper |

## Environment variables

| Variable | Purpose |
|---|---|
| `SPREZZATURE_WHISPER_MODEL` | Override the Whisper model path or alias |
| `SPREZZATURE_CACHE_DIR` | Cache directory for Whisper weights and transcripts |
| `SPREZZATURE_NO_CACHE` | Set to any value to disable the transcript cache |
| `NEMO_DIAR_MODEL` | Override the NeMo diarization checkpoint |
| `SPREZZATURE_LLM_*` | LLM backend configuration (see best-engine-ai-helper) |

## License

BSD 3-Clause. See [LICENSE](https://github.com/warith-harchaoui/sprezzature-audio/blob/main/LICENSE).

## Author

Warith Harchaoui: [harchaoui.org/warith](https://harchaoui.org/warith/)
