# Examples: sprezzature-audio

Each block below is a complete, runnable command followed by what it writes to disk or prints to the terminal. Read [README.md](README.md) first for what each script does in one line; this file is for copying a working invocation rather than reading a full explanation.

## Generate captions for a video

```sh
python scripts/captions_from_whisper.py conference.mp4
# Writes: conference.vtt
```

## Get a plain text transcript

```sh
python scripts/captions_from_whisper.py podcast.mp3 --format text
# Writes: podcast.txt
```

## Transcribe in a specific language

```sh
python scripts/captions_from_whisper.py interview.wav --lang fr --format srt
# Writes: interview.srt  (French)
```

## Bias the model toward domain vocabulary

```sh
# From a vocabulary file (one term per line)
python scripts/captions_from_whisper.py lecture.mp4 --vocab glossary.txt

# From a source directory (extracts proper nouns and identifiers)
python scripts/captions_from_whisper.py talk.mp4 --vocab-from ./project/
```

## Diarize an audio file

```sh
python scripts/diarize_from_nemo.py roundtable.wav
# Writes: roundtable.rttm, roundtable.diarization.json
```

## Full pipeline: captions + speaker attribution

`caption_diarize.py` merges an existing caption file with an existing
diarization file; it does not take a media file directly, so run the two
upstream steps first:

```sh
python scripts/captions_from_whisper.py meeting.mp4
# Writes: meeting.vtt

python scripts/diarize_from_nemo.py meeting.mp4
# Writes: meeting.rttm, meeting.diarization.json

python scripts/caption_diarize.py --captions meeting.vtt --diarization meeting.diarization.json
# Writes: meeting.speakers.vtt
```

## Guess speaker names from a diarized transcript

```sh
python scripts/name_from_transcript.py meeting.speakers.vtt
# Writes: meeting.speakers.json  {"0": "Alice", "1": "Bob"}
```

## Identify a speaker from reference clips

```sh
python scripts/identify_from_titanet.py meeting.diarization.json \
    --audio meeting.wav --refs ./voices/
# Writes: meeting.speakers.json  {"0": "Alice", "1": "Bob", "2": "2"}
# (speaker "2" stayed anonymous: no reference clip cleared the similarity threshold)
```

## Translate captions

```sh
# Target language auto-detected from the surrounding page
python scripts/translate_captions.py talk.vtt --in article.html

# Explicit target language
python scripts/translate_captions.py talk.vtt --lang es

# Two-track HTML snippet for a named media file
python scripts/translate_captions.py interview.vtt --lang de --media interview.mp4
```

## Install Whisper models ahead of time

```sh
python scripts/install_captions.py
# Downloads ggml-large-v3-turbo.bin to ~/.cache/sprezzature-skill/whisper/
```

## Install NeMo diarization models

```sh
python scripts/install_diarize.py
# Downloads Sortformer and TitaNet checkpoints from Hugging Face
```
