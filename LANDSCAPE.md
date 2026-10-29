# Landscape

`sprezzature-audio` is the speech package of the [sprezzature](https://sprezzature.ai/) suite, a set of Python packages for building publication-quality web content. It reads one modality in both directions: recorded speech becomes timed text, written text becomes timed speech. Nothing is sent to a remote service.

## How it fits in the ecosystem

```
sprezzature suite
├── sprezzature-audio          ← this package (captions out, narration in)
├── sprezzature-publish        (sites, meta tags, read-along; calls this one for the voice)
├── sprezzature-accessibility  (static HTML lint, alt text)
├── sprezzature-video          (claim checking over a film, captions from a narration script)
├── sprezzature-figures        (167 chart kinds)
├── sprezzature-maps           (choropleth, situation plate, accumulation field)
├── sprezzature-colors         (contrast, colour-vision deficiency, Tailwind palettes)
├── sprezzature-ui             (vanilla JS and Tailwind, i18n audit)
├── sprezzature-cli-gui        (a command line wrapped in a page)
├── sprezzature-ux-laws        (30 laws, 8 decidable from the HTML)
└── best-engine-ai-helper      (which local model fits this machine)
```

What comes before: [`audio-helper`](https://github.com/warith-harchaoui/audio-helper) at the signal level (format conversion, resampling, trimming, voice separation with Demucs) and [`video-helper`](https://github.com/warith-harchaoui/video-helper) for pulling an audio stream out of a container. A silence and a sentence look the same to them. This package starts once the audio is usable and asks what is in it.

What comes after: `sprezzature-publish`, which drives the narration engines as a subprocess so their heavy imports never enter its own import graph, and binds the resulting WebVTT to the page sentence by sentence. `sprezzature-video` consumes a narration script and measured audio to write a film's captions.

The sister brick doing neighbouring work is [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper), which owns the voices themselves: the engine sessions, the segment timeline, the pause arithmetic, the refusals. This package is the thin place where its wire format meets that library's API, and `scripts/_speaker.py` says so in its own docstring.

## When to choose it

- You have a recording somebody needs as text and the recording cannot leave the building: a legal interview, a patient consultation, an internal all-hands. Every step runs on the machine that calls it, including the translation, which goes through a local Ollama server rather than a hosted model.
- You need both directions in one dependency and one output convention. A transcript and a narration both land as audio beside a WebVTT file, written by the same module, with milliseconds truncated rather than rounded in both. That is what lets a page highlight the sentence being read without a second alignment pass.
- You want to know whether the captions can actually be read. `sprezzature-audio-audit` reports reading speed, cue overlap, line width, duration and line count against the Netflix Timed Text Style Guide, exits 1 on any finding, and needs nothing but the standard library. Accuracy is the only thing most of this field measures.
- You want the speakers named, not numbered. Diarization gives you `speaker 0` and `speaker 1`; TitaNet matched against a folder of reference clips gives you Alice and Bob, and `name_from_transcript` reads the names off the conversation itself when no reference clip exists.
- You want an install that stays small until you ask for a model. The base package is `click` and `langdetect`, and nothing else; the caption tier is torch-free; torch arrives only with the diarization tier and with the heavier voices. Which voice actually speaks is not this package's call, and never a caller's: `speaker-helper` routes the engine from the condition it is given, and a local, free, offline run lands on Chatterbox, Turbo for English and Multilingual for every other language. This package hands over the text and takes back the audio with its cues.

## When to pick something else

**NVIDIA NeMo**, if accuracy is the whole decision and you have NVIDIA hardware. Parakeet TDT sits at the top of the Open ASR Leaderboard at roughly 6.05 % aggregate word error rate against Whisper large-v3-turbo's 7.7 %, and NeMo is where Sortformer and TitaNet actually live: this package wraps two of its checkpoints and pays the flexibility cost. If you want a third checkpoint, or Riva's commercial support, go to the source.

**pyannote.audio with the Community-1 pipeline**, when speaker segmentation is the hard part. It has no ceiling on speaker count, publishes per-dataset diarization error rates on its model card, and is what diarization research benchmarks against. The Sortformer checkpoint used here is built for up to four concurrent speakers, which is right for an interview and wrong for a board meeting.

**ElevenLabs**, when you want one vendor for both directions and the recording may leave your machine. Scribe leads independent English accuracy benchmarks at 3 to 4 % word error rate across 90-plus languages with diarization up to 32 speakers, the synthesis side is the reference everybody else is measured against, and both halves return timings. You pay per hour and per character, and your audio is on somebody else's server.

**Chatterbox or XTTS v2 driven directly**, when cloning one particular person is the job rather than a step. Chatterbox clones from ten seconds and beat ElevenLabs in a blind listening test; XTTS v2 covers seventeen languages from six seconds. Chatterbox is in fact what `speaker-helper` routes to for a local offline run here, so the question is not access but control: go to the engine itself when you want its variants, its dials and its sampling under your hand, rather than through a router whose objective is the quality of a document being read aloud. The quality ceiling belongs to the engine either way, not to the wrapper.

**Piper**, for a Raspberry Pi, a kiosk, or anything where 44 language and region variants matter more than naturalness. It is smaller than Kokoro and covers more locales. Note that the maintained repository moved to the Open Home Foundation under GPL-3.0-or-later, which is a different licence promise from the archived MIT one.

**AssemblyAI or Deepgram**, for a transcription product rather than a transcription step. Per-hour pricing well under a dollar, streaming under 150 ms, diarization included, a service level agreement, and somebody to call. This package has none of those things and is not trying to.

**Vosk**, when the constraint is streaming on a device with no accelerator. It is Kaldi-era accuracy, which is noticeably below Whisper, and it runs in real time on a Raspberry Pi in twenty-odd languages, which Whisper does not.

## Ideas worth stealing

Ordered by what they return against what they cost.

**[pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1): say when you hit the ceiling.** Their pipeline has no fixed speaker count and publishes its error rate per dataset; ours is pinned to a four-speaker checkpoint and says nothing about it. Here: `scripts/diarize_from_nemo.py` already accepts `--model` and `NEMO_DIAR_MODEL`, so the checkpoint is swappable; what is missing is a refusal. When the turn list comes back with exactly four distinct ids on a long recording, Sortformer has probably folded a fifth voice into a fourth, and the script should say so on stderr and in the JSON rather than hand back a confident answer. Cost: an afternoon, one new field, no new dependency. Best ratio in this list, because the capability is there and only the honesty is missing.

**[Piper](https://github.com/OHF-Voice/piper1-gpl): name a voice by what it is.** Piper ids read `fr_FR-siwis-medium`, which is language, region, speaker and quality tier in one string. Kokoro ids read `af_bella`, where two letters encode language and gender and nothing else, and `scripts/pick_voice.py:68` carries a seven-line comment decoding them for the reader. Here: `sprezzature-audio-voice` should print the decoded triple beside the raw id, so the list is browsable without the comment. Cost: an hour. The mapping is already written, as prose, in that comment.

**[Otter.ai](https://otter.ai/): enrol a voice once, not every run.** Otter learns a speaker's voice once and names them in every later meeting. Here, `scripts/identify_from_titanet.py` recomputes the reference centroid from the WAV files in `--refs` on every single run, which is the slow half of the job for a recurring cast. A small enrolment store under `~/.cache/sprezzature-skill/voices/`, keyed on the TitaNet model tag, would skip it. Cost: an afternoon, plus one rule this suite has already learned the hard way: a cache must never silently change an answer, so the store needs a command that lists it and a flag that ignores it.

**[ElevenLabs `/with-timestamps`](https://elevenlabs.io/docs/overview/capabilities/speech-to-text) and [Kyutai TTS](https://huggingface.co/kyutai/tts-1.6b-en_fr): the synthesiser already knows the timings.** Both return alignment from the generation itself rather than re-recognising their own output. This package gets block-level cues from `speaker-helper`, which is enough for sentence highlighting and not enough for word highlighting. Here: a `--word-cues` flag on the narration command, writing a second VTT at word granularity. Cost: half a week, and it is half-built, because one of the engines `speaker-helper` carries, Kokoro, already exposes per-token durations at the phonemisation step it runs anyway. The honest part is that the others do not, so the flag has to refuse by engine name rather than estimate, and the engine is the router's choice rather than the caller's.

**[Deepgram](https://deepgram.com/learn/best-speech-to-text-apis) and [AssemblyAI](https://www.assemblyai.com/blog/top-speaker-diarization-libraries-and-apis): per-word confidence.** Both return how sure the model was, word by word, which is exactly what a human proofreader wants highlighted. `scripts/audit_captions.py` has eight rules and every one of them is geometric: speed, width, duration, overlap, line count. A ninth, `cue-low-confidence`, would be the first rule about the content rather than the shape. Cost: an afternoon to carry pywhispercpp's token probabilities through `captions_from_whisper.py`, and one real design decision before that, because WebVTT has no confidence field: a `NOTE` line, a sidecar JSON, or nothing.

**[whisper-diarization](https://github.com/MahmoudAshraf97/whisper-diarization): separate the music first.** It runs source separation before diarizing, and music under speech is the usual cause of a phantom extra speaker. Here: `--separate` on `sprezzature-audio-diarize`, calling the Demucs path that `audio-helper` already ships and that the `[diarize]` extra already declares. Cost: a day, and it roughly doubles the runtime, so it stays a flag and never becomes a default.

**[WhisperX](https://github.com/m-bain/whisperX): forced phoneme alignment, and why not here.** Its wav2vec2 alignment pass pulls word timestamps under 100 ms, against the 200 to 500 ms that whisper.cpp's segment boundaries give. That precision is exactly what `cue-too-fast` and `cue-too-brief` measure, so it would sharpen the audit as well as the captions. Refused on the default path: the `[captions]` extra is torch-free today and that is a property worth keeping, and alignment needs a model per language on top of torch. Defensible later as a separate `[captions-align]` extra, never as a default.

**[Vosk](https://alphacephei.com/vosk/) and the hosted APIs: streaming, and why not here.** Every hosted competitor and Vosk return partial results while the audio is still arriving. This package is file in, file out, from end to end, and the caption audit is defined over a complete track: `cue-overlap` compares a cue to the one before it, and a streaming cue has no settled neighbour. Refused on purpose. It is a different architecture, not a missing flag.

## How the field divides

**By direction.** Most entries here do one thing. Whisper and its ports, pyannote, Vosk and AssemblyAI only read speech; Kokoro, Piper, Chatterbox, XTTS v2, F5-TTS, Kyutai and MeloTTS only produce it. The tools that do both are either large research toolkits (NeMo, SpeechBrain) or hosted platforms (ElevenLabs, Azure Speech, Deepgram, the OpenAI audio API). There is very little in the middle, and the middle is where this package sits: small enough to pip install, local enough to run with the network off, and pointed both ways.

**By where the audio goes.** The split that decides most real adoptions is not accuracy, it is whether the recording leaves the machine. A hosted API is faster to adopt, cheaper per hour than a GPU, and immediately disqualified in a hospital, a law firm or a defence contractor. Local stacks pay for that in setup, in hardware, and in the hours somebody spends making NeMo and torch agree on a CUDA version. The honest comparison is not "which is better" but "which constraint is binding".

**By library against finished output.** pyannote hands back an annotation object; NeMo hands back tensors and a config file; faster-whisper hands back segments. Turning any of those into a `.vtt` a browser will accept is work somebody redoes in every project. The tools that write the file (whisper.cpp, WhisperX, whisper-diarization, the hosted APIs, this package) are doing something the libraries deliberately do not, and it is a smaller contribution than a model but a real one. This package goes one step further and audits the file it just wrote, which nothing else in the table does.

**By licence, which is messier than it looks.** Code and weights are licensed separately and often differently. Kokoro and NeMo are Apache-2.0 on both. Chatterbox is MIT. pyannote's code is MIT and its Community-1 weights are CC-BY-4.0 behind a Hugging Face access gate. XTTS v2's weights are under the Coqui Public Model License, which is non-commercial. F5-TTS's reference weights are non-commercial too. Kyutai's are CC-BY-4.0, which is permissive and not the same promise as Apache, which is why this package puts Kyutai behind its own extra rather than in the default install.

## How it compares

Every alternative rated 1 to 5 on each criterion, higher is better (⭐ weak to ⭐⭐⭐⭐⭐ strongest). The scores are a considered judgement, not a benchmark, and each axis is oriented so more stars mean stronger on that trait: for cost, more stars mean cheaper or more open; for install weight, more stars mean lighter. A single `⭐` means the tool does not attempt that job at all, which on a capability scale is a 1. The machine-readable source is [`assets/landscape.csv`](assets/landscape.csv): 23 tools across 15 criteria.

| Speech tool | Local and offline | Free or open source | Permissive commercial licence | Transcription accuracy | Speaker segmentation | Named speaker identification | Speech synthesis | Voice cloning | Timed track produced | Multilingual coverage | Light install without torch | Speed on an ordinary machine | Streaming and real time | Maturity and ecosystem | Commercial support |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| sprezzature-audio | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ |
| whisper.cpp | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| faster-whisper | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| WhisperX | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ |
| whisper-diarization | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ |
| pyannote.audio | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| NVIDIA NeMo | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| SpeechBrain | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| Vosk | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Kokoro | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| Piper | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| Chatterbox | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| XTTS v2 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| F5-TTS | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| Kyutai TTS | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| MeloTTS | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| ElevenLabs | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Deepgram | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| AssemblyAI | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Azure Speech | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Amazon Transcribe | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OpenAI Audio API | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Otter.ai | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

![Positioning map of sprezzature-audio against 22 other speech tools, on two axes derived from a principal component analysis of the table above. The package sits alone in the top right corner, the position the reference row is given by construction. The opposite corner holds the hosted platforms: AssemblyAI at the far bottom left, with Amazon Transcribe, Deepgram and Otter.ai beside it, and ElevenLabs at the very bottom. The upper left holds the light local engines that do one job, whisper.cpp, faster-whisper, Vosk, Piper and Kokoro. The right edge holds the voice-cloning synthesisers, F5-TTS, Chatterbox and XTTS v2. The horizontal axis opposes a fast, light recognition tool to an expensive voice that clones; the vertical opposes open and local to bought and supported.](assets/landscape.svg)

The source is [`assets/landscape.csv`](assets/landscape.csv), the star table above and nothing added, and the map is regenerated with:

```sh
python scripts/landscape_to_csv.py ~/sprezzature-audio/LANDSCAPE.md
standpoint ~/sprezzature-audio/assets/landscape.csv \
  --outdir ~/sprezzature-audio/assets --stem landscape --check
```

The geometry is ordinary correlation PCA and is deterministic: the same table gives the same map every run, whatever model named the poles. The poles are called **Nimble** and **Creative** across, **Robust** and **Accessible** up and down. Those four words come from a local model; the loadings below are the control, and they are the part to trust.

**Horizontal, Nimble on the left and Creative on the right.** Voice cloning (+0.48) and speech synthesis (+0.38) pull right; speed on an ordinary machine (−0.44), light install without torch (−0.36), transcription accuracy (−0.26), maturity and ecosystem (−0.24) and timed track produced (−0.23) pull left. What it really opposes is a cheap tool that reads speech fast against an expensive model that invents a voice: F5-TTS, Chatterbox and XTTS v2 are at the right edge, whisper.cpp, Vosk and faster-whisper at the left. `sprezzature-audio` is at the far right by construction, because it is the reference row and `standpoint` anchors the reference top right.

**Vertical, Robust at the bottom and Accessible at the top.** Free or open source (+0.43), permissive commercial licence (+0.40) and local and offline (+0.38) load at the top; commercial support (−0.34), streaming and real time (−0.31), voice cloning (−0.29) and speech synthesis (−0.25) at the bottom. This is the axis that decides most real adoptions: whether the recording leaves the machine, and whether anybody owes you an answer when it breaks. ElevenLabs is at the very bottom, with AssemblyAI, Deepgram, Amazon Transcribe and Azure Speech above it; the whole open half sits in the top band.

**Two axes carry 54.1 % of the table** (38.7 % and 15.4 %). Almost half of what these 15 criteria say is not on this page. That is expected with 15 criteria across 23 tools, and it means the map is a first orientation while the table is the evidence. One thing the axes do not carry, for instance, is that `sprezzature-audio` and NeMo both do the full job in both directions while almost nothing else does; the table says it in two columns, the projection spends its variance elsewhere. `standpoint` also writes a prose interpretation alongside the figure; it is not reproduced here, because a model reading back ratings somebody wrote is not a finding, and this file is more useful if the judgements stay visibly mine.

## Sources

- [Open ASR Leaderboard figures for Parakeet TDT and Whisper large-v3-turbo](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [pyannote Community-1 model card](https://huggingface.co/pyannote/speaker-diarization-community-1)
- [NVIDIA NeMo speaker diarization models](https://docs.nvidia.com/nemo/speech/nightly/asr/speaker_diarization/models.html)
- [TitaNet, by Nithin Rao KOLUGURI, Taejin PARK and Boris GINSBURG, 2021](https://arxiv.org/pdf/2110.04410)
- [ElevenLabs Scribe](https://elevenlabs.io/blog/meet-scribe)
- [Speech-to-text API pricing, 2026](https://convertaudiototext.com/blog/speech-to-text-api-pricing-2026)
- [Local text-to-speech models, with every licence checked](https://www.yaps.ai/blog/best-local-tts-models)
- [Kyutai tts-1.6b-en_fr, CC-BY-4.0 weights](https://huggingface.co/kyutai/tts-1.6b-en_fr)
- [Piper, now at the Open Home Foundation](https://github.com/OHF-Voice/piper1-gpl)
- [whisper.cpp against faster-whisper, measured](https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026)
