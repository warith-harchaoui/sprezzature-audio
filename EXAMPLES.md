# Examples: sprezzature-audio

Each block below is a complete, runnable command followed by what it writes to disk or prints to the terminal. Read [README.md](README.md) first for what each tool does in one line; this file is for copying a working invocation. Every command is also reachable through the front door: `sprezzature-audio-captions talk.mp4` and `sprezzature-audio captions talk.mp4` are the same call.

## Generate captions for a video

```sh
sprezzature-audio-captions conference.mp4
# Writes: conference.vtt
```

## Get a plain text transcript

```sh
sprezzature-audio-captions podcast.mp3 --format text
# Writes: podcast.txt
```

## Transcribe in a specific language

```sh
sprezzature-audio-captions interview.wav --lang fr --format srt
# Writes: interview.srt  (French)
```

## Bias the model toward domain vocabulary

```sh
# From a vocabulary file (one term per line, '#' starts a comment)
sprezzature-audio-captions lecture.mp4 --vocab glossary.txt

# From a source directory (extracts proper nouns and identifiers)
sprezzature-audio-captions talk.mp4 --vocab-from ./project/

# From the whole project the recording sits in
sprezzature-audio-captions ./project/media/talk.mp4 --auto-project
```

## Diarize an audio file

```sh
sprezzature-audio-diarize roundtable.wav
# Writes: roundtable.rttm, roundtable.diarization.json

sprezzature-audio-diarize call.wav --max-speakers 2 --format json
# Writes: call.diarization.json
```

## Full pipeline: captions and speaker attribution

`sprezzature-audio-pipeline` merges an existing caption file with an existing diarization file. It does not take a media file, so run the two upstream steps first:

```sh
sprezzature-audio-captions meeting.mp4
# Writes: meeting.vtt

sprezzature-audio-diarize meeting.mp4
# Writes: meeting.rttm, meeting.diarization.json

sprezzature-audio-pipeline --captions meeting.vtt --diarization meeting.diarization.json
# Writes: meeting.speakers.vtt  (<v Speaker 1>, <v Speaker 2>, ...)

sprezzature-audio-pipeline --captions meeting.vtt --diarization meeting.diarization.json \
    --speakers meeting.speakers.json --format srt
# Writes: meeting.speakers.srt  (with the names from meeting.speakers.json)
```

## Guess speaker names from a diarized transcript

```sh
sprezzature-audio-name meeting.speakers.vtt --out meeting.speakers.json
# Writes: meeting.speakers.json  {"0": "Alice", "1": "Bob"}

# Add a pass through a local model (needs Ollama running)
sprezzature-audio-name meeting.vtt --diarization meeting.diarization.json --ollama
# Writes: meeting.speakers.json
```

Without `--out`, the output is `<transcript stem>.speakers.json`, so `meeting.speakers.vtt` gives `meeting.speakers.speakers.json`.

## Identify a speaker from reference clips

```sh
sprezzature-audio-identify meeting.diarization.json \
    --audio meeting.wav --refs ./voices/
# Writes: meeting.speakers.json  {"0": "Alice", "1": "Bob", "2": "2"}
# (speaker "2" stayed anonymous: no reference clip cleared the similarity threshold)
```

Each file in `./voices/` is one known speaker, and its file name (without `.wav`) is the name written. `--threshold` (default 0.55) sets how close a match must be.

## Translate captions

```sh
# Target language detected from the page that embeds the media
sprezzature-audio-translate talk.vtt --in article.html
# Writes: talk.<detected>.vtt, and prints a two-track <video> snippet

# Explicit target language
sprezzature-audio-translate talk.vtt --lang es
# Writes: talk.es.vtt

# Two-track HTML snippet for a named media file
sprezzature-audio-translate interview.vtt --lang de --media interview.mp4
# Writes: interview.de.vtt
```

## Audit a caption track

```sh
sprezzature-audio-audit talk.vtt
# Prints one line per finding; exit code 1 if there is any, 0 otherwise

sprezzature-audio-audit talk.srt --cps 20 --format json
# The same, with a 20 characters-per-second ceiling, as JSON
```

## Measure a run

```sh
sprezzature-audio-benchmark --reference truth.vtt --hypothesis whisper.vtt
# Prints the word error rate with its substitution, deletion and insertion split

sprezzature-audio-benchmark --reference-rttm truth.rttm --hypothesis-rttm out.rttm
# Prints the diarization error rate

sprezzature-audio-benchmark --audio a.mp4 --time-command 'sprezzature-audio-captions a.mp4'
# Prints the real-time factor of that command on this machine
```

## Narrate a document

```sh
echo '[{"text": "First paragraph."}, {"text": "Second paragraph."}]' > segments.json

sprezzature-audio-narrate-kokoro --segments segments.json --out-dir out
# Writes: out/narration.wav, out/narration.vtt
# Prints: one JSON line with the audio path, duration, cue path, voice and language

sprezzature-audio-narrate-kokoro --segments segments.json --out-dir out \
    --audio-format mp3 --bitrate 64k
# Writes: out/narration.mp3, out/narration.vtt

sprezzature-audio-narrate-kokoro --check
# Exit code 0 if Kokoro can synthesise on this machine, 1 otherwise
```

## Pick a voice

```sh
sprezzature-audio-voice --engine kokoro
# Prints the 54 built-in Kokoro voices

sprezzature-audio-voice --engine kokoro --sample --measure
# Writes: out/voice-samples/kokoro/<voice>.wav, and ranks the voices by pitch movement
```

## Install Whisper models ahead of time

```sh
sprezzature-audio-install
# Downloads ggml-large-v3-turbo.bin to ~/.cache/sprezzature-skill/whisper/
```

## Install NeMo diarization models

```sh
sprezzature-audio-install-diarize
# Checks that NeMo imports (pip-installs nemo_toolkit[asr] only if it does not), then downloads the Sortformer and TitaNet checkpoints
```

## Install a narration engine's weights

```sh
sprezzature-audio-install-voice --engine kokoro
# Downloads kokoro-v1.0.onnx and voices-v1.0.bin to ~/.cache/sprezzature-skill/kokoro/
```

## See which tools run on this machine

```sh
sprezzature-audio tools
# Prints one line per tool: its front-door name, "ready" or "unavailable", and what it does
```

## Serve the web routes and the agent endpoint

One process serves both the HTTP (HyperText Transfer Protocol, the request-and-reply exchange a browser uses to fetch every page) routes and the MCP (Model Context Protocol, the protocol through which AI agents call tools in English) endpoint.

```sh
sprezzature-audio-mcp
# Serves the HTTP routes and the MCP endpoint at http://127.0.0.1:8000/mcp

curl -s -X POST localhost:8000/v1/captions/convert \
    -H 'Content-Type: application/json' \
    -d '{"captions": "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello.\n", "to": "srt"}'
# Prints the same cue as SRT
```

## Install the agent skill

```sh
sprezzature-audio-skill
# Prints whether ~/.claude/skills/sprezzature-audio holds the skill this package ships

sprezzature-audio-skill --install
# Copies it there; a copy that differed is moved to ~/.claude/skills-superseded/sprezzature-audio

sprezzature-audio-skill --install --agent opencode
# The same, into ~/.opencode/skills/sprezzature-audio
```
