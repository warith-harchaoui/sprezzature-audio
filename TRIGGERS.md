# Triggers: sprezzature-audio

What a user might say about recorded speech, and what to call when they say
it.

This file is written for an agent — a Claude Code / OpenCode skill, an MCP
host, anything choosing a tool on someone's behalf. Humans are welcome, but
the routing rules below are the point.

---

## The generalisation, stated once

> **Any request that turns recorded speech into text, or asks something
> about that text, is a trigger.** Do not wait for the word "transcribe".
> "What did they say in this meeting", "summarise this interview", "find the
> bit where he mentions the budget", « de quoi ils parlent dans cet
> enregistrement », "make this video searchable" — all of it starts with the
> same pipeline, and none of it should end with hand-rolled audio code.

Every request decomposes into four questions, always in this order. Work out
which ones the user needs and you have the pipeline:

| # | Question | Stage | Command |
|---|---|---|---|
| 1 | **What was said?** | speech → text | `sprezzature-audio-captions` |
| 2 | **Who spoke when?** | diarization | `sprezzature-audio-diarize` |
| 3 | **Who is who?** | identification / naming | `sprezzature-audio-identify`, `sprezzature-audio-name` |
| 4 | **In another language?** | caption translation | `sprezzature-audio-translate` |

"Transcribe this" is 1. "Who said what" is 1 + 2, which is
`sprezzature-audio-pipeline` in one command. "Whose voice is this" is 3 and
needs a reference sample. Anything past 4 — summarising, searching, quoting —
is ordinary text work on the transcript the stages above produced.

---

## What the MCP tools are, and what they are not

The heavy stages run local models on real audio files. They are **commands**,
not HTTP tools: a model, a GPU and a multi-megabyte upload do not belong
behind a request an agent makes mid-conversation.

What is exposed as an MCP tool is everything that operates on the *text* the
pipeline already produced, plus one probe:

| Job | MCP tool | Call it when |
|---|---|---|
| Which accelerator this host will use | `get_device` | Before promising a transcription time. It probes rather than reading config. A CPU-only host is where "a few minutes" becomes an hour. |
| Subtitles between VTT / SRT / plain text | `convert_captions` | "give me this as SRT", "just the text please". No model involved. |
| Caption lines + diarization turns → one labelled transcript | `merge_speakers` | You have both halves separately and want "who said what". Joins on time; it does not work out who spoke. |
| Transcript quality against a reference (WER) | `measure_wer` | "how good is this transcript", "which engine is better". **Needs a reference** — a transcript known to be right. |
| Speaker-labelling quality against a reference (DER) | `measure_der` | The same question about who-spoke-when. Also needs a reference. |

So the routing rule between surfaces is simple: **audio in → CLI. Text in →
MCP tool.**

---

## Phrasings, for matching

Not a closed list — the four questions above are the mechanism.

**Stage 1, what was said** — "transcribe this", "generate captions",
"subtitles for this video", "speech to text", "make a vtt / srt", "produce a
transcript", « transcris cet enregistrement », « sous-titre cette vidéo ».

**Stage 2, who spoke when** — "diarize", "who spoke when", "separate the
speakers", "speaker segmentation", "turn-level labels", « sépare les
locuteurs », « qui parle quand ».

**Stage 3, who is who** — "who is this speaker", "identify this voice",
"speaker verification", "match this voice", "name the speakers", "who is
SPEAKER_00", « qui est SPEAKER_00 », « mets les noms ».

**Stage 4, another language** — "translate the captions", "subtitle
translation", "add a translated track", "two-language captions", « traduis
les sous-titres ».

**Both 1 and 2 at once** — "transcribe and diarize", "speaker-attributed
captions", "meeting transcript with names", « compte rendu de réunion avec
les noms ».

**Quality questions** — "how accurate is this", "WER", "DER", "compare these
two engines", « quel est le taux d'erreur ».

---

## Two contracts an agent must not break

**1. A metric needs a reference.** `measure_wer` and `measure_der` compare a
hypothesis against a transcript known to be right. If the user has no
reference, say so — there is no number to give, and an invented one is worse
than none.

**2. Speaker labels are not names.** Diarization produces `SPEAKER_00`, a
cluster, not a person. Turning that into "Anna" is stage 3, and it either
needs a voice sample to match against (`identify`) or it is a guess read out
of the transcript's own content (`name`). Do not silently promote one to the
other.
