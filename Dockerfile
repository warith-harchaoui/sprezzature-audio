FROM python:3.11-slim

LABEL maintainer="warithmetics@deraison.ai"
LABEL description="sprezzature-audio: captions, speaker attribution, caption metrics and narration"

WORKDIR /app

# The two halves pip cannot supply.
#
# ffmpeg: every path that starts from a media file goes through it, directly
# or through audio-helper / video-helper, which fall back to it.
#
# espeak-ng: Kokoro phonemises through it. The base install declares
# `espeakng-loader`, a wheel carrying a built copy, and that copy is the
# fallback, not the plan — the system package is what the code looks for
# first. It is GPL, and it is reached as a separate binary through ctypes, the
# way a program calls ffmpeg; installing it here keeps that arrangement, it
# does not link it into anything.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        espeak-ng \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# One install, no extras: since 2026-11-01 everything this package does is in
# the base, nemo_toolkit[asr] and torch included. The API still serves only
# the fast, model-free routes (see the module docstring in api.py:
# transcription and diarization belong behind a job queue, not a synchronous
# HTTP call); the long tools run as commands in this same image.
RUN pip install --no-cache-dir .

EXPOSE 8000

# Serve what the image was built for. A CMD of `--help` is a container that
# starts, prints and exits — which looks like it works and does nothing.
# Override with any of the command lines:
#
#   docker run --rm -v "$PWD:/work" IMAGE sprezzature-audio-captions /work/talk.mp4
CMD ["uvicorn", "sprezzature_audio.api:app", "--host", "0.0.0.0", "--port", "8000"]
