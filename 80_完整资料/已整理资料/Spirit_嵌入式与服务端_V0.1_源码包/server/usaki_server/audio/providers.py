from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass
import logging
from typing import Union

import httpx

from usaki_server.llm.providers import LanguageModelProvider

logger = logging.getLogger(__name__)

AudioPayload = Union[bytes, list[bytes]]


@dataclass(frozen=True)
class AudioFormat:
    sample_rate_hz: int = 16000
    channels: int = 1
    sample_format: str = "pcm_s16le"


class SpeechToTextProvider:
    async def transcribe(self, audio: AudioPayload, audio_format: AudioFormat) -> str:
        raise NotImplementedError


class TextToSpeechProvider:
    async def stream_synthesize(
        self, text: str, audio_format: AudioFormat
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError


class HttpSpeechToTextProvider(SpeechToTextProvider):
    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url
        self._api_key = api_key

    async def transcribe(self, audio: AudioPayload, audio_format: AudioFormat) -> str:
        import io
        import wave
        pcm_data = b"".join(audio) if isinstance(audio, list) else audio
        # PCM S16LE → WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(audio_format.channels)
            wav_file.setsampwidth(2)  # 16bit = 2 bytes
            wav_file.setframerate(audio_format.sample_rate_hz)
            wav_file.writeframes(pcm_data)
        wav_buffer.seek(0)
        audio_base64 = base64.b64encode(wav_buffer.read()).decode("ascii")
        headers = _auth_headers(self._api_key)
        payload = {
            "audio_format": audio_format.__dict__,
            "audio_base64": audio_base64,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        logger.warning("STT response: %s", data)
        return str(data.get("text", "")).strip()


class HttpLanguageModelProvider(LanguageModelProvider):
    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url
        self._api_key = api_key

    async def stream_complete(
        self,
        text: str,
        device_id: str,
        memory_context: str | None = None,
    ) -> AsyncIterator[str]:
        headers = _auth_headers(self._api_key)
        payload = {"device_id": device_id, "text": text, "memory_context": memory_context or ""}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        completed = str(data.get("text", "")).strip()
        if completed:
            yield completed


class HttpTextToSpeechProvider(TextToSpeechProvider):
    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url
        self._api_key = api_key

    async def stream_synthesize(
        self, text: str, audio_format: AudioFormat
    ) -> AsyncIterator[bytes]:
        headers = _auth_headers(self._api_key)
        payload = {"text": text, "audio_format": audio_format.__dict__}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            data = response.json()
            audio_base64 = str(data.get("audio_base64", ""))
            if audio_base64:
                yield base64.b64decode(audio_base64)
            return
        if response.content:
            yield response.content


class StubSpeechToTextProvider(SpeechToTextProvider):
    async def transcribe(self, audio: AudioPayload, audio_format: AudioFormat) -> str:
        data = b"".join(audio) if isinstance(audio, list) else audio
        bytes_per_sample = 2  # 16bit
        sample_count = len(data) // bytes_per_sample
        seconds = sample_count / (audio_format.sample_rate_hz * audio_format.channels) if audio_format.sample_rate_hz else 0
        return f"received {seconds:.1f}s of {audio_format.sample_format} audio"


class StubLanguageModelProvider(LanguageModelProvider):
    async def stream_complete(
        self,
        text: str,
        device_id: str,
        memory_context: str | None = None,
    ) -> AsyncIterator[str]:
        del memory_context
        for chunk in ["I heard: ", text]:
            if chunk:
                yield chunk


class SilentTextToSpeechProvider(TextToSpeechProvider):
    async def stream_synthesize(
        self, text: str, audio_format: AudioFormat
    ) -> AsyncIterator[bytes]:
        duration_ms = max(500, min(2500, len(text) * 80))
        sample_count = audio_format.sample_rate_hz * duration_ms // 1000
        yield b"\x00\x00" * sample_count * audio_format.channels


@dataclass(frozen=True)
class VoiceProviders:
    stt: SpeechToTextProvider
    llm: LanguageModelProvider
    tts: TextToSpeechProvider


def _auth_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}
