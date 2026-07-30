"""
sprezzature_audio -- speech-to-text, diarization, and caption translation.

Local-first pipeline: Whisper for transcription, NeMo Sortformer for speaker
diarization, TitaNet for speaker identification, and a local LLM for translation.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""
from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Warith Harchaoui"
__email__ = "warith.harchaoui@gmail.com"
