import asyncio
import json
import time

from fastapi.testclient import TestClient

from usaki_server.api import voice_input as voice_input_api
from usaki_server.api.model import now_ms
from usaki_server.audio.providers import (
    AudioFormat,
    SilentTextToSpeechProvider,
    StubLanguageModelProvider,
    StubSpeechToTextProvider,
    VoiceProviders,
)
from usaki_server.audio.transport_codec import TransportAudioFormat, create_transport_codec
from usaki_server.audio.voice_interaction import VoiceInteractionFlow
from usaki_server.audio.voice_session import VoiceSession
from usaki_server.config import Settings, get_settings
from usaki_server.global_providers import set_voice_providers
from usaki_server.main import app


def _message(message_type: str, seq: int, data: dict | None = None) -> dict:
    return {
        "id": f"msg_{seq}",
        "type": message_type,
        "device_id": "test-device",
        "timestamp": now_ms(),
        "seq": seq,
        "data": data or {},
    }


class FailingTextToSpeechProvider:
    async def stream_synthesize(self, text: str, audio_format: AudioFormat):
        del text, audio_format
        if False:
            yield b""
        raise RuntimeError("11201: licc failed")


class FakeWebSocket:
    query_params: dict[str, str] = {}


class NeverFinalizingFlow:
    active_device_id = "test-device"
    input_audio_bytes = 0

    def append_audio(self, chunk: bytes) -> bool:
        self.input_audio_bytes += len(chunk)
        return False


def test_voice_protocol_websocket_accepts_voice_audio_turn() -> None:
    voice_input_api._voice_flow_cache.clear()
    settings = get_settings()
    providers = VoiceProviders(
        stt=StubSpeechToTextProvider(),
        llm=StubLanguageModelProvider(),
        tts=SilentTextToSpeechProvider(),
    )
    set_voice_providers(providers)
    flow = VoiceInteractionFlow(
        VoiceSession(
            settings,
            providers,
        )
    )
    voice_input_api._voice_flow_cache["test-device"] = flow
    input_codec = create_transport_codec(TransportAudioFormat(codec="opus"))
    frame_samples = input_codec.format.sample_rate_hz * input_codec.format.frame_duration_ms // 1000
    opus_packets = input_codec.encode_pcm_stream(b"\xff\x7f" * frame_samples)

    client = TestClient(app)

    with client.websocket_connect(
        "/api/v1/voice/voice?device_id=test-device&token=test-token"
    ) as websocket:
        websocket.send_json(_message("voice.input.start", 2))
        for packet in opus_packets:
            websocket.send_bytes(packet)
        websocket.send_json(_message("voice.input.end", 3, {"reason": "vad_end"}))

        response = websocket.receive_json()
        assert response["type"] == "voice.output.start"
        assert response["data"]["codec"] == "opus"
        assert response["data"]["output_id"]

        message = websocket.receive()
        assert message.get("bytes")

        while True:
            message = websocket.receive()
            if message.get("text"):
                response = json.loads(message["text"])
                break

        assert response["type"] == "voice.output.end"
        assert response["data"]["reason"] == "finished"


def test_voice_protocol_returns_end_when_tts_fails() -> None:
    voice_input_api._voice_flow_cache.clear()
    settings = get_settings()
    providers = VoiceProviders(
        stt=StubSpeechToTextProvider(),
        llm=StubLanguageModelProvider(),
        tts=FailingTextToSpeechProvider(),
    )
    set_voice_providers(providers)
    flow = VoiceInteractionFlow(VoiceSession(settings, providers))
    voice_input_api._voice_flow_cache["test-device"] = flow
    input_codec = create_transport_codec(TransportAudioFormat(codec="opus"))
    frame_samples = input_codec.format.sample_rate_hz * input_codec.format.frame_duration_ms // 1000
    opus_packets = input_codec.encode_pcm_stream(b"\xff\x7f" * frame_samples)

    client = TestClient(app)

    with client.websocket_connect(
        "/api/v1/voice/voice?device_id=test-device&token=test-token"
    ) as websocket:
        websocket.send_json(_message("voice.input.start", 2))
        for packet in opus_packets:
            websocket.send_bytes(packet)
        websocket.send_json(_message("voice.input.end", 3, {"reason": "vad_end"}))

        response = websocket.receive_json()

        assert response["type"] == "voice.output.end"
        assert response["data"]["reason"] == "tts_error"


def test_voice_flow_cache_reuses_flow_for_same_device() -> None:
    voice_input_api._voice_flow_cache.clear()
    settings = get_settings()
    providers = VoiceProviders(
        stt=StubSpeechToTextProvider(),
        llm=StubLanguageModelProvider(),
        tts=SilentTextToSpeechProvider(),
    )

    flow_a = voice_input_api._get_or_create_voice_flow("device-a", settings, providers)
    flow_b = voice_input_api._get_or_create_voice_flow("device-a", settings, providers)
    flow_c = voice_input_api._get_or_create_voice_flow("device-b", settings, providers)

    assert flow_a is flow_b
    assert flow_c is not flow_a


def test_voice_connection_hard_caps_input_when_device_end_is_missing() -> None:
    async def run() -> None:
        providers = VoiceProviders(
            stt=StubSpeechToTextProvider(),
            llm=StubLanguageModelProvider(),
            tts=SilentTextToSpeechProvider(),
        )
        handler = voice_input_api.VoiceConnectionHandler(
            FakeWebSocket(),
            Settings(
                audio_vad_provider="rms",
                audio_server_vad_auto_end=False,
                audio_max_utterance_ms=1,
            ),
            providers,
        )
        handler.flow = NeverFinalizingFlow()
        handler.state.device_id = "test-device"
        handler._current_request_id = "voice_req_test"
        handler._input_started_at = time.monotonic() - 1
        spawned = []
        handler._spawn_voice_output_turn = spawned.append

        await handler._handle_binary(b"audio")

        assert handler._input_turn_finalized is True
        assert spawned
        assert spawned[0].reason == "max_utterance"

    asyncio.run(run())
