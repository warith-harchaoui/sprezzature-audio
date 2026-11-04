# Triggers: sprezzature-audio

Which request about speech goes to which tool, and on which surface. This file is written for an agent (a Claude Code or OpenCode skill, an MCP host, anything choosing a tool on someone's behalf). Humans are welcome, but the routing rules are the point.

---

## The generalisation, stated once

> **Any request whose object is speech, in either direction, is a trigger.** Speech recorded and wanted as text, or text wanted as speech. Do not wait for the word "transcribe" or "narrate". Route on what the user is holding and what they want back, never on how they phrase it.

The domain has a closed vocabulary, and a request that names one of these objects belongs here:

| The user holds or wants | Words that name it |
|---|---|
| a recording | audio, video, recording, podcast, meeting, interview, talk, voice memo, `.wav`, `.mp3`, `.mp4` |
| timed text | captions, subtitles, transcript, cue, track, WebVTT, `.vtt`, SRT, `.srt` |
| who spoke | speaker, turn, diarization, RTTM, `.rttm`, `.diarization.json`, `.speakers.json`, voice sample |
| another language | translation, translated track, two-language captions |
| a quality number | WER, DER, RTF, accuracy, error rate, reference transcript |
| spoken text | narration, TTS (text-to-speech), voice, read aloud, narrator, `narration.wav` |

Then the direction decides the half:

- **Recording in, text out.** Four questions, always in this order. Work out which ones the user needs and you have the pipeline.

  | # | Question | Tool |
  |---|---|---|
  | 1 | What was said? | `captions` |
  | 2 | Who spoke when? | `diarize` |
  | 3 | Who is who? | `identify` (with reference samples) or `name` (from the transcript) |
  | 4 | In another language? | `translate` |

  "Who said what" is 1 then 2 then `pipeline`, which merges the two files. Anything past 4 (summarising, searching, quoting) is ordinary text work on the transcript these stages produced.

- **Timed text in, a judgement out.** `audit` (can it be read at that speed?), `benchmark` or the metric tools (how wrong is it against a reference?).

- **Text in, speech out.** `narrate` and its two siblings, after `install-voice`; `voice` to hear the candidates first. This package does not choose the engine, and the agent must not either: `speaker-helper`'s router decides, and `sprezzature-publish` calls it. Kokoro is the default (`narrate`). Name another engine only when the user explicitly asks for one.

**Not this package:** cutting, resampling or cleaning a signal (`audio-helper`); wiring a narration into a page with a player and read-along highlighting (`sprezzature-publish`, which calls this package for the voice); describing an image in words (`sprezzature-accessibility`).

---

## Every tool, and the request it answers

| Tool (front door) | Command | The request it answers |
|---|---|---|
| `captions` | `sprezzature-audio-captions` | Turn this recording into a WebVTT, SRT or plain transcript. |
| `diarize` | `sprezzature-audio-diarize` | Mark who spoke when, as speaker numbers. |
| `identify` | `sprezzature-audio-identify` | Put names on the diarized speakers, given one reference WAV per known person. |
| `pipeline` | `sprezzature-audio-pipeline` | Merge a caption file and a diarization file (and optional names) into one speaker-labelled track. |
| `name` | `sprezzature-audio-name` | Guess who the speakers are from what they say, with no reference sample. |
| `translate` | `sprezzature-audio-translate` | Translate a caption track, keeping its timings, and emit a two-track `<video>` snippet. |
| `audit` | `sprezzature-audio-audit` | Can these captions be read at the speed they go by? Exit code 1 on any finding. |
| `benchmark` | `sprezzature-audio-benchmark` | WER, DER or RTF of a run, against a reference or a stopwatch. |
| `narrate` | `sprezzature-audio-narrate-kokoro` | Read these blocks aloud with Kokoro (the default) and write the audio and its `.vtt`. |
| `narrate-openvoice` | `sprezzature-audio-narrate-openvoice` | The same with OpenVoice, which clones a voice sample. |
| `narrate-chatterbox` | `sprezzature-audio-narrate-chatterbox` | The same with Chatterbox. |
| `voice` | `sprezzature-audio-voice` | Which voices are there, and what do they sound like? |
| `install` | `sprezzature-audio-install` | Download the Whisper model ahead of the first transcription. |
| `install-diarize` | `sprezzature-audio-install-diarize` | Install NeMo and download the Sortformer and TitaNet checkpoints. |
| `install-voice` | `sprezzature-audio-install-voice` | Download a narration engine's weights and check for espeak-ng. |
| `tools` | `sprezzature-audio tools` | Which of the tools above import on this machine? |

The six MCP tools, and when to call each:

| MCP tool | Call it when |
|---|---|
| `health` | Only to diagnose a connection problem. |
| `get_device` | Before promising a transcription time. It probes the accelerator rather than reading config; a CPU-only host is where "a few minutes" becomes an hour. |
| `convert_captions` | "Give me this as SRT", "just the text". Format conversion only, no model. |
| `merge_speakers` | Captions and speaker turns are held separately and "who said what" is wanted. It joins on time; it does not work out who spoke. |
| `measure_wer` | "How good is this transcript", "which engine is better". **Needs a reference**, a transcript known to be right. |
| `measure_der` | The same question about who spoke when. Also needs a reference. |

---

## What to call on every surface

The heavy stages run local models on real files: they are commands, not HTTP or MCP tools. What the HTTP API and MCP expose is the work on text the pipeline already produced, plus the device probe. So the rule between surfaces is short: **audio in, or speech out: CLI. Text in: MCP tool.**

| Job | Library (`import sprezzature_audio as audio`) | CLI command | Front door | HTTP route | MCP tool (`operation_id`) |
|---|---|---|---|---|---|
| Transcribe | `audio.transcribe` | `sprezzature-audio-captions` | `captions` | none | none |
| Diarize | `audio.diarize` | `sprezzature-audio-diarize` | `diarize` | none | none |
| Identify speakers | `audio.match_speakers` | `sprezzature-audio-identify` | `identify` | none | none |
| Merge captions and turns | `audio.attribute_speakers` | `sprezzature-audio-pipeline` | `pipeline` | `POST /v1/captions/merge` | `merge_speakers` |
| Guess names | none | `sprezzature-audio-name` | `name` | none | none |
| Translate captions | `audio.translate_cues` | `sprezzature-audio-translate` | `translate` | none | none |
| Convert VTT, SRT, text | `audio.parse`, `audio.write_vtt`, `audio.write_srt` | none | none | `POST /v1/captions/convert` | `convert_captions` |
| Audit captions | `audio.audit_cues` | `sprezzature-audio-audit` | `audit` | none | none |
| WER | `audio.word_error_rate` | `sprezzature-audio-benchmark --reference --hypothesis` | `benchmark` | `POST /v1/metrics/wer` | `measure_wer` |
| DER | `audio.diarization_error_rate` | `sprezzature-audio-benchmark --reference-rttm --hypothesis-rttm` | `benchmark` | `POST /v1/metrics/der` | `measure_der` |
| RTF | none | `sprezzature-audio-benchmark --time-command` | `benchmark` | none | none |
| Device probe | `audio.describe_device`, `audio.device_report` | none | none | `GET /v1/device` | `get_device` |
| Liveness | none | none | none | `GET /health` | `health` |
| Narrate (Kokoro, default) | `audio.narrate("kokoro", ...)` | `sprezzature-audio-narrate-kokoro` | `narrate` | none | none |
| Narrate (OpenVoice) | `audio.narrate("openvoice", ...)` | `sprezzature-audio-narrate-openvoice` | `narrate-openvoice` | none | none |
| Narrate (Chatterbox) | `audio.narrate("chatterbox", ...)` | `sprezzature-audio-narrate-chatterbox` | `narrate-chatterbox` | none | none |
| List and sample voices | `audio.sample_one_voice` | `sprezzature-audio-voice` | `voice` | none | none |
| Pre-download Whisper | none | `sprezzature-audio-install` | `install` | none | none |
| Pre-download NeMo | none | `sprezzature-audio-install-diarize` | `install-diarize` | none | none |
| Pre-download a voice | none | `sprezzature-audio-install-voice` | `install-voice` | none | none |

The MCP server is `sprezzature-audio-mcp`, endpoint `/mcp`. The skill is `sprezzature-audio`, kept in the sprezzature hub.

---

## Two contracts an agent must not break

**1. A metric needs a reference.** `measure_wer`, `measure_der` and `benchmark` compare a hypothesis against something known to be right. If the user has no reference, say so: there is no number to give, and an invented one is worse than none.

**2. Speaker labels are not names.** Diarization produces numbered speakers (`"0"`, `"1"` in the JSON, `Speaker 1` in a merged track), a cluster, not a person. Turning that into "Anna" is stage 3, and it either matches a voice sample (`identify`) or is a guess read out of the transcript's own content (`name`). Do not silently promote one to the other.
