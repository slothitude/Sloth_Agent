#!/usr/bin/env python3
"""Whisper STT Server — fast speech-to-text on CPU.

Endpoints:
  GET  /health                              - health + model status
  GET  /models                              - list available model sizes
  POST /v1/audio/transcriptions             - multipart file upload
  POST /v1/audio/transcriptions/raw         - raw audio body (wav/mp3/etc)
  POST /v1/audio/transcriptions/json        - JSON body with base64 audio
"""

import os
import io
import json
import time
import base64
import tempfile
import traceback

os.environ["PYTHONWARNINGS"] = "ignore"
import warnings
warnings.filterwarnings("ignore")

from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

PORT = int(os.environ.get("PORT", 8007))
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
LANGUAGE = os.environ.get("WHISPER_LANGUAGE", None)  # None = auto-detect

# ── Eager model loading ────────────────────────────────────────────────────────
print(f"Loading Whisper '{MODEL_SIZE}' on {DEVICE} ({COMPUTE_TYPE})...", flush=True)
from faster_whisper import WhisperModel
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print(f"Whisper STT ready on :{PORT}", flush=True)


# ── Helpers ─────────────────────────────────────────────────────────────────────

def transcribe(audio_bytes, language=None):
    """Transcribe audio bytes, return (text, language, duration, elapsed)."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        t0 = time.time()
        lang_param = language or LANGUAGE
        segments, info = model.transcribe(
            tmp,
            beam_size=5,
            language=lang_param,
        )
        text = " ".join(seg.text for seg in segments).strip()
        elapsed = time.time() - t0
        return text, info.language, info.duration, elapsed
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def parse_multipart(body, content_type):
    fields = {}
    if "boundary=" not in content_type:
        return fields
    boundary = content_type.split("boundary=")[-1].strip()
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]
    boundary = boundary.encode()
    parts = body.split(b"--" + boundary)
    for part in parts:
        if not part or part.strip() in (b"", b"--", b"--\r\n"):
            continue
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        headers_raw = part[:header_end].decode(errors="replace")
        part_body = part[header_end + 4:]
        if part_body.endswith(b"\r\n"):
            part_body = part_body[:-2]
        name = None
        for line in headers_raw.split("\r\n"):
            if "name=" in line:
                for seg in line.split(";"):
                    seg = seg.strip()
                    if seg.startswith("name="):
                        name = seg.split("=", 1)[1].strip('"')
                        break
        if name:
            fields[name] = part_body
    return fields


# ── HTTP Handler ────────────────────────────────────────────────────────────────

class STTHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            self._json(200, {
                "status": "ok",
                "model": MODEL_SIZE,
                "device": DEVICE,
                "loaded": True,
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        ct = self.headers.get("Content-Type", "")
        path = self.path.split("?")[0]

        if path == "/v1/audio/transcriptions":
            # Multipart form upload (OpenAI-compatible)
            fields = parse_multipart(body, ct)
            audio = fields.get("file")
            lang = fields.get("language")
            if isinstance(lang, bytes):
                lang = lang.decode()
            if not audio:
                return self._json(400, {"error": "no file uploaded"})
            self._do_transcribe(audio, lang)

        elif path == "/v1/audio/transcriptions/raw":
            # Raw audio bytes in body
            if not body:
                return self._json(400, {"error": "empty body"})
            self._do_transcribe(body, None)

        elif path == "/v1/audio/transcriptions/json":
            # JSON with base64-encoded audio
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self._json(400, {"error": "invalid json"})
            audio_b64 = data.get("audio", "")
            lang = data.get("language")
            if not audio_b64:
                return self._json(400, {"error": "audio field required (base64)"})
            try:
                audio = base64.b64decode(audio_b64)
            except Exception:
                return self._json(400, {"error": "invalid base64"})
            self._do_transcribe(audio, lang)

        else:
            self._json(404, {"error": "not found"})

    def _do_transcribe(self, audio_bytes, language):
        try:
            text, lang, audio_dur, elapsed = transcribe(audio_bytes, language)
            rtf = elapsed / audio_dur if audio_dur > 0 else 0
            print(
                f"STT: {len(audio_bytes)} bytes, "
                f"{elapsed:.2f}s for {audio_dur:.2f}s audio "
                f"({rtf:.2f}x RTF) [{lang}] \"{text[:80]}\"",
                flush=True,
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Transcribe-Time", f"{elapsed:.3f}")
            self.send_header("X-Audio-Duration", f"{audio_dur:.3f}")
            self.send_header("X-Language", lang)
            self.send_header("X-RTF", f"{rtf:.3f}")
            self.end_headers()
            self.wfile.write(json.dumps({
                "text": text,
                "language": lang,
                "duration": round(audio_dur, 3),
                "transcribe_time": round(elapsed, 3),
            }).encode())
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
    server = HTTPServer(("0.0.0.0", PORT), STTHandler)
    server.daemon_threads = True
    server.serve_forever()
