from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any
from urllib.parse import urlencode

import websockets

from usaki_server.audio.providers import AudioFormat, TextToSpeechProvider


@dataclass(frozen=True)
class XfyunTtsConfig:
    app_id: str
    api_key: str
    api_secret: str
    host: str = "tts-api.xfyun.cn"
    path: str = "/v2/tts"
    voice_name: str = "xiaoyan"
    speed: int = 50
    volume: int = 50
    pitch: int = 50
    background_sound: int = 0
    timeout_seconds: float = 30


class XfyunTtsError(RuntimeError):
    pass


class XfyunTextToSpeechProvider(TextToSpeechProvider):
    """Xfyun online TTS provider with streaming PCM output."""

    def __init__(self, config: XfyunTtsConfig) -> None:
        self._config = config

    async def stream_synthesize(
        self, text: str, audio_format: AudioFormat
    ) -> AsyncIterator[bytes]:
        text = text.strip()
        if not text:
            return
        _validate_audio_format(audio_format)

        url = build_xfyun_tts_url(
            api_key=self._config.api_key,
            api_secret=self._config.api_secret,
            host=self._config.host,
            path=self._config.path,
        )
        payload = _build_xfyun_tts_payload(text, audio_format, self._config)

        async with websockets.connect(
            url,
            max_size=8 * 1024 * 1024,
            open_timeout=self._config.timeout_seconds,
            close_timeout=self._config.timeout_seconds,
        ) as websocket:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            while True:
                raw = await websocket.recv()
                audio, is_final = _decode_xfyun_tts_frame(raw)
                if audio:
                    yield audio
                if is_final:
                    break


def _validate_audio_format(audio_format: AudioFormat) -> None:
    if audio_format.sample_format != "pcm_s16le":
        raise XfyunTtsError(f"unsupported sample_format: {audio_format.sample_format}")
    if audio_format.channels != 1:
        raise XfyunTtsError(f"unsupported channels: {audio_format.channels}")


def _build_xfyun_tts_payload(
    text: str,
    audio_format: AudioFormat,
    config: XfyunTtsConfig,
) -> dict[str, Any]:
    return {
        "common": {"app_id": config.app_id},
        "business": {
            "aue": "raw",
            "auf": f"audio/L16;rate={audio_format.sample_rate_hz}",
            "vcn": config.voice_name,
            "speed": config.speed,
            "volume": config.volume,
            "pitch": config.pitch,
            "bgs": config.background_sound,
            "tte": "UTF8",
        },
        "data": {
            "status": 2,
            "text": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        },
    }


def _decode_xfyun_tts_frame(raw: str | bytes) -> tuple[bytes, bool]:
    data = json.loads(raw)
    code = int(data.get("code", 0))
    if code != 0:
        message = data.get("message") or data.get("desc") or "xfyun tts error"
        raise XfyunTtsError(f"{code}: {message}")

    frame_data = data.get("data", {})
    audio_base64 = frame_data.get("audio")
    audio = base64.b64decode(audio_base64) if audio_base64 else b""
    return audio, int(frame_data.get("status", 0)) == 2


def build_xfyun_tts_url(
    *,
    api_key: str,
    api_secret: str,
    host: str = "tts-api.xfyun.cn",
    path: str = "/v2/tts",
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    date = format_datetime(now.astimezone(timezone.utc), usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("ascii")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
    query = urlencode({"authorization": authorization, "date": date, "host": host})
    return f"wss://{host}{path}?{query}"
