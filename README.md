# sprezzature-audio

Local-first speech processing for the [sprezzature](https://sprezzature.ai/) stack.

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
| `audit_captions.py` | What is wrong with a caption track: reading speed, overlaps, line width, duration |

And the other direction — text back into sound, because that is the same
modality read backwards. A narration lands as a WAV plus a WebVTT, exactly
like a transcript does, so a page can follow the reading sentence by
sentence.

| Script | What it produces |
|---|---|
| `narrate_kokoro.py` | A narrated WAV and its cues, from 54 built-in voices in nine languages. **The default.** |
| `narrate_openvoice.py` | The same, in a voice cloned from a 6–30 s sample |
| `narrate_chatterbox.py` | The same, with emotion and intensity hints the model can act on |
| `pick_voice.py` | A one-line demo clip per voice, so a narrator is chosen by listening |
| `install_narrate.py` | The checkpoints each engine needs |

Nobody passes a language. `narrate_kokoro.py` reads the text, detects the
language, and picks the voice that speaks it — which matters more than it
sounds: the detected language is what the phonemiser works from, so French
read as English is not French in an American accent, it is an American
spelling the words out.

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

# Add narration. No torch: Kokoro is 82 M parameters through ONNX Runtime,
# Apache-2.0 in code and weights. espeak-ng is the one half pip cannot
# supply — `brew install espeak-ng`, or `apt install espeak-ng`.
pip install "sprezzature-audio[narrate]"
sprezzature-audio-install-voice --engine kokoro

# French, natively. Kyutai's tts-1.6b-en_fr comes from a Paris lab, where the
# other three reach French through an English-first pipeline; on a Mac it runs
# through Kyutai's own MLX build. An extra rather than the default because its
# weights are CC-BY-4.0, not Apache-2.0 — permissive, and not the same promise.
pip install "sprezzature-audio[narrate-kyutai]"

# The cloning engines, if you want to sound like a particular person rather
# than to have a page read aloud. These are the ones that pull torch.
pip install "sprezzature-audio[narrate-openvoice]"
pip install "sprezzature-audio[narrate-chatterbox]"

# Everything
pip install "sprezzature-audio[all]"
```

## Quick start

Fifteen tools ship here, each with its own command — which is what a script
should call. The two front doors are how you find them:

```sh
make-audio --help          # argparse: the catalogue, with a line per tool
sprezzature-audio --help   # click: the same fifteen, the other parser

make-audio audit subtitles.vtt
make-audio narrate post.md --out post.mp3
```

Every argument after the tool name belongs to that tool, so
`make-audio captions --help` shows the transcription flags, not these.

```sh
# Transcribe a video to WebVTT
sprezzature-audio-captions talk.mp4

# Same, as a plain-text transcript
sprezzature-audio-captions podcast.mp3 --format text

# Diarize an audio file: who spoke when
sprezzature-audio-diarize interview.wav

# Full pipeline: caption_diarize.py merges caption + diarization files
# already produced by the two steps above (it takes no media file itself)
sprezzature-audio-captions meeting.mp4
sprezzature-audio-diarize meeting.mp4
sprezzature-audio-pipeline --captions meeting.vtt --diarization meeting.diarization.json

# Guess speaker names from the diarized transcript
sprezzature-audio-name meeting.speakers.vtt

# Translate captions to French
sprezzature-audio-translate talk.vtt --lang fr
```

## As a library

`import sprezzature_audio` hands back the engine, not a version string. What
is importable with **no extras at all** is everything that needs no model —
the same set the HTTP API serves, and for the same reason: it is fast and
pure.

```python
import sprezzature_audio as audio

cues = audio.parse(open("talk.vtt").read())
for finding in audio.audit_cues(cues):      # too fast, too short, too wide
    print(finding)

print(audio.write_srt(cues))                # VTT -> SRT, same reader
print(audio.word_error_rate(reference, hypothesis)["wer"])
print(audio.describe_device())              # which accelerator this host uses
```

The model-backed half resolves on first use, so the import above costs
nothing even on a machine with Whisper, NeMo and Kokoro installed:

```python
audio.synthesise(...)      # [narrate]  — Kokoro
audio.transcribe(...)      # [captions] — Whisper
audio.diarize(...)         # [diarize]  — NeMo Sortformer
audio.translate_cues(...)  # [translate]
```

Ask for one without its extra and the error names the `pip install` that
fixes *that* tool, not the package in general.

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

Warith HARCHAOUI: [deraison.ai](https://deraison.ai/)
