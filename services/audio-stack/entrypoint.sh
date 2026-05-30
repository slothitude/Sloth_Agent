#!/bin/bash
set -e

echo "=== Audio Stack Starting ==="

# Kokoro TTS on :8006
KOKORO_MODEL_DIR="${KOKORO_MODEL_DIR:-/models/kokoro}"
export KOKORO_MODEL_DIR

echo "Starting Kokoro TTS on :8006 (model: ${KOKORO_MODEL_DIR})"
python tts_server_kokoro.py &
TTS_PID=$!
echo "TTS PID: ${TTS_PID}"

# Whisper STT on :8007
export WHISPER_MODEL="${WHISPER_MODEL:-base}"
export WHISPER_DEVICE="${WHISPER_DEVICE:-cpu}"
export WHISPER_COMPUTE_TYPE="${WHISPER_COMPUTE_TYPE:-int8}"
export PORT=8007

echo "Starting Whisper STT on :8007 (model: ${WHISPER_MODEL}, device: ${WHISPER_DEVICE})"
python stt_server.py &
STT_PID=$!
echo "STT PID: ${STT_PID}"

# Audio Proxy on :8005
export TTS_URL="${TTS_URL:-http://localhost:8006}"
export STT_URL="${STT_URL:-http://localhost:8007}"
export PORT=8005

echo "Starting Audio Proxy on :8005 -> TTS:${TTS_URL} STT:${STT_URL}"
python openai_audio_proxy.py &
PROXY_PID=$!
echo "Proxy PID: ${PROXY_PID}"

echo "=== All services started ==="

# Wait for any to exit
wait -n $TTS_PID $STT_PID $PROXY_PID 2>/dev/null
EXIT=$?
echo "=== Service exited (code ${EXIT}), shutting down ==="
kill $TTS_PID $STT_PID $PROXY_PID 2>/dev/null
exit $EXIT
