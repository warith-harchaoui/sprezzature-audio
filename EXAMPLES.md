# Examples: sprezzature-audio

Each block below is a complete, runnable command followed by what it writes to disk or prints to the terminal. Read [README.md](README.md) first for what each script does in one line; this file is for copying a working invocation rather than reading a full explanation.

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
# From a vocabulary file (one term per line)
sprezzature-audio-captions lecture.mp4 --vocab glossary.txt

# From a source directory (extracts proper nouns and identifiers)
sprezzature-audio-captions talk.mp4 --vocab-from ./project/
```

## Diarize an audio file

```sh
sprezzature-audio-diarize roundtable.wav
# Writes: roundtable.rttm, roundtable.diarization.json
```

## Full pipeline: captions + speaker attribution

`caption_diarize.py` merges an existing caption file with an existing
diarization file; it does not take a media file directly, so run the two
upstream steps first:

```sh
sprezzature-audio-captions meeting.mp4
# Writes: meeting.vtt

sprezzature-audio-diarize meeting.mp4
# Writes: meeting.rttm, meeting.diarization.json

sprezzature-audio-pipeline --captions meeting.vtt --diarization meeting.diarization.json
# Writes: meeting.speakers.vtt
```

## Guess speaker names from a diarized transcript

```sh
sprezzature-audio-name meeting.speakers.vtt
# Writes: meeting.speakers.json  {"0": "Alice", "1": "Bob"}
```

## Identify a speaker from reference clips

```sh
sprezzature-audio-identify meeting.diarization.json \
    --audio meeting.wav --refs ./voices/
# Writes: meeting.speakers.json  {"0": "Alice", "1": "Bob", "2": "2"}
# (speaker "2" stayed anonymous: no reference clip cleared the similarity threshold)
```

## Translate captions

```sh
# Target language auto-detected from the surrounding page
sprezzature-audio-translate talk.vtt --in article.html

# Explicit target language
sprezzature-audio-translate talk.vtt --lang es

# Two-track HTML snippet for a named media file
sprezzature-audio-translate interview.vtt --lang de --media interview.mp4
```

## Install Whisper models ahead of time

```sh
sprezzature-audio-install
# Downloads ggml-large-v3-turbo.bin to ~/.cache/sprezzature-skill/whisper/
```

## Install NeMo diarization models

```sh
sprezzature-audio-install-diarize
# Downloads Sortformer and TitaNet checkpoints from Hugging Face
```
