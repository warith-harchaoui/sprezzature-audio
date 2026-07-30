FROM python:3.11-slim

LABEL maintainer="warith.harchaoui@gmail.com"
LABEL description="sprezzature-audio: speech-to-text and caption translation (base install, no heavy ML)"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

# Default: show captions help (heavy deps not present in base image)
CMD ["python", "scripts/captions_from_whisper.py", "--help"]
