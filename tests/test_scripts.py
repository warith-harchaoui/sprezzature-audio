"""Tests for the pure, dependency-light functions in scripts/.

Every script in this project defers its heavy dependency (NeMo,
pywhispercpp, ``best-engine-ai-helper``) to inside the function that
actually calls it, so the parsing / merging / rendering logic around
those calls is plain Python and testable without installing any of the
optional extras. This file exercises that logic directly: caption
parsing and speaker attribution, diarization turn normalisation and
speaker capping, speaker-name rule matching, cue translation batching,
and vocabulary extraction.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ── caption_diarize ─────────────────────────────────────────────────────────


def test_parse_caption_cues_vtt() -> None:
    """parse_caption_cues reads a WebVTT document and strips voice tags."""
    import caption_diarize as cd

    vtt = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\n"
        "Hello there\n\n"
        "00:00:02.000 --> 00:00:04.000\n"
        "<v Alice>General Kenobi\n"
    )
    cues = cd.parse_caption_cues(vtt)
    assert [c["text"] for c in cues] == ["Hello there", "General Kenobi"]
    assert cues[0]["start"] == 0.0
    assert cues[1]["end"] == 4.0


def test_parse_caption_cues_srt() -> None:
    """parse_caption_cues also reads the comma-decimal SRT timestamp form."""
    import caption_diarize as cd

    srt = "1\n00:00:00,000 --> 00:00:01,500\nHello\n"
    cues = cd.parse_caption_cues(srt)
    assert len(cues) == 1
    assert cues[0] == {"start": 0.0, "end": 1.5, "text": "Hello"}


def test_attribute_speakers_picks_max_overlap() -> None:
    """Each cue is labelled with the turn it overlaps the most."""
    import caption_diarize as cd

    cues = [
        {"start": 0.0, "end": 2.0, "text": "a"},
        {"start": 2.0, "end": 4.0, "text": "b"},
    ]
    turns = [
        {"start": 0.0, "end": 2.5, "speaker": "0"},
        {"start": 2.5, "end": 4.0, "speaker": "1"},
    ]
    out = cd.attribute_speakers(cues, turns)
    assert out[0]["speaker_id"] == "0"
    assert out[1]["speaker_id"] == "1"
    # No explicit names: numeric ids are rendered as "Speaker N" (1-based).
    assert out[0]["speaker"] == "Speaker 1"
    assert out[1]["speaker"] == "Speaker 2"


def test_attribute_speakers_uses_names_and_falls_back() -> None:
    """A speaker-names map overrides the default label; no overlap falls back."""
    import caption_diarize as cd

    cues = [
        {"start": 0.0, "end": 1.0, "text": "a"},
        {"start": 10.0, "end": 11.0, "text": "gap"},  # no turn covers this
    ]
    turns = [{"start": 0.0, "end": 1.0, "speaker": "0"}]
    out = cd.attribute_speakers(cues, turns, speaker_names={"0": "Alice"})
    assert out[0]["speaker"] == "Alice"
    # Zero overlap for the second cue: falls back to the previous speaker.
    assert out[1]["speaker_id"] == "0"
    assert out[1]["speaker"] == "Alice"


def test_render_vtt_and_srt() -> None:
    """render_vtt / render_srt emit the expected cue block shape."""
    import caption_diarize as cd

    cues = [{"start": 0.0, "end": 1.0, "text": "Hi", "speaker": "Alice"}]
    vtt = cd.render_vtt(cues)
    assert "WEBVTT" in vtt
    assert "<v Alice>Hi" in vtt

    srt = cd.render_srt(cues)
    assert "1\n00:00:00,000 --> 00:00:01,000\nAlice: Hi" in srt


def test_render_text_breaks_on_new_speaker_and_long_pause() -> None:
    """render_text starts a new paragraph on a speaker change or a long pause."""
    import caption_diarize as cd

    cues = [
        {"speaker": "Alice", "start": 0.0, "end": 1.0, "text": "Hi"},
        {"speaker": "Alice", "start": 5.0, "end": 6.0, "text": "there"},
    ]
    text = cd.render_text(cues)
    assert text == "Alice: Hi\n\nthere\n"


# ── diarize_from_nemo ────────────────────────────────────────────────────────


def test_normalise_predictions_rttm_strings() -> None:
    """_normalise_predictions reads Sortformer's RTTM-line output shape."""
    import diarize_from_nemo as dn

    raw = [
        "SPEAKER file 1 0.00 3.21 <NA> <NA> speaker_0 <NA> <NA>",
        "SPEAKER file 1 3.21 3.93 <NA> <NA> speaker_1 <NA> <NA>",
    ]
    turns = dn._normalise_predictions(raw)
    assert turns == [
        {"start": 0.0, "end": 3.21, "speaker": "0"},
        {"start": 3.21, "end": pytest.approx(7.14), "speaker": "1"},
    ]


