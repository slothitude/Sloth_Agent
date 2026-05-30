#!/usr/bin/env python3
"""Kokoro TTS Server - Fast ONNX-based text-to-speech on GPU.
Runs on Lappy (RTX 3060 6GB). Port 8006.
"""

import os
import sys
import json
import io
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

os.environ["PYTHONWARNINGS"] = "ignore"
import warnings
warnings.filterwarnings("ignore")

PORT = int(os.environ.get("PORT", 8006))
MODEL_DIR = r"C:\Users\aaron\hotswap\kokoro-models"
ONNX_PATH = os.path.join(MODEL_DIR, "kokoro-v1.0.onnx")
VOICES_PATH = os.path.join(MODEL_DIR, "voices-v1.0.bin")

import re
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from kokoro_onnx.config import MAX_PHONEME_LENGTH

print(f"Loading Kokoro TTS model...", flush=True)
kokoro = Kokoro(ONNX_PATH, VOICES_PATH)
print(f"Kokoro TTS loaded. Listening on :{PORT}", flush=True)

VOICES = [
    "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael",
    "bf_emma", "bf_isabella",
    "bm_george", "bm_lewis",
    "ff_siwis",
]

# ~250 chars per chunk keeps us well under MAX_PHONEME_LENGTH (510 tokens)
CHUNK_MAX_CHARS = 250
# 0.15s silence between chunks at 24kHz = 3600 samples
PAUSE_SAMPLES = 3600


def _split_sentences(text):
    """Split text into sentence-aligned chunks under CHUNK_MAX_CHARS."""
    # Split on sentence-ending punctuation, keeping the delimiter with the sentence
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current = ""
    for s in sentences:
        if not s.strip():
            continue
        if len(current) + len(s) + 1 <= CHUNK_MAX_CHARS:
            current = (current + " " + s).strip() if current else s.strip()
        else:
            if current:
                chunks.append(current)
            # If a single sentence exceeds limit, force-split on commas/spaces
            if len(s) > CHUNK_MAX_CHARS:
                words = s.split()
                current = ""
                for w in words:
                    if len(current) + len(w) + 1 <= CHUNK_MAX_CHARS:
                        current = (current + " " + w).strip() if current else w
                    else:
                        if current:
                            chunks.append(current)
                        current = w
            else:
                current = s.strip()
    if current:
        chunks.append(current)
    return chunks


def _generate_with_chunking(text, voice, speed, lang):
    """Generate audio with explicit sentence-level chunking + pause padding.

    Bypasses Kokoro's internal auto-batch concatenation which has aggressive
    silence trimming that can cut off audio on long text.
    """
    chunks = _split_sentences(text)
    if len(chunks) == 1:
        # Short text — no chunking needed
        return kokoro.create(chunks[0], voice=voice, speed=speed, lang=lang)

    all_samples = []
    sample_rate = None
    pause = np.zeros(PAUSE_SAMPLES, dtype=np.float32)

    for i, chunk in enumerate(chunks):
        samples, sr = kokoro.create(chunk, voice=voice, speed=speed, lang=lang)
        if sample_rate is None:
            sample_rate = sr
        all_samples.append(samples)
        if i < len(chunks) - 1:
            all_samples.append(pause)

    return np.concatenate(all_samples), sample_rate


class TTSHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            self._json(200, {"status": "ok", "model": "kokoro-v1.0"})
        elif path == "/voices":
            self._json(200, {"voices": VOICES})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        path = self.path.split("?")[0]

        if path == "/tts":
            self._handle_tts(body)
        else:
            self._json(404, {"error": "not found"})

    def _handle_tts(self, body):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid json"})

        text = data.get("text", "")
        if not text:
            return self._json(400, {"error": "text is required"})

        voice = data.get("voice", "af_bella")
        speed = float(data.get("speed", 1.0))
        lang = data.get("language", "en-us")
        if not lang:
            lang = "en-us"

        try:
            import time as _time
            t0 = _time.time()
            samples, sample_rate = _generate_with_chunking(
                text, voice=voice, speed=speed, lang=lang
            )
            t1 = _time.time()

            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format="WAV")
            buf.seek(0)
            wav_bytes = buf.read()

            audio_dur = len(samples) / sample_rate
            gen_time = t1 - t0
            print(
                f"TTS: {len(text)} chars, {voice}, "
                f"{gen_time:.2f}s -> {audio_dur:.2f}s audio "
                f"({audio_dur/gen_time:.1f}x realtime)",
                flush=True,
            )

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav_bytes)))
            self.send_header("X-Gen-Time", f"{gen_time:.3f}")
            self.send_header("X-Audio-Duration", f"{audio_dur:.3f}")
            self.send_header("X-Speed", f"{audio_dur/gen_time:.2f}")
            self.end_headers()
            self.wfile.write(wav_bytes)
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"error": str(e)})

    def _json(self, code, data):
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception:
            pass

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), TTSHandler).serve_forever()
