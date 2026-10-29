import asyncio

from usaki_server.api.model import VoiceInputEndData, VoiceInputStartData
from usaki_server.audio.eye_emotions import eye_animation_for_text, eye_emotion_for_text
from usaki_server.audio.providers import AudioFormat, VoiceProviders
from usaki_server.audio.voice_interaction import VoiceInteractionFlow
from usaki_server.audio.voice_session import VoiceSession
from usaki_server.config import Settings


class FixedSpeechToTextProvider:
    def __init__(self, text: str) -> None:
        self._text = text

    async def transcribe(self, audio, audio_format: AudioFormat) -> str:
        del audio, audio_format
        return self._text


class FixedLanguageModelProvider:
    async def stream_complete(self, text: str, device_id: str, memory_context: str | None = None):
        del text, device_id, memory_context
        yield "收到。"


class FailingTextToSpeechProvider:
    async def stream_synthesize(self, text: str, audio_format: AudioFormat):
        del text, audio_format
        if False:
            yield b""
        raise RuntimeError("tts failed")


def test_eye_emotion_keyword_mapping() -> None:
    assert eye_emotion_for_text("来一个星星眼").emotion == "star"
    assert eye_emotion_for_text("心心眼一下").emotion == "heart"
    assert eye_emotion_for_text("怒目瞪眼").emotion == "angry"
    assert eye_emotion_for_text("发火眼").emotion == "fire"
    assert eye_emotion_for_text("有点委屈").emotion == "wronged"
    assert eye_emotion_for_text("恢复正常").emotion == "idle"
    assert eye_emotion_for_text("摇摇耳朵") is None


def test_eye_animation_keyword_mapping() -> None:
    assert eye_animation_for_text("眨眨眼").name == "blink"
    assert eye_animation_for_text("星星眼") is None


def test_eye_emotion_is_sent_before_tts_can_fail() -> None:
    async def run() -> None:
        providers = VoiceProviders(
            stt=FixedSpeechToTextProvider("来一个心心眼，再眨眨眼"),
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

        assert frames[0].message_type == "emotion.update"
        assert frames[0].data["emotion"] == "heart"
        assert frames[1].message_type == "eye.animation"
        assert frames[1].data["name"] == "blink"
        assert frames[2].message_type is None
        assert frames[2].data["reason"] == "tts_error"

    asyncio.run(run())