def test_normalise_predictions_nested_list() -> None:
    """_normalise_predictions also reads the nested-list output shape."""
    import diarize_from_nemo as dn

    raw = [[[0.0, 3.21, "0"], [3.21, 7.14, "1"]]]
    turns = dn._normalise_predictions(raw)
    assert turns == [
        {"start": 0.0, "end": 3.21, "speaker": "0"},
        {"start": 3.21, "end": 7.14, "speaker": "1"},
    ]


def test_normalise_predictions_empty() -> None:
    """_normalise_predictions returns an empty list for falsy input."""
    import diarize_from_nemo as dn

    assert dn._normalise_predictions([]) == []
    assert dn._normalise_predictions(None) == []


def test_normalise_predictions_compact_string_form() -> None:
    """_normalise_predictions reads nemo_toolkit 2.4.0's actual output shape.

    Confirmed live against ``SortformerEncLabelModel.diarize`` on a real
    two-speaker recording: it returns
    ``[["0.000 5.840 speaker_0", "6.560 13.920 speaker_1", ...]]``, three
    whitespace-separated fields with no leading ``SPEAKER`` token, distinct
    from both the RTTM-line shape and the nested-tuple shape this function
    already handled. Before this branch was added, every turn in that
    shape was silently dropped and the script reported zero speakers.
    """
    import diarize_from_nemo as dn

    raw = [["0.000 5.840 speaker_0", "6.560 13.920 speaker_1"]]
    turns = dn._normalise_predictions(raw)
    assert turns == [
        {"start": 0.0, "end": 5.84, "speaker": "0"},
        {"start": 6.56, "end": 13.92, "speaker": "1"},
    ]


def test_cap_speakers_keeps_top_by_duration() -> None:
    """_cap_speakers keeps the most-active speakers and reassigns the rest."""
    import diarize_from_nemo as dn

    turns = [
        {"start": 0, "end": 10, "speaker": "0"},  # 10s
        {"start": 10, "end": 15, "speaker": "1"},  # 5s
        {"start": 15, "end": 16, "speaker": "2"},  # 1s
    ]
    capped = dn._cap_speakers(turns, cap=2)
    speakers = {t["speaker"] for t in capped}
    assert speakers <= {"0", "1"}
    assert len(capped) == 3
    # The two most-active speakers keep their own turns verbatim.
    assert capped[0]["speaker"] == "0"
    assert capped[1]["speaker"] == "1"


def test_cap_speakers_noop_below_cap() -> None:
    """_cap_speakers is a no-op when the cap already covers every speaker."""
    import diarize_from_nemo as dn

    turns = [{"start": 0, "end": 1, "speaker": "0"}]
    assert dn._cap_speakers(turns, cap=5) == turns
    assert dn._cap_speakers(turns, cap=0) == turns


def test_turns_to_rttm_and_json() -> None:
    """turns_to_rttm / turns_to_json render the two documented output shapes."""
    import diarize_from_nemo as dn

    turns = [{"start": 0.0, "end": 1.5, "speaker": "0"}]
    rttm = dn.turns_to_rttm(turns, file_id="clip")
    assert rttm == "SPEAKER clip 1 0.000 1.500 <NA> <NA> speaker_0 <NA> <NA>\n"
    js = dn.turns_to_json(turns)
    assert '"speaker": "0"' in js


