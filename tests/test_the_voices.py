"""
The voices, and the one clock they share.

These moved here with `narrate_openvoice` and `narrate_chatterbox` when the
voices left `sprezzature-publish`. Captions turn sound into timed text and
narration turns text into timed sound; one package owns the modality in both
directions, and the tests that read these wrappers' source belong beside the
source they read.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import narrate_chatterbox  # noqa: E402


class TestChatterboxEmotionMap:
    def test_neutral_at_half_intensity_is_base(self):
        v = narrate_chatterbox.emotion_to_exaggeration("neutral", 0.5)
        assert v == pytest.approx(0.5)

    def test_cheerful_intensity_dial(self):
        low = narrate_chatterbox.emotion_to_exaggeration("cheerful", 0.0)
        mid = narrate_chatterbox.emotion_to_exaggeration("cheerful", 0.5)
        high = narrate_chatterbox.emotion_to_exaggeration("cheerful", 1.0)
        assert low < mid < high
        assert 0.0 <= low <= 2.0
        assert 0.0 <= high <= 2.0

    def test_unknown_emotion_falls_back_to_neutral(self):
        v = narrate_chatterbox.emotion_to_exaggeration("nope", 0.5)
        assert v == pytest.approx(0.5)

    def test_extreme_intensity_clamped(self):
        v = narrate_chatterbox.emotion_to_exaggeration("angry", 999.0)
        assert 0.0 <= v <= 2.0


# ── site_indexes audio enclosure ───────────────────────────────────────────




class TestBothEnginesShareOneClock:
    """The defect was not in a function; it was in two copies of a loop.

    ``pause_before_ms`` went missing from ``narrate_chatterbox`` and
    ``narrate_openvoice`` identically, because each carried its own
    hand-rolled conversion from milliseconds to samples. No unit test of a
    pure function could see that: the value was read correctly, clamped
    correctly, stored correctly, and then not used.

    So these read the wrappers' source. Crude, and the right shape for
    "nothing calls this" -- which is invisible to every test that calls it.
    """

    ENGINES = ("narrate_chatterbox", "narrate_openvoice")

    def _source(self, name: str) -> str:
        import importlib

        return Path(importlib.import_module(name).__file__).read_text(encoding="utf-8")

    #: The call that actually spends the pause, not a mention of its name. The
    #: first draft of this test asserted `"pause_before_ms" in source` and was
    #: satisfied by the comment *explaining* the fix -- it stayed green with
    #: the fix itself deleted, which is the exact failure mode it was written
    #: to prevent.
    SPENDS = 'timeline.silence(seg.get("{key}", 0))'

    @pytest.mark.parametrize("engine", ENGINES)
    def test_the_engine_spends_the_pause_before_a_segment(self, engine):
        assert self.SPENDS.format(key="pause_before_ms") in self._source(engine), (
            f"{engine} never spends pause_before_ms; the silence that sets a "
            "heading apart from what precedes it is computed and dropped"
        )

    @pytest.mark.parametrize("engine", ENGINES)
    def test_the_engine_spends_the_pause_after_a_segment(self, engine):
        assert self.SPENDS.format(key="pause_after_ms") in self._source(engine)

    @pytest.mark.parametrize("engine", ENGINES)
    def test_no_engine_converts_milliseconds_to_samples_by_hand(self, engine):
        """One clock, or the two drift again.

        Both wrappers used to spell the conversion out inline. That is what
        made the omission duplicable, and what would make the next one
        duplicable too, so the arithmetic now lives in `_vtt.Timeline`
        and nowhere else.
        """
        source = self._source(engine)
        assert "/ 1000.0" not in source, (
            f"{engine} converts milliseconds to samples itself; use "
            "_vtt.Timeline so both engines share one clock"
        )
        assert "_vtt.Timeline(" in source

    @pytest.mark.parametrize("engine", ENGINES)
    def test_the_engine_writes_cues_beside_its_audio(self, engine):
        source = self._source(engine)
        assert "speech_to_vtt" in source and "narration.vtt" in source
