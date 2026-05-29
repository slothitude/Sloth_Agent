#!/usr/bin/env python3
"""OpenAI-compatible audio proxy for OpenWebUI.

Translates OpenAI /audio/speech and /audio/transcriptions calls
to our Kokoro TTS (:8006) and Whisper STT (:8007) servers.
"""

import json
import io
import os
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

TTS_URL = os.environ.get("TTS_URL", "http://localhost:8006")
STT_URL = os.environ.get("STT_URL", "http://localhost:8007")
PORT = int(os.environ.get("PORT", 8005))

import urllib.request
import urllib.error


class ProxyHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok", "proxy": "openai-audio"})
        elif self.path == "/models":
            self._json(200, {"data": [{"id": "kokoro-v1.0"}]})
        elif self.path == "/audio/models":
            self._json(200, {"data": [{"id": "kokoro-v1.0"}]})
        elif self.path == "/audio/voices":
            try:
                req = urllib.request.Request(f"{TTS_URL}/voices")
                resp = urllib.request.urlopen(req, timeout=5)
                data = json.loads(resp.read().decode())
                self._json(200, data)
            except Exception as e:
                self._json(500, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/audio/speech":
            self._handle_tts()
        elif path == "/audio/transcriptions":
            self._handle_stt()
        else:
            self._json(404, {"error": "not found"})

    def _handle_tts(self):
        """Proxy TTS: OpenAI format -> Kokoro format."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid json"})

        text = data.get("input", "")
        voice = data.get("voice", "af_bella")
        speed = float(data.get("speed", 1.0))

        if not text:
            return self._json(400, {"error": "input is required"})

        try:
            tts_body = json.dumps({"text": text, "voice": voice, "speed": speed}).encode()
            req = urllib.request.Request(
                f"{TTS_URL}/tts",
                data=tts_body,
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=60)
            wav_bytes = resp.read()

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav_bytes)))
            self.end_headers()
            self.wfile.write(wav_bytes)
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"error": str(e)})

    def _handle_stt(self):
        """Proxy STT: forward multipart to Whisper server."""
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            req = urllib.request.Request(
                f"{STT_URL}/v1/audio/transcriptions",
                data=body,
                headers={"Content-Type": content_type},
            )
            resp = urllib.request.urlopen(req, timeout=30)
            result = resp.read()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)
        except urllib.error.HTTPError as e:
            err = e.read()
            self._json(e.code, json.loads(err) if err else {"error": str(e)})
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
    print(f"OpenAI Audio Proxy on :{PORT} -> TTS:{TTS_URL} STT:{STT_URL}", flush=True)
    HTTPServer(("0.0.0.0", PORT), ProxyHandler).serve_forever()