def test_pick_device_explicit_wins() -> None:
    """pick_device returns the explicit override without touching torch."""
    import diarize_from_nemo as dn

    assert dn.pick_device("cuda") == "cuda"


# ── identify_from_titanet (numpy-gated: optional [diarize] extra) ──────────


def test_match_speakers_above_and_below_threshold() -> None:
    """match_speakers assigns the closest reference above threshold only."""
    np = pytest.importorskip("numpy")
    import identify_from_titanet as idt

    centroids = {"0": np.array([1.0, 0.0]), "1": np.array([0.0, 1.0])}
    refs = {"Alice": np.array([1.0, 0.0]), "Bob": np.array([0.0, 1.0])}
    labels = idt.match_speakers(centroids, refs, threshold=0.55)
    assert labels == {"0": "Alice", "1": "Bob"}

    # A centroid with no close reference keeps its anonymous id.
    centroids2 = {"2": np.array([0.6, 0.8])}
    labels2 = idt.match_speakers(centroids2, refs, threshold=0.95)
    assert labels2["2"] == "2"


def test_match_speakers_no_refs() -> None:
    """match_speakers keeps every id verbatim when there is no reference set."""
    np = pytest.importorskip("numpy")
    import identify_from_titanet as idt

    centroids = {"0": np.array([1.0, 0.0])}
    assert idt.match_speakers(centroids, {}) == {"0": "0"}


# ── name_from_transcript ─────────────────────────────────────────────────────


def test_clean_name_filters_stopwords_and_short_names() -> None:
    """_clean_name rejects stopwords and short tokens, title-cases the rest."""
    import name_from_transcript as nft

    assert nft._clean_name("alice,") == "Alice"
    assert nft._clean_name("the") is None  # stopword
    assert nft._clean_name("Bo") is None  # shorter than SHORT_NAME_LEN
    assert nft._clean_name("Bob") == "Bob"


def test_run_rule_pass_self_introduction() -> None:
    """A self-introduction is attributed to the speaker who says it."""
    import name_from_transcript as nft

    cues = [{"text": "I'm Alice, nice to meet you.", "speaker_id": "0"}]
    candidates = nft._run_rule_pass(cues)
    final = nft._pick_best(candidates)
    assert final["0"][0] == "Alice"
    assert final["0"][1] == pytest.approx(nft.CONF_SELF_INTRO)


def test_run_rule_pass_vocative_targets_other_speaker() -> None:
    """A turn-initial vocative names the *other* speaker, not the one talking."""
    import name_from_transcript as nft

    cues = [
        {"text": "Hey Bob, how are you?", "speaker_id": "0"},
        {"text": "Great, thanks.", "speaker_id": "1"},
    ]
    candidates = nft._run_rule_pass(cues)
    assert "1" in candidates
    assert candidates["1"][0] == ("Bob", nft.CONF_VOCATIVE_START)


def test_merge_picks_highest_confidence_across_passes() -> None:
    """_merge keeps, per speaker, the name with the highest confidence."""
    import name_from_transcript as nft

    rule_pass = {"0": ("Alice", 0.5)}
    llm_pass = {"0": ("Bob", 0.9), "1": ("Carl", 0.3)}
    merged = nft._merge(rule_pass, llm_pass)
    assert merged == {"0": "Bob", "1": "Carl"}


def test_repopulate_speaker_ids_from_voice_tags() -> None:
    """_repopulate_speaker_ids recovers ids from <v Name> tags in cue order."""
    import name_from_transcript as nft

    cues = [{"start": 0, "end": 1, "text": "a"}, {"start": 1, "end": 2, "text": "b"}]
    raw = (
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n<v Alice>a\n\n"
        "00:00:01.000 --> 00:00:02.000\n<v Bob>b\n"
    )
    out = nft._repopulate_speaker_ids(cues, raw)
    assert [c["speaker"] for c in out] == ["Alice", "Bob"]
    assert [c["speaker_id"] for c in out] == ["0", "1"]


