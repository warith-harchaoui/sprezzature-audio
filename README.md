# sprezzature-audio

Local-first speech processing for the [sprezzature](https://sprezzature.ai/) stack.

Point it at a recording (a meeting, an interview, a lecture) and it hands back a transcript that says not just *what* was said, but *who* said it and *in which language*. It also works the other way: a page of text becomes a narration with its timed track. Everything runs on your own machine: no audio leaves it, and no API key is needed. If you instead need to cut, resample, or clean up the audio signal itself (trim silence, separate a voice from background music), that is a different job, handled by a sibling package, [audio-helper](https://github.com/warith-harchaoui/audio-helper); this package starts once the audio is already usable and asks what was said in it.

## How it works

![Flow diagram. At the top, a recording or a page of text feeds two lanes. The left lane turns sound into text: it transcribes with a local Whisper build, says who spoke when with NeMo Sortformer, names the speakers against a reference voice, and translates, returning WebVTT, SRT or a plain transcript. The right lane turns text into sound: it detects the language, picks the voice that speaks it, measures each audio file and cuts the cues, returning a WAV and its WebVTT. Both meet in one outcome, the same audit of the cue track whichever direction wrote it.](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-audio/main/assets/how-it-works.svg)

## What it does

Fifteen tools. Each one is its own command, and each one is also a sub-command of the front door `sprezzature-audio` (alias `make-audio`). A few terms recur in the tables below, so here they are once:

- **ASR** (automatic speech recognition) is the technical name for speech-to-text: turning a sound wave into written words.
- **WebVTT** and **SRT** are two plain-text file formats for subtitles: a list of `[start time, end time, text]` triples. WebVTT is the web standard (what a `<video>` tag expects); SRT is older and read by more video players.
- **RTTM** (Rich Transcription Time Marked) is a plain-text format from speech research for recording *who spoke when*: one line per speaker turn, with a start time, a duration and a speaker label.
- **Diarization** is the step that marks who spoke when, without knowing anyone's name.
- **NeMo** is NVIDIA's open-source toolkit for speech models; **Sortformer** (diarization) and **TitaNet** (voice fingerprints) are two NeMo models used here.
- **WER** (word error rate), **DER** (diarization error rate) and **RTF** (real-time factor: processing time divided by audio duration) are the three measurements `benchmark` reports.

### From speech to text

| Command | Front door | What it produces |
|---|---|---|
| `sprezzature-audio-captions` | `captions` | WebVTT, SRT or a plain transcript of an audio or video file, through a local Whisper model (`vocal-helper`, over whisper.cpp). Vocabulary biasing with `--prompt`, `--vocab`, `--vocab-from`, `--auto-project`. |
| `sprezzature-audio-diarize` | `diarize` | An RTTM file and a `.diarization.json` turn list, through NeMo Sortformer (a checkpoint built for up to 4 speakers). |
| `sprezzature-audio-identify` | `identify` | A `.speakers.json` that maps each diarized speaker to a name, by matching TitaNet embeddings against a folder of reference WAVs (`--refs`, one file per known speaker). |
| `sprezzature-audio-pipeline` | `pipeline` | A speaker-labelled WebVTT, SRT or plain text, merged from a caption file and a `.diarization.json` already on disk (and optionally a `.speakers.json`). It takes no media file. |
| `sprezzature-audio-name` | `name` | A `speakers.json` guessed from the transcript itself: self-introduction and vocative patterns, plus a local-model pass when `--ollama` is given. |
| `sprezzature-audio-translate` | `translate` | A translated `.vtt` (`<stem>.<lang>.vtt`) and a two-track `<video>` snippet on standard output, through a local model. The target language is `--lang`, or detected from the surrounding page (`--in`, `--context`). |

### Checking the result

| Command | Front door | What it produces |
|---|---|---|
| `sprezzature-audio-audit` | `audit` | Every cue that cannot be read as timed: reversed, overlapping, empty, too brief, too long, too fast, too wide, too many lines. Defaults follow the Netflix Timed Text Style Guide; each threshold is a flag. Exit code 1 on any finding. Standard library only. |
| `sprezzature-audio-benchmark` | `benchmark` | WER between two transcripts, DER between two RTTM files, and RTF of a timed command (`--time-command`). |

### From text to speech

A narration lands as an audio file plus a WebVTT, the same convention a transcript uses, so a page can follow the reading sentence by sentence.

| Command | Front door | What it produces |
|---|---|---|
| `sprezzature-audio-narrate-kokoro` | `narrate` | `narration.wav` (or `--audio-format mp3`) and `narration.vtt` in `--out-dir`, from a `--segments` JSON file, with the Kokoro voice: 54 built-in voices in eight languages, English in American and British voices. `narrate` is the oldest name, not a default engine: which engine reads a document is `speaker-helper`'s call (see below). |
| `sprezzature-audio-narrate-openvoice` | `narrate-openvoice` | The same, with OpenVoice, which can clone a voice from a short sample (`--voice-sample`). |
| `sprezzature-audio-narrate-chatterbox` | `narrate-chatterbox` | The same, with Chatterbox. |
| `sprezzature-audio-voice` | `voice` | The built-in voices of each engine; `--sample` writes a one-line demo clip per voice, and `--measure` ranks them by how far their pitch moves. |

The three narration commands share one set of flags, because `sprezzature-publish` drives them interchangeably. They print a one-line JSON report on standard output: audio path, duration, cue path, voice and language, plus the language detected, whether a fallback was used, and any voice hints the engine ignored.

This package does not choose the voice engine, and neither should its caller. That decision belongs to the router in [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper), which owns the engines. `sprezzature-publish` asks the router and then runs the matching wrapper here. With no `--voice`, the language is detected from the text and a voice that speaks it is picked. This matters: the detected language is what the phonemiser works from, so French read as English is not French with an accent, it is English spelling rules applied to French words.

### Preparing a machine

| Command | Front door | What it does |
|---|---|---|
| `sprezzature-audio-install` | `install` | Pre-downloads a GGML Whisper model (`--model`, default `large-v3-turbo`) so captioning runs offline. |
| `sprezzature-audio-install-diarize` | `install-diarize` | Checks that NeMo imports, running `pip install nemo_toolkit[asr]` only if it does not (`--no-install` skips that), and pre-downloads the Sortformer and TitaNet checkpoints (`--only` for one of them). |
| `sprezzature-audio-install-voice` | `install-voice` | Downloads a narration engine's weights (`--engine kokoro`, `openvoice`, `chatterbox` or `all`, the default) and checks for a system espeak-ng. |

Two more commands are not tools: `sprezzature-audio tools` lists the fifteen and says which ones import on this machine, and `sprezzature-audio-mcp` serves the MCP surface (see below).

## Install

One line. Captioning, diarization, speaker identification, translation, narration and the HTTP and MCP surfaces all install with it.

```sh
pip install sprezzature-audio
```

There are no feature extras. The suite folded them into the base install on 2026-11-01. One extra remains, and it is not a feature: `[dev]` is the test toolchain (pytest, ruff).

What pip cannot do for you:

```sh
# System programs. ffmpeg reads media files; Kokoro phonemises through espeak-ng.
brew install ffmpeg espeak-ng          # or: apt install ffmpeg espeak-ng

# Model weights are fetched on demand, not shipped in the wheel.
sprezzature-audio-install                             # Whisper large-v3-turbo
sprezzature-audio-install-diarize --no-install        # Sortformer and TitaNet
sprezzature-audio-install-voice --engine kokoro       # two files, about 354 MB
sprezzature-audio-install-voice --engine chatterbox   # about 1 GB, from Hugging Face
```

OpenVoice needs one more step. Its Python package ships from GitHub with no wheel, and a published wheel cannot depend on a git URL, so from a clone:

```sh
pip install -r scripts/requirements-narrate-openvoice.txt
sprezzature-audio-install-voice --engine openvoice
```

Two consequences worth stating rather than discovering:

- **Python 3.10 to 3.13.** `requires-python` is `>=3.10,<3.14`, because `vocal-helper`, `audio-helper`, `video-helper` and `speaker-helper` all declare `<3.14` at the versions named in the manifest.
- **torch comes with it**, through `speaker-helper[chatterbox]` and `nemo_toolkit[asr]`. Importing the library does not load it: `import sprezzature_audio` to parse a WebVTT file touches no model at all, and a test enforces that.

## Quick start

The front door lists every tool. A script should call the tool's own command.

```sh
sprezzature-audio --help                 # the catalogue, one line per tool
make-audio --help                        # the same command, under its older name
sprezzature-audio tools                  # which tools import on this machine
sprezzature-audio captions --help        # one tool's own flags, through the front door
sprezzature-audio-captions --help        # the same flags, from the tool's own command
```

Both names resolve to the same click group, so they cannot drift. Every argument after the tool name goes to that tool, `--help` included: the front door answers `--help` only before a tool is named.

```sh
# Transcribe a video to WebVTT (writes talk.vtt)
sprezzature-audio-captions talk.mp4

# Same, as a plain-text transcript (writes podcast.txt)
sprezzature-audio-captions podcast.mp3 --format text

# Who spoke when (writes interview.rttm and interview.diarization.json)
sprezzature-audio-diarize interview.wav

# Who said what: the pipeline merges the two files the steps above wrote
sprezzature-audio-captions meeting.mp4
sprezzature-audio-diarize meeting.mp4
sprezzature-audio-pipeline --captions meeting.vtt --diarization meeting.diarization.json
# writes meeting.speakers.vtt

# Guess speaker names from the attributed transcript
sprezzature-audio-name meeting.speakers.vtt --out meeting.speakers.json

# Translate captions to French (writes talk.fr.vtt)
sprezzature-audio-translate talk.vtt --lang fr

# Check that the captions can be read at the speed they go by
sprezzature-audio-audit talk.vtt

# Narrate a list of blocks (writes out/narration.wav and out/narration.vtt)
echo '[{"text": "First paragraph."}, {"text": "Second paragraph."}]' > segments.json
sprezzature-audio-narrate-kokoro --segments segments.json --out-dir out
```

More invocations, each with the files it writes, are in [EXAMPLES.md](https://github.com/warith-harchaoui/sprezzature-audio/blob/main/EXAMPLES.md).

## As a library

`import sprezzature_audio` hands back the engine, not only a version string. What imports eagerly is everything that needs no model: the WebVTT reader and writer, the caption audit, speaker attribution over an existing transcript, WER and DER, the device probe and language detection. It is the same set the HTTP API serves, for the same reason: it is fast and pure.

```python
import sprezzature_audio as audio

cues = audio.parse(open("talk.vtt").read())
for finding in audio.audit_cues(cues):      # too fast, too short, too wide
    print(finding)

print(audio.write_srt(cues))                # VTT -> SRT, same reader
ref = audio.normalise_words(reference_text)
hyp = audio.normalise_words(hypothesis_text)
print(audio.word_error_rate(ref, hyp)["wer"])
print(audio.describe_device())              # which accelerator this host uses
```

The model-backed half resolves on first use (PEP 562), so the import above costs nothing even with Whisper, NeMo and Kokoro installed:

```python
from pathlib import Path

audio.transcribe(Path("talk.mp4"), fmt="vtt")      # Whisper, through vocal-helper
audio.diarize(Path("talk.mp4"))                    # NeMo Sortformer

rows = audio.parse_caption_cues(open("talk.vtt").read())
translate = audio.make_ollama_translator(
    url="http://localhost:11434", model="qwen3-vl:8b", source_lang="en", target_lang="fr"
)
audio.translate_cues(rows, translate_batch=translate)

audio.narrate("kokoro", [{"text": "Hello."}], voice="", voice_sample=None, out_dir=Path("out"))
```

`audio.narrate` is the adapter the narration commands use; the voice engine itself is `speaker-helper`'s, and it is not re-exported here. If a lazy name fails to import, the error says the install is broken (everything is in the base) and chains the import error that names what is missing.

## HTTP API and MCP

The FastAPI (Python web framework) app serves the fast, model-free half. Transcription, diarization and narration are deliberately absent: they load large models and run for minutes, which behind a synchronous request is a timeout.

| Route | `operation_id` | What it does |
|---|---|---|
| `GET /health` | `health` | Liveness probe. |
| `GET /v1/device` | `get_device` | Which accelerator this host will use, probed rather than read from config. |
| `POST /v1/captions/convert` | `convert_captions` | VTT, SRT and plain text, from one to another. |
| `POST /v1/captions/merge` | `merge_speakers` | Captions plus speaker turns into one speaker-labelled track. |
| `POST /v1/metrics/wer` | `measure_wer` | WER between a reference and a hypothesis transcript. |
| `POST /v1/metrics/der` | `measure_der` | DER between two sets of speaker segments, with the best label permutation. |

```sh
uvicorn sprezzature_audio.api:app --host 127.0.0.1 --port 8000   # HTTP only; docs at /docs
sprezzature-audio-mcp                                             # HTTP routes plus MCP at /mcp
```

MCP (Model Context Protocol) is how an agent host calls tools. `sprezzature-audio-mcp` wraps the same app with `fastapi-mcp` and mounts the endpoint at `/mcp`; each route's `operation_id` is the MCP tool name, so the six tools are the six rows above. It binds `127.0.0.1:8000` by default; `--host`, `--port`, `SPREZZATURE_AUDIO_HOST` and `SPREZZATURE_AUDIO_PORT` change that.

### Docker

```sh
docker compose up -d                       # the API on localhost:8000
curl -s localhost:8000/health
docker compose run --rm api sprezzature-audio-captions /work/talk.mp4
docker compose --profile translate up -d   # adds an Ollama server for translate and name
```

The image installs the package with `ffmpeg` and `espeak-ng`, and its default command is `sprezzature-audio-mcp --host 0.0.0.0 --port 8000`: one process on one port serves the HTTP routes and the MCP endpoint at `/mcp`. Files go through `./work`, mounted at `/work`; the Whisper and NeMo caches go to the named volume `audio-cache` through `SPREZZATURE_CACHE_DIR`, and the narration weights, which do not follow that variable, to a second one, `voice-cache`, mounted on the container's `~/.cache`. Both survive `docker compose down`; `down -v` deletes them. `OLLAMA_URL` points at the `ollama` service. The long tools run as commands in the same image.

## Agent skill

The fifth surface is the `sprezzature-audio` skill for Claude Code and OpenCode, kept in the [sprezzature](https://github.com/warith-harchaoui/sprezzature) hub. [TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-audio/blob/main/TRIGGERS.md) is the routing table an agent reads: which request goes to which tool, on which surface.

## How this differs from audio-helper

`audio-helper` works at the **signal level**: converting formats, slicing a waveform, resampling, separating a voice from background music with Demucs. It has no notion of words; a silence and a sentence look the same to it.

`sprezzature-audio` works at the **content level**: it reads speech, attributes it to a speaker, translates it, and reads text aloud. The two packages are meant to be used together. `captions_from_whisper.py` extracts a 16 kHz mono WAV file (the format Whisper expects) before it runs the speech model, through `video-helper` first, then `audio-helper`, then a plain `ffmpeg` call if neither is importable.

## Models used

| Task | Model | Backend |
|---|---|---|
| ASR (speech to text) | `large-v3-turbo` by default, or any other GGML Whisper weights (the compact format whisper.cpp expects) | vocal-helper / whisper.cpp |
| Diarization (who spoke when) | `nvidia/diar_sortformer_4spk-v1` | NeMo |
| Speaker identification (matching a voice to a reference sample) | `nvidia/speakerverification_en_titanet_large` | NeMo |
| Translation and name guessing | `qwen3-vl:8b`, through the Ollama server at `--url` | best-engine-ai-helper |
| Narration | Kokoro, OpenVoice, Chatterbox, chosen per reading by the router | speaker-helper |

## Environment variables

| Variable | Purpose |
|---|---|
| `SPREZZATURE_WHISPER_MODEL` | Override the Whisper model path or alias |
| `SPREZZATURE_CACHE_DIR` | Cache root for Whisper weights, NeMo checkpoints and results (default `~/.cache/sprezzature-skill`). Narration weights ignore it: Kokoro and OpenVoice go under `~/.cache/sprezzature-skill`, Chatterbox under `~/.cache/huggingface` |
| `SPREZZATURE_NO_CACHE` | Set to any value to disable the transcription and diarization result cache |
| `OLLAMA_URL` | Default of the `--url` of `translate` and `name`: the Ollama server they check and then call (default `http://localhost:11434`) |
| `SPREZZATURE_LLM_TIMEOUT` | Per-request timeout, in seconds, of the LLM (large language model) call that best-engine-ai-helper makes for `translate` and `name` (default 120). The backend and server are not read from the environment: those two tools name Ollama at `--url` themselves |
| `SPREZZATURE_AUDIO_HOST`, `SPREZZATURE_AUDIO_PORT` | Default bind address of `sprezzature-audio-mcp` |

## License

BSD 3-Clause. See [LICENSE](https://github.com/warith-harchaoui/sprezzature-audio/blob/main/LICENSE).

## Author

Warith HARCHAOUI: [deraison.ai](https://deraison.ai/)
