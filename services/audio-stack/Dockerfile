FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Kokoro TTS dependencies
RUN pip install --no-cache-dir \
    kokoro-onnx \
    soundfile \
    numpy

# Whisper STT dependencies (CPU by default, GPU if nvidia runtime available)
RUN pip install --no-cache-dir \
    faster-whisper

WORKDIR /app

# Copy all 3 server scripts
COPY tts_server_kokoro.py .
COPY stt_server.py .
COPY openai_audio_proxy.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8005 8006 8007

# Model volumes
VOLUME /models/kokoro
VOLUME /models/whisper

ENTRYPOINT ["/app/entrypoint.sh"]