def test_repopulate_speaker_ids_no_tags_falls_back_to_single_speaker() -> None:
    """With no <v ...> tags at all, every cue is attributed to speaker "0"."""
    import name_from_transcript as nft

    cues = [{"start": 0, "end": 1, "text": "a"}]
    out = nft._repopulate_speaker_ids(cues, "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\na\n")
    assert out[0]["speaker_id"] == "0"
    assert out[0]["speaker"] == "0"


# ── translate_captions ───────────────────────────────────────────────────────


def test_detect_source_language() -> None:
    """detect_source_language reads the language off the joined cue text."""
    import translate_captions as tc

    cues = [{"text": "Bonjour tout le monde, comment allez-vous aujourd'hui ?"}]
    assert tc.detect_source_language(cues) == "fr"


def test_resolve_target_language_precedence() -> None:
    """An explicit --lang wins; otherwise the surrounding text is detected."""
    import translate_captions as tc

    assert tc.resolve_target_language("ES", "", fallback="en") == "es"
    assert (
        tc.resolve_target_language(None, "Bonjour, comment ça va aujourd'hui ?", fallback="en")
        == "fr"
    )
    assert tc.resolve_target_language(None, "", fallback="en") == "en"


def test_render_vtt_translated_cues() -> None:
    """render_vtt formats translated cues without a <v ...> voice tag."""
    import translate_captions as tc

    cues = [{"start": 0.0, "end": 1.5, "text": "hola"}]
    assert tc.render_vtt(cues) == "WEBVTT\n\n00:00:00.000 --> 00:00:01.500\nhola\n"


def test_translate_cues_happy_path() -> None:
    """A well-behaved translator preserves cue count and timestamps."""
    import translate_captions as tc

    cues = [{"start": 0.0, "end": 1.0, "text": "a"}, {"start": 1.0, "end": 2.0, "text": "b"}]
    out = tc.translate_cues(cues, translate_batch=lambda w: [t.upper() for t in w])
    assert [c["text"] for c in out] == ["A", "B"]
    assert out[0]["start"] == 0.0 and out[1]["end"] == 2.0


def test_translate_cues_retries_per_cue_on_count_mismatch() -> None:
    """A window that comes back with the wrong count is retried one cue at a time."""
    import translate_captions as tc

    def flaky(window: list[str]) -> list[str]:
        if len(window) > 1:
            return ["WRONG_COUNT"]  # triggers the per-cue retry path
        return [window[0].upper()]

    cues = [{"text": "a"}, {"text": "b"}, {"text": "c"}]
    out = tc.translate_cues(cues, translate_batch=flaky, batch_size=3)
    assert [c["text"] for c in out] == ["A", "B", "C"]


def test_translate_cues_raises_when_single_cue_also_misaligns() -> None:
    """A translator that never returns exactly one segment aborts loudly."""
    import translate_captions as tc

    cues = [{"text": "a"}]
    with pytest.raises(tc.TranslationError):
        tc.translate_cues(cues, translate_batch=lambda w: [])


def test_two_track_snippet_has_both_tracks() -> None:
    """two_track_snippet emits a captions track and a subtitles track."""
    import translate_captions as tc

    html = tc.two_track_snippet(
        media="clip.mp4",
        native_vtt="clip.vtt",
        translated_vtt="clip.fr.vtt",
        audio_lang="en",
        target_lang="fr",
    )
    assert 'kind="captions"' in html and 'srclang="en"' in html
    assert 'kind="subtitles"' in html and 'srclang="fr"' in html


# ── _vocab ───────────────────────────────────────────────────────────────────


def test_extract_vocabulary_finds_backticks_snake_case_and_proper_nouns() -> None:
    """extract_vocabulary pulls code spans, snake_case identifiers, and names."""
    import _vocab as vocab

    text = "Use `myVariableName` and snake_case_name. I love the Golden Gate Bridge."
    terms = vocab.extract_vocabulary(text)
    assert "myVariableName" in terms
    assert "snake_case_name" in terms
    assert "Golden Gate Bridge" in terms


def test_read_vocab_file_dedupes_case_insensitively(tmp_path: Path) -> None:
    """read_vocab_file skips comments/blanks and dedupes case-insensitively."""
    import _vocab as vocab

    glossary = tmp_path / "glossary.txt"
    glossary.write_text("# a comment\nAlice\n\nBob\nalice\n", encoding="utf-8")
    assert vocab.read_vocab_file(glossary) == ["Alice", "Bob"]


