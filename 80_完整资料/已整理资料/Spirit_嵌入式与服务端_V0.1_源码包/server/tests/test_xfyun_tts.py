import asyncio
import base64
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from usaki_server.audio.providers import AudioFormat, TextToSpeechProvider
from usaki_server.audio.xfyun_tts import (
    XfyunTextToSpeechProvider,
    XfyunTtsConfig,
    XfyunTtsError,
    build_xfyun_tts_url,
)


def test_build_xfyun_tts_url_contains_signed_query() -> None:
    url = build_xfyun_tts_url(
        api_key="970d334d",
        api_secret="6817e045c08d555e1800040fb42f5f20",
        now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "wss"
    assert parsed.netloc == "tts-api.xfyun.cn"
    assert parsed.path == "/v2/tts"
    assert query["host"] == ["tts-api.xfyun.cn"]
    assert query["date"] == ["Thu, 01 Jan 2026 00:00:00 GMT"]
    assert "authorization" in query


def test_xfyun_tts_provider_streams_audio_frames(monkeypatch) -> None:
    sent_payloads: list[dict] = []

    class FakeWebSocket:
        def __init__(self) -> None:
            self._frames = [
                {
                    "code": 0,
                    "data": {
                        "audio": base64.b64encode(b"pcm-").decode("ascii"),
                        "status": 1,
                    },
                },
                {
                    "code": 0,
                    "data": {
                        "audio": base64.b64encode(b"done").decode("ascii"),
                        "status": 2,
                    },
                },
            ]

        async def send(self, raw: str) -> None:
            sent_payloads.append(json.loads(raw))

        async def recv(self) -> str:
            return json.dumps(self._frames.pop(0))

    class FakeConnection:
        async def __aenter__(self) -> FakeWebSocket:
            return FakeWebSocket()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_connect(*args, **kwargs) -> FakeConnection:
        return FakeConnection()

    monkeypatch.setattr("usaki_server.audio.xfyun_tts.websockets.connect", fake_connect)

    provider = XfyunTextToSpeechProvider(
        XfyunTtsConfig(app_id="app", api_key="key", api_secret="secret")
    )

    async def run() -> None:
        chunks = [
            chunk async for chunk in provider.stream_synthesize("hello", AudioFormat())
        ]

        assert isinstance(provider, TextToSpeechProvider)
        assert chunks == [b"pcm-", b"done"]

    asyncio.run(run())
    assert sent_payloads[0]["data"]["status"] == 2
    assert sent_payloads[0]["data"]["text"] == base64.b64encode(b"hello").decode("ascii")


def test_xfyun_tts_provider_rejects_unsupported_audio_format() -> None:
    provider = XfyunTextToSpeechProvider(
        XfyunTtsConfig(app_id="app", api_key="key", api_secret="secret")
    )

    async def run() -> None:
        chunks = [
            chunk
            async for chunk in provider.stream_synthesize(
                "hello", AudioFormat(channels=2)
            )
        ]
        assert chunks == []

    with pytest.raises(XfyunTtsError):
        asyncio.run(run())
