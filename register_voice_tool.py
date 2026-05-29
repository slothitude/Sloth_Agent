"""Register voice tool (speech_to_text + text_to_speech) as OpenWebUI custom tool."""
import json
import urllib.request
import sys

BASE = "http://192.168.0.33:3000"
EMAIL = "aaron@slothitude.com"
PASSWORD = "Sloth2026!"

# Get token
req = urllib.request.Request(
    f"{BASE}/api/v1/auths/signin",
    data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())["token"]

# Check if voice tool already exists
req = urllib.request.Request(
    f"{BASE}/api/v1/tools/",
    headers={"Authorization": f"Bearer {token}"},
)
resp = urllib.request.urlopen(req)
tools = json.loads(resp.read().decode())
existing = {t["id"]: t for t in tools}

# Delete old voice tool if exists
for t in tools:
    if t.get("name") == "voice" or t.get("id", "").startswith("voice"):
        del_req = urllib.request.Request(
            f"{BASE}/api/v1/tools/{t['id']}",
            headers={"Authorization": f"Bearer {token}"},
            method="DELETE",
        )
        urllib.request.urlopen(del_req)
        print(f"Deleted old tool: {t['id']}")

# Create voice tool
tool_body = {
    "id": "voice",
    "name": "voice",
    "meta": {
        "description": "Voice I/O tools — speech-to-text (Whisper) and text-to-speech (Kokoro). STT server on port 8007, TTS on port 8006."
    },
    "content": '''"""
title: Voice I/O
description: Speech-to-text and text-to-speech tools
required_open_webui_version: 0.3.0
version: 0.1.0
"""

import json
import urllib.request
import base64


class Tools:
    def __init__(self):
        pass

    def speech_to_text(self, audio_base64: str, language: str = "") -> str:
        """
        Transcribe audio to text using Whisper STT server.
        :param audio_base64: Base64-encoded audio data (WAV/MP3).
        :param language: Language code (empty = auto-detect).
        :return: Transcribed text.
        """
        body = json.dumps({
            "audio": audio_base64,
            "language": language or None,
        }).encode()
        req = urllib.request.Request(
            "http://192.168.0.33:8007/v1/audio/transcriptions/json",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        return data.get("text", "")

    def text_to_speech(self, text: str, voice: str = "af_bella", speed: float = 1.0) -> str:
        """
        Convert text to speech audio using Kokoro TTS server.
        :param text: Text to convert to speech.
        :param voice: Voice name (af_bella, af_nicole, af_sarah, af_sky, am_adam, am_michael, bf_emma, bf_isabella, bm_george, bm_lewis, ff_siwis).
        :param speed: Speech speed multiplier (default 1.0).
        :return: Base64-encoded WAV audio.
        """
        body = json.dumps({"text": text, "voice": voice, "speed": speed}).encode()
        req = urllib.request.Request(
            "http://192.168.0.33:8006/tts",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=60)
        wav_bytes = resp.read()
        audio_b64 = base64.b64encode(wav_bytes).decode()
        return audio_b64

    def list_voices(self) -> str:
        """
        List available TTS voices.
        :return: JSON list of available voice names.
        """
        req = urllib.request.Request("http://192.168.0.33:8006/voices")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        return json.dumps(data.get("voices", []))
''',
    "access_control": None,
}

req = urllib.request.Request(
    f"{BASE}/api/v1/tools/create",
    data=json.dumps(tool_body).encode(),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
    method="POST",
)
try:
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read().decode())
    print(f"Voice tool registered: {result.get('id', 'ok')}")
except urllib.error.HTTPError as e:
    err = e.read().decode()
    print(f"Error: {e.code} {err}")
