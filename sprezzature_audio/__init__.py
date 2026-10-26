"""
sprezzature_audio — everything this suite does with a recording and a voice.

Two halves of one subject. **Understanding** a recording: what was said, when
each speaker took their turn, who that speaker is, what it all means in
another language, and how good any of those answers are. **Speaking** a
document: turning a page of prose into narration, with a caption track whose
cues keep the words the page shows.

The understanding half, four models, one per question:

- Whisper (through the ``vocal-helper`` package) turns sound into text: this
  is "automatic speech recognition," or ASR.
- NeMo's Sortformer model marks *who* spoke *when*, without yet knowing
  anyone's name: this step is called diarization.
- NeMo's TitaNet model turns a short voice sample into a fixed-length list of
  numbers (an "embedding"), so two samples from the same person land close
  together and two different people land far apart; matching a diarized
  speaker against a labelled reference sample this way is how a name gets
  attached.
- A local LLM (reached through Ollama, no cloud call) translates the
  transcript into another language once it has speaker labels.

The speaking half, one model: Kokoro, an 82M-parameter text-to-speech model
run through ONNX, phonemising through espeak-ng. It is the default voice
since 1.3.0; OpenVoice and Chatterbox stay available behind their own extras.

Every step runs on the machine that calls it: no audio or text is sent to a
remote server unless the caller explicitly configures a remote LLM.

What this module exports
------------------------
The engine, not a version string. What is importable here with no extras at
all is everything that needs no model: the shared WebVTT reader and writer,
the caption audit, speaker attribution over an existing transcript, the
word- and diarization-error rates, what accelerator this host will use, and
which language a document is written in. That set is deliberately the same
one the HTTP API serves, and for the same reason — it is fast and pure.

The rest — transcription, diarization, identification, translation,
narration — is served lazily, per :pep:`562`, so that ``import
sprezzature_audio`` stays a free statement of intent. Whisper, NeMo, torch
and Kokoro are not reached by any of it: each of those modules already
defers its own heavy import into the function that needs it, which is what
makes ``sprezzature-audio-narrate-kokoro --help`` answer instantly on a
machine with no model installed. The laziness here is the second lock on the
same door — it keeps the import graph flat, and it is what would still hold
if one of those modules ever started importing eagerly at the top.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

__version__ = "1.6.0"
__author__ = "Warith HARCHAOUI"
__email__ = "warithmetics@deraison.ai"
__license__ = "BSD-3-Clause"

from typing import Any  # noqa: E402

# ── What needs no model, and therefore no extra ────────────────────────────
#
# Alphabetical, because the import sorter says so — not grouped by half. The
# one import worth a word is `_vtt`: a single WebVTT module that four writers
# and two readers were folded onto, precisely so that a cue written by the
# narrator and a cue written by the translator cannot disagree about what a
# timestamp looks like.
from sprezzature_audio_scripts._device import (  # noqa: E402
    compute_threads,
    torch_device,
    whisper_backend,
)
from sprezzature_audio_scripts._device import describe as describe_device  # noqa: E402
from sprezzature_audio_scripts._device import report as device_report  # noqa: E402
from sprezzature_audio_scripts._lang import (  # noqa: E402
    detect_language,
    detect_text_language,
    extract_body_text,
    language_name,
)
from sprezzature_audio_scripts._vtt import (  # noqa: E402
    Cue,
    format_timestamp,
    parse,
    write_srt,
    write_vtt,
)
from sprezzature_audio_scripts.audit_captions import Finding  # noqa: E402
from sprezzature_audio_scripts.audit_captions import audit as audit_cues  # noqa: E402
from sprezzature_audio_scripts.benchmark_stt import (  # noqa: E402
    diarization_error_rate,
    normalise_words,
    word_error_rate,
)
from sprezzature_audio_scripts.caption_diarize import (  # noqa: E402
    attribute_speakers,
    parse_caption_cues,
    render_srt,
    render_text,
    render_vtt,
)

# `audit` is renamed on the way out: at package level the bare verb says
# nothing about *what* is audited, and this package audits two different
# things in two different halves. `render_vtt` is not renamed but is the
# attributed-caption one on purpose — the translator has a renderer of the
# same name that passes `voices=False`, because W3C reserves <v Name> tags
# for a same-language track. Two correct functions, one name: exporting
# either one bare would make the other invisible, so only the one the API
# already serves comes through here.

#: Names served lazily, each with the extra that installs it. The value is
#: ``(module, extra)``: the module to import on first use, and the extra to
#: name in the error when that import fails.
#:
#: The import-time cost of these six modules is small today — they defer
#: their own model imports — so the extra named here is mostly for the day
#: one of them does not. What the extra *is* good for right now is the
#: message: a caller who asks for ``synthesise`` is told about ``[narrate]``
#: and not about whichever extra the package happened to mention first.
_LAZY: dict[str, tuple[str, str]] = {
    # transcription — [captions]
    "transcribe": ("captions_from_whisper", "captions"),
    "compose_prompt": ("captions_from_whisper", "captions"),
    "resolve_vocab": ("captions_from_whisper", "captions"),
    "segments_to_srt": ("captions_from_whisper", "captions"),
    "segments_to_text": ("captions_from_whisper", "captions"),
    "segments_to_vtt": ("captions_from_whisper", "captions"),
    # diarization and identification — [diarize]
    "diarize": ("diarize_from_nemo", "diarize"),
    "turns_to_json": ("diarize_from_nemo", "diarize"),
    "turns_to_rttm": ("diarize_from_nemo", "diarize"),
    "build_reference_centroids": ("identify_from_titanet", "diarize"),
    "build_speaker_centroids": ("identify_from_titanet", "diarize"),
    "embed_clip": ("identify_from_titanet", "diarize"),
    "match_speakers": ("identify_from_titanet", "diarize"),
    # translation — [translate]
    "detect_source_language": ("translate_captions", "translate"),
    "make_ollama_translator": ("translate_captions", "translate"),
    "resolve_target_language": ("translate_captions", "translate"),
    "translate_cues": ("translate_captions", "translate"),
    # narration — [narrate]
    #
    # The voice itself is not re-exported here, and that is deliberate. It
    # lives in `speaker-helper` now; forwarding its names through this package
    # would give the engine two owners and let the two drift. What this
    # package exports of narration is what it still owns: the adapter that
    # turns a document's segments into the files a page needs, and the
    # measurement that says how flat a voice is before a long text is
    # committed to it. For the engine, `import speaker_helper`.
    "narrate": ("_speaker", "narrate"),
    "check_narration_install": ("_speaker", "narrate"),
    "engine_is_available": ("pick_voice", "narrate"),
    "pitch_span_semitones": ("pick_voice", "narrate"),
    "sample_one_voice": ("pick_voice", "narrate"),
}

# `extract_audio` is in neither list, and that is the point. Two modules
# define a function by that name — captions_from_whisper and
# diarize_from_nemo — and they are not the same function. A single bare
# export would silently be whichever one was listed last.


def __getattr__(name: str) -> Any:
    """Resolve one of the model-backed names on first use, per :pep:`562`.

    A caller who stays inside the no-extra set never reaches this. A caller
    who asks for ``synthesise`` without ``[narrate]`` installed gets the
    install line for *that* extra — not for whichever one the package
    happened to mention first.
    """
    try:
        module, extra = _LAZY[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    try:
        engine = __import__(
            f"sprezzature_audio_scripts.{module}", fromlist=[name]
        )
    except ImportError as exc:
        raise ImportError(
            f"`{name}` comes from the {extra} half of this package, which is "
            f"an optional extra so that importing the library stays free. "
            f"Install it with: pip install 'sprezzature-audio[{extra}]'"
        ) from exc
    return getattr(engine, name)


def __dir__() -> list[str]:
    """Let tab-completion and ``dir()`` see the lazy names too."""
    return sorted(__all__)


__all__ = [
    # captions: read, write, audit
    "Cue",
    "Finding",
    "audit_cues",
    "format_timestamp",
    "parse",
    "write_srt",
    "write_vtt",
    # speaker attribution over an existing transcript
    "attribute_speakers",
    "parse_caption_cues",
    "render_srt",
    "render_text",
    "render_vtt",
    # how good the answer is
    "diarization_error_rate",
    "normalise_words",
    "word_error_rate",
    # this machine, and this document
    "compute_threads",
    "describe_device",
    "device_report",
    "torch_device",
    "whisper_backend",
    "detect_language",
    "detect_text_language",
    "extract_body_text",
    "language_name",
    # served lazily, behind their extras
    *sorted(_LAZY),
    "__version__",
]