def test_find_project_root_walks_up_to_a_marker(tmp_path: Path) -> None:
    """find_project_root walks upward until a marker file/dir is found."""
    import _vocab as vocab

    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert vocab.find_project_root(nested) == tmp_path


def test_resolve_vocab_terms_vocab_file_wins(tmp_path: Path) -> None:
    """An explicit --vocab file is used verbatim, ahead of project discovery."""
    import _vocab as vocab

    glossary = tmp_path / "glossary.txt"
    glossary.write_text("Alice\nBob\n", encoding="utf-8")
    terms = vocab.resolve_vocab_terms(tmp_path / "audio.wav", vocab_file=glossary)
    assert terms == ["Alice", "Bob"]


# ── captions_from_whisper ───────────────────────────────────────────────────


def test_compose_prompt_basic_and_empty() -> None:
    """compose_prompt builds a one-sentence prompt, or "" for an empty vocab."""
    import captions_from_whisper as cfw

    assert cfw.compose_prompt([], "en") == ""
    prompt = cfw.compose_prompt(["Alice", "Bob"], "en")
    assert prompt == "The following terms may appear in the audio: Alice, Bob."


def test_compose_prompt_truncates_to_the_word_budget() -> None:
    """A vocabulary far larger than MAX_PROMPT_WORDS is truncated, not dropped."""
    import captions_from_whisper as cfw

    vocab = [f"term{i}" for i in range(300)]
    prompt = cfw.compose_prompt(vocab, "en")
    assert len(prompt.split()) <= cfw.MAX_PROMPT_WORDS


def test_format_timestamp_centiseconds_to_vtt_and_srt() -> None:
    """_format_timestamp converts 10-ms units to HH:MM:SS with the right separator."""
    import captions_from_whisper as cfw

    assert cfw._format_timestamp(6134) == "00:01:01.340"
    assert cfw._format_timestamp(6134, srt=True) == "00:01:01,340"


def test_segments_to_vtt_srt_text() -> None:
    """The three renderers agree on timing and skip empty-text segments."""
    import captions_from_whisper as cfw

    segments = [
        SimpleNamespace(t0=0, t1=100, text="Hello"),
        SimpleNamespace(t0=100, t1=200, text="  "),  # blank: dropped by every renderer
    ]
    vtt = cfw.segments_to_vtt(segments)
    assert "00:00:00.000 --> 00:00:01.000\nHello" in vtt
    assert vtt.count("-->") == 1

    srt = cfw.segments_to_srt(segments)
    assert "1\n00:00:00,000 --> 00:00:01,000\nHello" in srt

    text = cfw.segments_to_text(segments)
    assert text == "Hello\n"


def test_cache_key_is_deterministic_and_input_sensitive() -> None:
    """_cache_key returns the same key for identical inputs, a different one otherwise."""
    import captions_from_whisper as cfw

    k1 = cfw._cache_key(b"abc", "large-v3-turbo", "en", "vtt", "")
    k2 = cfw._cache_key(b"abc", "large-v3-turbo", "en", "vtt", "")
    k3 = cfw._cache_key(b"xyz", "large-v3-turbo", "en", "vtt", "")
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 32


def test_resolve_model_arg_env_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """SPREZZATURE_WHISPER_MODEL takes precedence over a pre-downloaded file."""
    import captions_from_whisper as cfw

    monkeypatch.setenv("SPREZZATURE_WHISPER_MODEL", "/explicit/model.bin")
    assert cfw._resolve_model_arg("large-v3-turbo") == "/explicit/model.bin"


