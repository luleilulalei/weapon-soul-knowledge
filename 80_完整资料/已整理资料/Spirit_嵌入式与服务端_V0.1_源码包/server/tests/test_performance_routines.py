import asyncio

from usaki_server.agent.profile import build_agent_system_prompt
from usaki_server.audio import voice_interaction
from usaki_server.audio.performance_routines import (
    SHOTA_WAIST_TWIST_ROUTINE,
    load_motion_script,
    motion_routine_for_text,
    output_start_eye_emotion_for_text,
    post_response_eye_emotion_for_text,
    pre_response_eye_emotion_for_text,
    scripted_reply_for_text,
)
from usaki_server.audio.providers import AudioFormat, VoiceProviders
from usaki_server.audio.voice_interaction import VoiceInteractionFlow
from usaki_server.audio.voice_session import VoiceSession
from usaki_server.api.model import VoiceInputEndData, VoiceInputStartData
from usaki_server.config import Settings


class FixedSpeechToTextProvider:
    def __init__(self, text: str) -> None:
        self._text = text

    async def transcribe(self, audio, audio_format: AudioFormat) -> str:
        del audio, audio_format
        return self._text


class FailingLanguageModelProvider:
    async def stream_complete(self, text: str, device_id: str, memory_context: str | None = None):
        del text, device_id, memory_context
        raise AssertionError("scripted routine should not call the LLM")
        yield ""


