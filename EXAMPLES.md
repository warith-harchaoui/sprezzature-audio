# Examples -- sprezzature-audio

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

```sh
python scripts/caption_diarize.py meeting.mp4
# Writes: meeting.speakers.vtt
```

## Guess speaker names from a diarized transcript

```sh
python scripts/name_from_transcript.py meeting.speakers.vtt
# Prints: {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
```

## Identify a speaker from a reference sample

```sh
python scripts/identify_from_titanet.py --reference alice_sample.wav unknown.wav
# Prints: match=True  score=0.94
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