def test_resolve_model_arg_prefers_predownloaded_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no env override, a pre-downloaded ggml file wins over the bare alias."""
    import captions_from_whisper as cfw

    monkeypatch.delenv("SPREZZATURE_WHISPER_MODEL", raising=False)
    monkeypatch.delenv("FRONT_WHISPER_MODEL", raising=False)
    monkeypatch.setattr(cfw, "WHISPER_DIR", tmp_path)
    cached = tmp_path / "ggml-tiny.bin"
    cached.write_bytes(b"fake weights")
    assert cfw._resolve_model_arg("tiny") == str(cached)


def test_resolve_model_arg_falls_back_to_bare_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no override and no cached file, the bare alias is returned as-is."""
    import captions_from_whisper as cfw

    monkeypatch.delenv("SPREZZATURE_WHISPER_MODEL", raising=False)
    monkeypatch.delenv("FRONT_WHISPER_MODEL", raising=False)
    monkeypatch.setattr(cfw, "WHISPER_DIR", tmp_path)
    assert cfw._resolve_model_arg("tiny") == "tiny"


def test_resolve_vocab_explicit_prompt_short_circuits() -> None:
    """resolve_vocab returns the explicit --prompt untouched, skipping vocab lookup."""
    import captions_from_whisper as cfw

    result = cfw.resolve_vocab(
        Path("audio.wav"),
        prompt="Use exactly this prompt.",
        vocab_file=None,
        vocab_from=None,
        auto_project=False,
        lang="en",
    )
    assert result == "Use exactly this prompt."


def test_resolve_vocab_composes_prompt_from_vocab_file(tmp_path: Path) -> None:
    """resolve_vocab feeds --vocab terms through compose_prompt when no --prompt is given."""
    import captions_from_whisper as cfw

    glossary = tmp_path / "glossary.txt"
    glossary.write_text("Alice\nBob\n", encoding="utf-8")
    result = cfw.resolve_vocab(
        tmp_path / "audio.wav",
        prompt="",
        vocab_file=glossary,
        vocab_from=None,
        auto_project=False,
        lang="en",
    )
    assert result == "The following terms may appear in the audio: Alice, Bob."


# ── caption_diarize timestamp helpers ───────────────────────────────────────


def test_parse_timestamp_field_group_to_seconds() -> None:
    """_parse_timestamp converts an HH:MM:SS.mmm field group to seconds."""
    import caption_diarize as cd

    assert cd._parse_timestamp("00", "01", "01", "500") == 61.5
    assert cd._parse_timestamp("01", "00", "00", "000") == 3600.0


def test_caption_diarize_format_timestamp_vtt_and_srt() -> None:
    """_format_timestamp renders VTT's dot and SRT's comma decimal separator."""
    import caption_diarize as cd

    assert cd._format_timestamp(61.5) == "00:01:01.500"
    assert cd._format_timestamp(61.5, srt=True) == "00:01:01,500"
    # Negative input clamps to zero rather than raising or going negative.
    assert cd._format_timestamp(-5.0) == "00:00:00.000"


def test_caption_diarize_overlap() -> None:
    """_overlap returns the shared duration of two intervals, or 0 when disjoint."""
    import caption_diarize as cd

    assert cd._overlap(0.0, 2.0, 1.0, 3.0) == 1.0
    assert cd._overlap(0.0, 1.0, 1.0, 2.0) == 0.0  # touching, no overlap
    assert cd._overlap(0.0, 1.0, 2.0, 3.0) == 0.0  # disjoint


# ── translate_captions timestamp helper ─────────────────────────────────────


def test_translate_captions_format_timestamp() -> None:
    """translate_captions._format_timestamp matches the WebVTT dot-decimal form."""
    import translate_captions as tc

    assert tc._format_timestamp(61.5) == "00:01:01.500"
    assert tc._format_timestamp(0.0) == "00:00:00.000"
    assert tc._format_timestamp(-1.0) == "00:00:00.000"


# ── diarize_from_nemo cache + device helpers ────────────────────────────────


def test_diarize_cache_key_deterministic_and_sensitive() -> None:
    """_cache_key is stable for identical inputs and changes with any of them."""
    import diarize_from_nemo as dn

    k1 = dn._cache_key(b"abc", "sortformer", 4)
    k2 = dn._cache_key(b"abc", "sortformer", 4)
    k3 = dn._cache_key(b"abc", "sortformer", 2)
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 32


