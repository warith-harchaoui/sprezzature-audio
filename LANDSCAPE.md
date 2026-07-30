# Landscape -- sprezzature-audio in context

The table below compares tools for speech-to-text, diarization, speaker identification, and caption translation. Stars rate each axis from 1 (weak) to 5 (excellent). Blank cells mean the tool does not address that axis.

| Tool | Local-first | ASR | Diarization | Speaker ID | Multilingual translation | pip installable |
|---|---|---|---|---|---|---|
| **sprezzature-audio** | **5** | **4** | **4** | **4** | **4** | **5** |
| whisper (OpenAI CLI) | 5 | 4 | -- | -- | -- | 5 |
| WhisperX | 5 | 4 | 4 | -- | -- | 4 |
| pyannote.audio | 5 | -- | 5 | 3 | -- | 4 |
| Speechbrain | 4 | 3 | 3 | 4 | 2 | 3 |
| NeMo (raw) | 4 | 4 | 5 | 5 | 3 | 3 |
| AssemblyAI | 1 | 5 | 5 | 4 | 4 | 5 |
| Amazon Transcribe | 1 | 5 | 5 | 3 | 3 | 4 |

## Notes

**whisper (OpenAI CLI)** transcribes but does not know who spoke. No diarization, no speaker ID.

**WhisperX** adds word-level alignment and pyannote-backed diarization. No speaker ID from a reference sample.

**pyannote.audio** is the benchmark for diarization. It does not transcribe.

**Speechbrain** covers many audio tasks. The API requires more setup than a one-liner pip install for production use.

**NeMo (raw)** provides the Sortformer and TitaNet models that `sprezzature-audio` wraps. Direct NeMo use requires more boilerplate; this package provides the ready-made scripts.

**AssemblyAI / Amazon Transcribe** are cloud services. Data leaves the machine. Pricing per minute of audio.

## Where sprezzature-audio fits

The unique selling point is the **local-first full stack**: transcription (Whisper via vocal-helper), diarization (NeMo Sortformer), speaker ID (TitaNet), and LLM-based translation (sprezzature-local with ollama), all runnable offline on a laptop or server. No cloud required at any step.
