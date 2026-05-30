FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Kokoro TTS
RUN pip install --no-cache-dir \
    kokoro-onnx \
    soundfile \
    numpy

# Whisper STT (CPU — fast enough for base model)
RUN pip install --no-cache-dir \
    faster-whisper

WORKDIR /app

COPY tts_server_kokoro.py .
COPY stt_server.py .
COPY openai_audio_proxy.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8005 8006 8007

VOLUME /models/kokoro
VOLUME /root/.cache/huggingface

ENTRYPOINT ["/app/entrypoint.sh"]
