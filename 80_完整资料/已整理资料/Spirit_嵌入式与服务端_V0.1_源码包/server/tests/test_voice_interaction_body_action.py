import asyncio

from usaki_server.api.model import VoiceInputEndData, VoiceInputStartData
from usaki_server.audio.providers import AudioFormat, VoiceProviders
from usaki_server.audio.voice_interaction import VoiceInteractionFlow
from usaki_server.audio.voice_session import VoiceSession
from usaki_server.config import Settings


class FixedSpeechToTextProvider:
    async def transcribe(self, audio, audio_format: AudioFormat) -> str:
        del audio, audio_format
        return "摇摇耳朵"


class FixedLanguageModelProvider:
    async def stream_complete(self, text: str, device_id: str, memory_context: str | None = None):
        del text, device_id, memory_context
        yield "好呀。"


class FailingTextToSpeechProvider:
    async def stream_synthesize(self, text: str, audio_format: AudioFormat):
        del text, audio_format
        if False:
            yield b""
        raise RuntimeError("tts failed")


def test_body_action_is_sent_before_tts_can_fail() -> None:
    async def run() -> None:
        providers = VoiceProviders(
            stt=FixedSpeechToTextProvider(),
            llm=FixedLanguageModelProvider(),
            tts=FailingTextToSpeechProvider(),
        )
        flow = VoiceInteractionFlow(
            VoiceSession(Settings(audio_vad_provider="rms"), providers)
        )
        flow.start_input(
            data=VoiceInputStartData(),
            device_id="test-device",
        )
        flow._session._buffer._append_chunk(b"audio", b"\x00\x00" * 960)

        frames = [
            frame
            async for frame in flow.finish_input(
                VoiceInputEndData(reason="vad_end"),
                device_id="test-device",
                seq=1,
            )
        ]

        assert frames[0].message_type == "body.action"
        assert frames[0].data["actions"][0]["part"] == "both_ears"
        assert frames[1].message_type is None
        assert frames[1].data["reason"] == "tts_error"

    asyncio.run(run())
