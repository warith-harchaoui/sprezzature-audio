# Landscape: sprezzature-audio in context

The table below scores seven tools for speech-to-text, diarization, speaker identification, and caption translation, one star column per axis. A star rating runs from 1 (weak) to 5 (excellent); a cell marked `--` means the tool does not attempt that axis at all, so scoring it would be meaningless.

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

Three columns name a task rather than a familiar word: **ASR** (automatic speech recognition) is speech-to-text; **diarization** is figuring out who spoke when, without yet knowing anyone's name; **speaker ID** goes one step further and matches a voice against a known reference sample to put an actual name on it. "Local-first" scores how well a tool runs entirely on your own machine, with no cloud call required for its core function.

## Notes

**whisper (OpenAI CLI)** transcribes speech to text but has no notion of who is speaking: no diarization, no speaker ID.

**WhisperX** adds word-level timing alignment and diarization borrowed from pyannote. It has no way to attach a real name to a speaker from a reference sample.

**pyannote.audio** is the reference tool for diarization; researchers benchmark new diarization methods against it. It does not transcribe at all.

**Speechbrain** covers a wide range of audio tasks in one library. Its API asks for more setup than a one-line `pip install` before it is production-ready.

**NeMo (raw)** is the toolkit that actually contains the Sortformer and TitaNet models `sprezzature-audio` wraps. Calling NeMo directly demands more boilerplate; this package trades a little of NeMo's flexibility for ready-to-run scripts.

**AssemblyAI and Amazon Transcribe** are cloud services: every clip is sent to a remote server, billed per minute of audio. Convenient, but the recording leaves your machine, which rules them out for anything that must stay local.

## Where sprezzature-audio fits

Its distinguishing feature is being a **complete local-first stack**: transcription (Whisper, through vocal-helper), diarization (NeMo's Sortformer), speaker identification (TitaNet), and LLM-based translation (through best-engine-ai-helper's local Ollama connection), all runnable offline on a laptop or a server. No step requires reaching a cloud service.
