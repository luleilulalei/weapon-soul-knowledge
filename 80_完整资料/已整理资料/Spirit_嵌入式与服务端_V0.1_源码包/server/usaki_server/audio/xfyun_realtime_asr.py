from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any
from urllib.parse import urlencode

import websockets
from websockets.asyncio.client import ClientConnection

from usaki_server.audio.providers import AudioFormat, AudioPayload, SpeechToTextProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class XfyunRealtimeAsrConfig:
    app_id: str
    api_key: str
    api_secret: str
    host: str = "iat.cn-huabei-1.xf-yun.com"
    path: str = "/v1"
    language: str = "zh_cn"
    domain: str = "slm"
    accent: str = "mandarin"
    vad_eos_ms: int = 3000


@dataclass(frozen=True)
class XfyunRealtimeAsrResult:
    text: str
    is_final: bool = False
    is_correction: bool = False
    raw_result: dict[str, Any] | None = None


class XfyunRealtimeAsrError(RuntimeError):
    pass


class XfyunRealtimeAsrStream:
    """Xfyun realtime ASR large-model WebSocket client."""

    def __init__(self, config: XfyunRealtimeAsrConfig, audio_format: AudioFormat) -> None:
        self._config = config
        self._audio_format = audio_format
        self._ws: ClientConnection | None = None
        self._started = False
        self._closed = False

    async def __aenter__(self) -> "XfyunRealtimeAsrStream":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def connect(self) -> None:
        if self._ws is not None:
            return
        if self._audio_format.channels != 1:
            raise XfyunRealtimeAsrError(f"unsupported channels: {self._audio_format.channels}")

        url = build_xfyun_realtime_asr_url(
            api_key=self._config.api_key,
            api_secret=self._config.api_secret,
            host=self._config.host,
            path=self._config.path,
        )
        self._ws = await websockets.connect(url, max_size=4 * 1024 * 1024)

    async def send_audio(self, chunk: bytes, *, is_last: bool = False) -> None:
        if self._closed:
            return
        await self.connect()
        assert self._ws is not None

        status = 0 if not self._started else 1
        if is_last:
            status = 2
        payload: dict[str, Any] = {
            "data": {
                "status": status,
                "format": f"audio/L16;rate={self._audio_format.sample_rate_hz}",
                "encoding": "raw",
                "audio": base64.b64encode(chunk).decode("ascii"),
            }
        }
        if not self._started:
            payload["common"] = {"app_id": self._config.app_id}
            payload["business"] = {
                "language": self._config.language,
                "domain": self._config.domain,
                "accent": self._config.accent,
                "vad_eos": self._config.vad_eos_ms,
            }
            self._started = True

        await self._ws.send(json.dumps(payload, ensure_ascii=False))
        if is_last:
            self._closed = True

    async def receive_result(self) -> XfyunRealtimeAsrResult | None:
        if self._ws is None:
            return None
        raw = await self._ws.recv()
        data = json.loads(raw)
        code = int(data.get("code", 0))
        if code != 0:
            message = data.get("message") or data.get("desc") or "xfyun realtime asr error"
            raise XfyunRealtimeAsrError(f"{code}: {message}")

        frame_data = data.get("data", {})
        result = frame_data.get("result")
        if not isinstance(result, dict):
            return None
        text = parse_xfyun_realtime_asr_text(result)
        response_status = int(frame_data.get("status", 0))
        return XfyunRealtimeAsrResult(
            text=text,
            is_final=response_status == 2,
            is_correction=str(result.get("pgs", "")) == "rpl",
            raw_result=result,
        )

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None


class XfyunRealtimeSpeechToTextProvider(SpeechToTextProvider):
    def __init__(self, config: XfyunRealtimeAsrConfig) -> None:
        self._config = config

    async def transcribe(self, audio: AudioPayload, audio_format: AudioFormat) -> str:
        started_at = time.perf_counter()
        pcm_data = b"".join(audio) if isinstance(audio, list) else audio
        # 按 60ms 帧切分 PCM (960 samples * 2 bytes = 1920 bytes)
        frame_size = 960 * 2  # 60ms@16kHz, S16LE
        frames = [pcm_data[i:i+frame_size] for i in range(0, len(pcm_data), frame_size)]
        text_parts: list[str] = []
        async with XfyunRealtimeAsrStream(self._config, audio_format) as stream:
            connected_at = time.perf_counter()
            for frame in frames:
                if frame:
                    await stream.send_audio(frame)
            await stream.send_audio(b"", is_last=True)
            sent_at = time.perf_counter()
            logger.warning(
                "[USAKI PERF] xfyun_asr_sent frames=%d audio_ms=%.0f connect_ms=%.0f send_ms=%.0f",
                len(frames),
                len(pcm_data) / (audio_format.sample_rate_hz * audio_format.channels * 2) * 1000
                if audio_format.sample_rate_hz and audio_format.channels
                else 0,
                (connected_at - started_at) * 1000,
                (sent_at - connected_at) * 1000,
            )

            first_result_logged = False
            while True:
                result = await stream.receive_result()
                if result is None:
                    continue
                if not first_result_logged:
                    first_result_logged = True
                    logger.warning(
                        "[USAKI PERF] xfyun_asr_first_result ms=%.0f text_len=%d",
                        (time.perf_counter() - sent_at) * 1000,
                        len(result.text),
                    )
                if result.text:
                    text_parts.append(result.text)
                if result.is_final:
                    text = "".join(text_parts).strip()
                    logger.warning(
                        "[USAKI PERF] xfyun_asr_final total_ms=%.0f after_send_ms=%.0f text_len=%d",
                        (time.perf_counter() - started_at) * 1000,
                        (time.perf_counter() - sent_at) * 1000,
                        len(text),
                    )
                    return text


def build_xfyun_realtime_asr_url(
    *,
    api_key: str,
    api_secret: str,
    host: str = "iat.cn-huabei-1.xf-yun.com",
    path: str = "/v1",
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


def parse_xfyun_realtime_asr_text(result: dict[str, Any]) -> str:
    pieces: list[str] = []
    _collect_words(result.get("ws", []), pieces)

    cn = result.get("cn")
    if isinstance(cn, dict):
        st = cn.get("st")
        if isinstance(st, dict):
            for rt in st.get("rt", []):
                if isinstance(rt, dict):
                    _collect_words(rt.get("ws", []), pieces)

    return "".join(pieces).strip()


def _collect_words(words: Any, pieces: list[str]) -> None:
    if not isinstance(words, list):
        return
    for item in words:
        if not isinstance(item, dict):
            continue
        candidates = item.get("cw") or item.get("word") or []
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            word = candidate.get("w") or candidate.get("word") or candidate.get("text") or ""
            if word:
                pieces.append(str(word))