class ShortTextToSpeechProvider:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def stream_synthesize(self, text: str, audio_format: AudioFormat):
        self.texts.append(text)
        yield b"\x00\x00" * (audio_format.sample_rate_hz * audio_format.channels * 60 // 1000)


def test_shota_performance_prompt_is_in_agent_profile() -> None:
    prompt = build_agent_system_prompt("base", "usaki_server/agent/usaki")

    assert "隔壁来了个正太" in prompt
    assert "可我早就不扭了。" in prompt
    assert "什么，把我的领带拿来。" in prompt


def test_shota_performance_triggers_scripted_reply_and_motion_routine() -> None:
    assert scripted_reply_for_text("隔壁来了个正太，他靠扭腰吸引了很多妹子，我们都扭不过他") == "可我早就不扭了。"
    assert scripted_reply_for_text("可是语数也在") == "什么，把我的领带拿来。"
    assert scripted_reply_for_text("emo也在") == "什么，把我的领带拿来。"
    assert motion_routine_for_text("可是语数也在") == SHOTA_WAIST_TWIST_ROUTINE
    assert motion_routine_for_text("emo也在") == SHOTA_WAIST_TWIST_ROUTINE
    assert motion_routine_for_text("隔壁来了个正太，他靠扭腰吸引了很多妹子") is None


def test_shota_performance_eye_cues() -> None:
    setup_text = "隔壁来了个正太，他靠扭腰吸引了很多妹子，我们都扭不过他"
    trigger_text = "可是语数也在"

    assert pre_response_eye_emotion_for_text(setup_text).emotion == "idle"
    assert output_start_eye_emotion_for_text(setup_text).emotion == "idle"
    assert post_response_eye_emotion_for_text(setup_text) is None

    pre_trigger = pre_response_eye_emotion_for_text(trigger_text)
    output_start_trigger = output_start_eye_emotion_for_text(trigger_text)
    post_trigger = post_response_eye_emotion_for_text(trigger_text)

    assert pre_trigger.emotion == "angry"
    assert pre_trigger.duration_ms == 8000
    assert output_start_trigger.emotion == "angry"
    assert output_start_trigger.duration_ms == 8000
    assert post_trigger.emotion == "star"
    assert post_trigger.duration_ms == 33000


def test_shota_motion_script_shape() -> None:
    script = load_motion_script(SHOTA_WAIST_TWIST_ROUTINE)

    assert script is not None
    assert script["duration_ms"] == 30000
    assert script["tracks"]["left_ear"] == []
    assert script["tracks"]["right_ear"] == []
    assert len(script["tracks"]["body"]) > 40
    assert len(script["tracks"]["left_arm"]) > 20
    assert len(script["tracks"]["right_arm"]) > 20


def test_scripted_voice_turn_starts_motion_after_voice(monkeypatch) -> None:
    async def run() -> None:
        starts: list[tuple[str, str]] = []

        async def fake_start_motion_routine(device_id: str, routine: str) -> bool:
            starts.append((device_id, routine))
            return True

        monkeypatch.setattr(voice_interaction, "start_motion_routine", fake_start_motion_routine)

        tts = ShortTextToSpeechProvider()
        providers = VoiceProviders(
            stt=FixedSpeechToTextProvider("可是语数也在"),
            llm=FailingLanguageModelProvider(),
            tts=tts,
        )
        flow = VoiceInteractionFlow(VoiceSession(Settings(audio_vad_provider="rms"), providers))
        flow.start_input(data=VoiceInputStartData(), device_id="test-device")
        flow._session._buffer._append_chunk(b"audio", b"\x00\x00" * 960)

        frames = [
            frame
            async for frame in flow.finish_input(
                VoiceInputEndData(reason="vad_end"),
                device_id="test-device",
                seq=1,
            )
        ]

        assert not any(frame.message_type == "body.action" for frame in frames)
        assert tts.texts == ["什么，把我的领带拿来。"]
        assert starts == [("test-device", SHOTA_WAIST_TWIST_ROUTINE)]
        json_frames = [frame for frame in frames if frame.kind == "json"]
        json_types = [_frame_message_type(frame) for frame in json_frames]
        assert json_types == [
            "emotion.update",
            "voice.output.start",
            "emotion.update",
            "voice.output.end",
            "emotion.update",
        ]
        assert json_frames[0].data["emotion"] == "angry"
        assert json_frames[2].data["emotion"] == "angry"
        assert json_frames[3].data["reason"] == "finished"
        assert json_frames[4].data["emotion"] == "star"

    asyncio.run(run())


def test_scripted_setup_turn_uses_idle_eyes_without_motion(monkeypatch) -> None:
    async def run() -> None:
        starts: list[tuple[str, str]] = []

        async def fake_start_motion_routine(device_id: str, routine: str) -> bool:
            starts.append((device_id, routine))
            return True

        monkeypatch.setattr(voice_interaction, "start_motion_routine", fake_start_motion_routine)

        tts = ShortTextToSpeechProvider()
        providers = VoiceProviders(
            stt=FixedSpeechToTextProvider("隔壁来了个正太，他靠扭腰吸引了很多妹子，我们都扭不过他"),
            llm=FailingLanguageModelProvider(),
            tts=tts,
        )
        flow = VoiceInteractionFlow(VoiceSession(Settings(audio_vad_provider="rms"), providers))
        flow.start_input(data=VoiceInputStartData(), device_id="test-device")
        flow._session._buffer._append_chunk(b"audio", b"\x00\x00" * 960)

        frames = [
            frame
            async for frame in flow.finish_input(
                VoiceInputEndData(reason="vad_end"),
                device_id="test-device",
                seq=1,
            )
        ]

        assert tts.texts == ["可我早就不扭了。"]
        assert starts == []
        json_frames = [frame for frame in frames if frame.kind == "json"]
        json_types = [_frame_message_type(frame) for frame in json_frames]
        assert json_types == [
            "emotion.update",
            "voice.output.start",
            "emotion.update",
            "voice.output.end",
        ]
        assert json_frames[0].data["emotion"] == "idle"
        assert json_frames[2].data["emotion"] == "idle"
        assert json_frames[3].data["reason"] == "finished"

    asyncio.run(run())


def _frame_message_type(frame) -> str:
    if frame.message_type is not None:
        return frame.message_type
    if isinstance(frame.data, dict) and "reason" in frame.data:
        return "voice.output.end"
    return "voice.output.start"
