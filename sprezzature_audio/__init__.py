"""
sprezzature_audio: turn a recording into a transcript that names its speakers.

Feed the package an audio or video file and it works out, in sequence,
what was said, when each speaker took their turn, who that speaker
actually is, and, if asked, what all of it translates to in another
language. A five-minute meeting recording, for instance, becomes a text
file where each line carries a timestamp, a speaker's name, and the
words they spoke.

Four models, one per question, each wrapped by one script under
`scripts/`:

- Whisper (through the `vocal-helper` package) turns sound into text: this
  is "automatic speech recognition," or ASR.
- NeMo's Sortformer model marks *who* spoke *when*, without yet knowing
  anyone's name: this step is called diarization.
- NeMo's TitaNet model turns a short voice sample into a fixed-length list
  of numbers (an "embedding"), so two samples from the same person land
  close together and two different people land far apart; matching a
  diarized speaker against a labelled reference sample this way is how a
  name gets attached.
- A local LLM (reached through Ollama, no cloud call) translates the
  transcript into another language once it has speaker labels.

Every step runs on the machine that calls it: no audio or text is sent to
a remote server unless the caller explicitly configures a remote LLM.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

__version__ = "1.1.0"
__author__ = "Warith HARCHAOUI"
__email__ = "warith.harchaoui@gmail.com"