def test_diarize_cache_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_cache_set writes turns to disk that _cache_get reads back unchanged."""
    import diarize_from_nemo as dn

    monkeypatch.setattr(dn, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(dn, "NO_CACHE", False)
    turns = [{"start": 0.0, "end": 1.0, "speaker": "0"}]
    key = dn._cache_key(b"abc", "sortformer", 0)
    assert dn._cache_get(key) is None  # miss before any write
    dn._cache_set(key, turns)
    assert dn._cache_get(key) == turns


def test_diarize_cache_disabled_by_no_cache_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NO_CACHE=True makes both _cache_get and _cache_set no-ops."""
    import diarize_from_nemo as dn

    monkeypatch.setattr(dn, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(dn, "NO_CACHE", True)
    key = dn._cache_key(b"abc", "sortformer", 0)
    dn._cache_set(key, [{"start": 0.0, "end": 1.0, "speaker": "0"}])
    assert dn._cache_get(key) is None
    assert list(tmp_path.iterdir()) == []  # nothing was written to disk


def test_diarize_cache_get_survives_corrupt_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cache file that fails to parse is treated as a miss, not an error."""
    import diarize_from_nemo as dn

    monkeypatch.setattr(dn, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(dn, "NO_CACHE", False)
    key = "deadbeef"
    (tmp_path / f"{key}.json").write_text("not json", encoding="utf-8")
    assert dn._cache_get(key) is None


def test_pick_device_explicit_beats_torch_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit --device value is returned without importing torch at all."""
    import diarize_from_nemo as dn

    assert dn.pick_device("mps") == "mps"


# ── name_from_transcript: helpers not exercised via _run_rule_pass ──────────


def test_find_other_speaker_looks_forward_then_backward() -> None:
    """_find_other_speaker prefers the next differing speaker, then the previous one."""
    import name_from_transcript as nft

    cues = [
        {"speaker_id": "0"},
        {"speaker_id": "0"},  # idx=1, current speaker
        {"speaker_id": "1"},  # next differing speaker: found forward
    ]
    assert nft._find_other_speaker(cues, 1, "0") == "1"

    # No differing speaker ahead within the window: falls back to backward scan.
    cues2 = [{"speaker_id": "1"}, {"speaker_id": "0"}, {"speaker_id": "0"}]
    assert nft._find_other_speaker(cues2, 1, "0") == "1"

    # No other speaker anywhere nearby: returns the current speaker unchanged.
    cues3 = [{"speaker_id": "0"}, {"speaker_id": "0"}]
    assert nft._find_other_speaker(cues3, 0, "0") == "0"


def test_pick_best_sums_confidence_across_recurrences() -> None:
    """_pick_best sums per-(speaker, name) confidence so repeats outrank one-offs."""
    import name_from_transcript as nft

    candidates = {
        "0": [("Alice", 0.3), ("Alice", 0.3), ("Bob", 0.5)],
    }
    best = nft._pick_best(candidates)
    # Alice's summed confidence (0.6) beats Bob's single mention (0.5).
    assert best["0"][0] == "Alice"
    assert best["0"][1] == pytest.approx(0.6)


# ── _vocab.surrounding_text ──────────────────────────────────────────────────


def test_surrounding_text_finds_markdown_image_and_nearest_heading(tmp_path: Path) -> None:
    """surrounding_text extracts context around an image ref, tagged with its heading."""
    import _vocab as vocab

    doc = tmp_path / "post.md"
    doc.write_text(
        "# Intro\n\nSome text.\n\n"
        "## The Golden Gate\n\n"
        "Here is a photo ![bridge](images/bridge.png) of the bridge.\n",
        encoding="utf-8",
    )
    ctx = vocab.surrounding_text(doc, tmp_path / "images" / "bridge.png", window=20)
    assert "The Golden Gate" in ctx
    assert "bridge.png" in ctx


def test_surrounding_text_no_match_returns_empty(tmp_path: Path) -> None:
    """surrounding_text returns "" when the image is never referenced in the doc."""
    import _vocab as vocab

    doc = tmp_path / "post.md"
    doc.write_text("No images here.\n", encoding="utf-8")
    assert vocab.surrounding_text(doc, tmp_path / "missing.png") == ""


# ── install_captions / install_diarize: _is_installed ───────────────────────


def test_install_captions_is_installed() -> None:
    """_is_installed reflects find_spec: a stdlib module is found, a bogus one isn't."""
    import install_captions as ic

    assert ic._is_installed("os") is True
    assert ic._is_installed("this_package_does_not_exist_xyz") is False


def test_install_diarize_is_installed() -> None:
    """_is_installed reflects find_spec: a stdlib module is found, a bogus one isn't."""
    import install_diarize as idz

    assert idz._is_installed("sys") is True
    assert idz._is_installed("this_package_does_not_exist_xyz") is False


# ── _argparse.make_parser ────────────────────────────────────────────────────


def test_make_parser_has_prog_description_and_version_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """make_parser wires prog/description through and pre-attaches -V/--version."""
    import _argparse as ap

    parser = ap.make_parser("my-prog", "Does a thing.", epilog="Example: my-prog --help")
    assert parser.prog == "my-prog"
    assert parser.description == "Does a thing."
    assert parser.epilog == "Example: my-prog --help"

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["-V"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "my-prog" in out and ap.SKILL_VERSION in out


def test_make_parser_help_flag_present_in_usage() -> None:
    """The parser accepts -h/--help without needing it registered explicitly."""
    import _argparse as ap

    parser = ap.make_parser("my-prog", "Does a thing.")
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])
    assert exc.value.code == 0


