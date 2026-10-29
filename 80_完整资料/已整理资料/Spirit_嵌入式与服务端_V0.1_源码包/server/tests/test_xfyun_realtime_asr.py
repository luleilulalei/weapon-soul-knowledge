from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from usaki_server.audio.xfyun_realtime_asr import (
    build_xfyun_realtime_asr_url,
    parse_xfyun_realtime_asr_text,
)


def test_build_xfyun_realtime_asr_url_contains_signed_query() -> None:
    url = build_xfyun_realtime_asr_url(
        api_key="970d334d",
        api_secret="6817e045c08d555e1800040fb42f5f20",
        now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "wss"
    assert parsed.netloc == "iat.cn-huabei-1.xf-yun.com"
    assert parsed.path == "/v1"
    assert query["host"] == ["iat.cn-huabei-1.xf-yun.com"]
    assert query["date"] == ["Thu, 01 Jan 2026 00:00:00 GMT"]
    assert "authorization" in query


def test_parse_xfyun_realtime_asr_text_from_ws_result() -> None:
    result = {"ws": [{"cw": [{"w": "hello"}]}, {"cw": [{"w": "Usaki"}]}]}

    assert parse_xfyun_realtime_asr_text(result) == "helloUsaki"


def test_parse_xfyun_realtime_asr_text_from_realtime_transcription_result() -> None:
    result = {
        "cn": {
            "st": {
                "rt": [
                    {"ws": [{"cw": [{"w": "good"}]}, {"cw": [{"w": "morning"}]}]},
                    {"ws": [{"cw": [{"w": "Usaki"}]}]},
                ]
            }
        }
    }

    assert parse_xfyun_realtime_asr_text(result) == "goodmorningUsaki"