# ── _click: sprezzature_command / run_command ───────────────────────────────


def test_sprezzature_command_runs_and_returns_exit_code() -> None:
    """A command built via sprezzature_command runs and forwards its int return."""
    import _click as sc
    import click

    @sc.sprezzature_command("my-tool", help="Does a thing.")
    @click.option("--fail", is_flag=True)
    def cmd(fail: bool) -> int:
        return 1 if fail else 0

    assert sc.run_command(cmd, []) == 0
    assert sc.run_command(cmd, ["--fail"]) == 1


def test_sprezzature_command_none_return_means_success() -> None:
    """A command body that returns None is treated as exit code 0."""
    import _click as sc
    import click

    @sc.sprezzature_command("my-tool", help="Does a thing.")
    @click.option("--x", default=1)
    def cmd(x: int) -> None:
        return None

    assert sc.run_command(cmd, []) == 0


def test_run_command_usage_error_exits_2() -> None:
    """An unknown option raises Click's UsageError, mapped to SystemExit(2)."""
    import _click as sc
    import click

    @sc.sprezzature_command("my-tool", help="Does a thing.")
    @click.option("--known", default="x")
    def cmd(known: str) -> int:
        return 0

    with pytest.raises(SystemExit) as exc:
        sc.run_command(cmd, ["--unknown-flag"])
    assert exc.value.code == 2


def test_run_command_help_and_version_exit_0(capsys: pytest.CaptureFixture[str]) -> None:
    """--help and --version both print their message and report exit code 0.

    Click's ``standalone_mode=False`` swallows the internal ``Exit(0)`` for
    these two builtin eager options and returns ``None`` from ``main()``
    rather than raising, unlike a genuine usage error; ``run_command`` maps
    that ``None`` to ``0`` (see its "Defensive default" branch).
    """
    import _click as sc
    import click

    @sc.sprezzature_command("my-tool", help="Does a thing.")
    @click.option("--x", default=1)
    def cmd(x: int) -> int:
        return 0

    assert sc.run_command(cmd, ["--help"]) == 0
    assert "my-tool" in capsys.readouterr().out

    assert sc.run_command(cmd, ["--version"]) == 0
    assert sc.SKILL_VERSION in capsys.readouterr().out


def test_sprezzature_command_usage_line_shows_help_token() -> None:
    """SprezzatureCommand injects [--help] into the usage line Click renders."""
    import _click as sc
    import click.testing

    @sc.sprezzature_command("my-tool", help="Does a thing.")
    @click.option("--x", default=1)
    def cmd(x: int) -> int:
        return 0

    runner = click.testing.CliRunner()
    result = runner.invoke(cmd, ["--help"])
    assert "[--help]" in result.output
