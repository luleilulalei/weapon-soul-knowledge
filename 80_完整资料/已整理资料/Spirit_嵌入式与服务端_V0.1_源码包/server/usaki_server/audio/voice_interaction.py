from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import logging
import time
import uuid

from usaki_server.api.model import (
    VoiceInputEndData,
    VoiceInputStartData,
    VoiceOutputCancelData,
    VoiceOutputEndData,
    VoiceOutputStartData,
)
from usaki_server.audio.transport_codec import (
    DEFAULT_OPUS_FRAME_DURATION_MS,
    TransportAudioFormat,
)
from usaki_server.audio.body_actions import body_actions_for_text
from usaki_server.audio.eye_emotions import eye_animation_for_text, eye_emotion_for_text
from usaki_server.audio.performance_routines import (
    motion_routine_for_text,
    output_start_eye_emotion_for_text,
    post_response_eye_emotion_for_text,
    pre_response_eye_emotion_for_text,
    scripted_reply_for_text,
    start_motion_routine,
)
from usaki_server.audio.voice_session import VoiceSession
from usaki_server.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VoiceOutputFrame:
    """A transport-neutral frame produced by one voice interaction turn."""

    kind: str
    data: dict | bytes
    message_type: str | None = None

    @classmethod
    def json(cls, data: dict, *, message_type: str | None = None) -> "VoiceOutputFrame":
        return cls(kind="json", data=data, message_type=message_type)

    @classmethod
    def binary(cls, data: bytes) -> "VoiceOutputFrame":
        return cls(kind="binary", data=data)


class VoiceInteractionFlow:
    """Coordinates voice input audio with STT -> LLM -> TTS.

    This class is intentionally independent of FastAPI/WebSocket so the API layer only
    adapts transport messages and does not import concrete provider implementations.
    """

    def __init__(self, session: VoiceSession) -> None:
        self._session = session
        self._active_device_id: str | None = None
        self._input_audio_bytes = 0
        self._output_format = TransportAudioFormat(
            codec="opus",
            sample_rate_hz=self._session.audio_format.sample_rate_hz,
            channels=self._session.audio_format.channels,
            sample_bits=16,
            frame_duration_ms=DEFAULT_OPUS_FRAME_DURATION_MS,
        )

    @property
    def input_audio_bytes(self) -> int:
        return self._input_audio_bytes

    @property
    def active_device_id(self) -> str | None:
        return self._active_device_id

    def start_input(self, data: VoiceInputStartData, *, device_id: str) -> None:
        self._active_device_id = device_id
        self._input_audio_bytes = 0
        expected = self._session.audio_format
        input_format = TransportAudioFormat(
            codec=data.codec.lower(),
            sample_rate_hz=data.sample_rate,
            channels=data.channels,
            sample_bits=data.sample_bits,
            frame_duration_ms=data.frame_duration_ms,
        )
        self._session.configure_input(input_format)
        vad_source = str(data.vad.get("source", "")).strip().lower()
        trust_device_vad = bool(data.vad.get("enabled", True)) and vad_source.startswith(
            "device"
        )
        self._session.begin_input(trust_external_vad=trust_device_vad)
        if (
            data.codec.lower() != "opus"
            or data.sample_rate != expected.sample_rate_hz
            or data.channels != expected.channels
            or data.sample_bits != 16
            or data.frame_duration_ms != DEFAULT_OPUS_FRAME_DURATION_MS
        ):
            raise ValueError(
                "unsupported voice input format: "
                f"got {data.codec}/{data.sample_rate}Hz/{data.channels}ch/"
                f"{data.sample_bits}bit/{data.frame_duration_ms}ms, "
                f"expected opus/{expected.sample_rate_hz}Hz/{expected.channels}ch/16bit/"
                f"{DEFAULT_OPUS_FRAME_DURATION_MS}ms"
            )
        logger.warning(
            "[USAKI DIAG] voice.input.start device_id=%s codec=opus sample_rate=%s channels=%s "
            "frame_ms=%s vad_source=%s trust_device_vad=%s",
            device_id,
            expected.sample_rate_hz,
            expected.channels,
            data.frame_duration_ms,
            vad_source,
            trust_device_vad,
        )

    def append_audio(self, chunk: bytes) -> bool:
        if self._active_device_id is None:
            return False
        self._input_audio_bytes += len(chunk)
        result = self._session.append_audio(chunk)
        # logger.warning(
        #     "[USAKI DIAG] append_audio chunk_len=%d total_bytes=%d vad_finalized=%s",
        #     len(chunk),
        #     self._input_audio_bytes,
        #     result,
        # )
        return result

    def cancel_input(self) -> None:
        self._active_device_id = None
        self._input_audio_bytes = 0
        if self._session.has_audio():
            self._session.pop_audio()
        logger.warning("[USAKI DIAG] cancel_input")

    async def finish_input(
        self,
        data: VoiceInputEndData,
        *,
        device_id: str,
        seq: int,
    ) -> AsyncIterator[VoiceOutputFrame]:
        output_id = f"voice_out_{uuid.uuid4().hex[:12]}"
        turn_started_at = time.perf_counter()
        request_id = data.request_id
        input_audio_bytes = self._input_audio_bytes
        self._active_device_id = None
        self._input_audio_bytes = 0

        if not self._session.has_audio():
            logger.warning(
                "[USAKI DIAG] finish_input: no audio buffered, returning empty_input"
            )
            yield VoiceOutputFrame.json(
                VoiceOutputEndData(
                    output_id=output_id,
                    request_id=request_id,
                    reason="empty_input",
                    duration_ms=data.duration_ms,
                ).model_dump(exclude_none=True)
            )
            return

        logger.warning(
            "[USAKI DIAG] finish_input: calling transcribe_buffered_audio() audio_bytes=%d",
            input_audio_bytes,
        )
        stt_started_at = time.perf_counter()
        user_text = (await self._session.transcribe_buffered_audio()).strip()
        stt_done_at = time.perf_counter()
        logger.warning(
            "[USAKI DIAG] STT result: device_id=%s bytes=%d text=[%s]",
            device_id,
            input_audio_bytes,
            user_text,
        )
        logger.warning(
            "[USAKI PERF] stt_done device_id=%s output_id=%s stt_ms=%.0f since_finish_ms=%.0f",
            device_id,
            output_id,
            (stt_done_at - stt_started_at) * 1000,
            (stt_done_at - turn_started_at) * 1000,
        )
        if not user_text:
            logger.warning(
                "[USAKI DIAG] STT returned empty text, returning empty_speech"
            )
            yield VoiceOutputFrame.json(
                VoiceOutputCancelData(
                    output_id=output_id,
                    request_id=request_id,
                    reason="empty_speech",
                ).model_dump(exclude_none=True),
                message_type="voice.output.cancel",
            )
            return

        legacy_body = get_settings().device_profile == "usaki"
        scripted_reply = scripted_reply_for_text(user_text) if legacy_body else None
        motion_routine = motion_routine_for_text(user_text) if legacy_body else None
        pre_response_eye_emotion = pre_response_eye_emotion_for_text(user_text)
        output_start_eye_emotion = output_start_eye_emotion_for_text(user_text)
        post_response_eye_emotion = post_response_eye_emotion_for_text(user_text)
        body_action = body_actions_for_text(user_text) if legacy_body and not motion_routine else None
        eye_emotion = pre_response_eye_emotion or eye_emotion_for_text(user_text)
        eye_animation = eye_animation_for_text(user_text)

        logger.warning(
            "[USAKI DIAG] starting voice output pipeline user_text=[%s] scripted_reply=%s "
            "motion_routine=%s body_actions=%d eye_emotion=%s output_start_eye=%s "
            "post_response_eye=%s eye_animation=%s",
            user_text,
            scripted_reply or "",
            motion_routine or "",
            len(body_action.actions) if body_action is not None else 0,
            eye_emotion.emotion if eye_emotion is not None else "",
            output_start_eye_emotion.emotion if output_start_eye_emotion is not None else "",
            post_response_eye_emotion.emotion if post_response_eye_emotion is not None else "",
            eye_animation.name if eye_animation is not None else "",
        )

        if body_action is not None and body_action.actions:
            logger.warning(
                "[USAKI DIAG] body.action before voice output device_id=%s output_id=%s actions=%d",
                device_id,
                output_id,
                len(body_action.actions),
            )
            yield VoiceOutputFrame.json(
                body_action.model_dump(exclude_none=True),
                message_type="body.action",
            )

        if eye_emotion is not None:
            logger.warning(
                "[USAKI DIAG] emotion.update before voice output device_id=%s output_id=%s emotion=%s",
                device_id,
                output_id,
                eye_emotion.emotion,
            )
            yield VoiceOutputFrame.json(
                eye_emotion.model_dump(exclude_none=True),
                message_type="emotion.update",
            )

        if eye_animation is not None:
            logger.warning(
                "[USAKI DIAG] eye.animation before voice output device_id=%s output_id=%s name=%s",
                device_id,
                output_id,
                eye_animation.name,
            )
            yield VoiceOutputFrame.json(
                eye_animation.model_dump(exclude_none=True),
                message_type="eye.animation",
            )

        audio_bytes = 0
        chunk_count = 0
        output_started = False
        try:
            if scripted_reply:
                output_stream = self._session.stream_transport_fixed_text(
                    scripted_reply,
                    self._output_format,
                )
            else:
                output_stream = self._session.stream_transport_response_from_text(
                    user_text,
                    device_id,
                    self._output_format,
                )
            async for chunk in output_stream:
                chunk_count += 1
                if not chunk.audio:
                    # logger.warning(
                    #     "[USAKI DIAG] TTS text_chunk[%d] text=[%s] no_audio=True",
                    #     chunk_count,
                    #     chunk.text,
                    # )
                    continue
                audio_bytes += len(chunk.audio)
                if not output_started:
                    logger.warning(
                        "[USAKI DIAG] first output audio ready device_id=%s output_id=%s first_packet=%dB",
                        device_id,
                        output_id,
                        len(chunk.audio),
                    )
                    logger.warning(
                        "[USAKI PERF] first_output_audio device_id=%s output_id=%s total_ms=%.0f "
                        "after_stt_ms=%.0f",
                        device_id,
                        output_id,
                        (time.perf_counter() - turn_started_at) * 1000,
                        (time.perf_counter() - stt_done_at) * 1000,
                    )
                    yield VoiceOutputFrame.json(
                        VoiceOutputStartData(
                            output_id=output_id,
                            request_id=request_id,
                            codec=self._output_format.codec,
                            sample_rate=self._output_format.sample_rate_hz,
                            channels=self._output_format.channels,
                            sample_bits=self._output_format.sample_bits,
                            frame_duration_ms=self._output_format.frame_duration_ms,
                            play_mode="stream",
                        ).model_dump(exclude_none=True)
                    )
                    output_started = True
                    if output_start_eye_emotion is not None:
                        logger.warning(
                            "[USAKI DIAG] emotion.update after voice output start "
                            "device_id=%s output_id=%s emotion=%s",
                            device_id,
                            output_id,
                            output_start_eye_emotion.emotion,
                        )
                        yield VoiceOutputFrame.json(
                            output_start_eye_emotion.model_dump(exclude_none=True),
                            message_type="emotion.update",
                        )
                # logger.warning(
                #     "[USAKI DIAG] TTS audio_chunk[%d] text=[%s] audio_len=%d",
                #     chunk_count,
                #     chunk.text,
                #     len(chunk.audio),
                # )
                yield VoiceOutputFrame.binary(chunk.audio)
        except Exception as exc:
            logger.warning(
                "[USAKI DIAG] voice output synthesis failed device_id=%s output_id=%s error=%s",
                device_id,
                output_id,
                exc,
            )
            yield VoiceOutputFrame.json(
                VoiceOutputEndData(
                    output_id=output_id,
                    request_id=request_id,
                    reason="tts_error",
                    duration_ms=data.duration_ms,
                ).model_dump(exclude_none=True)
            )
            return

        logger.warning(
            "[USAKI DIAG] voice output done device_id=%s output_id=%s total_chunks=%d audio_bytes=%d",
            device_id,
            output_id,
            chunk_count,
            audio_bytes,
        )
        yield VoiceOutputFrame.json(
            VoiceOutputEndData(
                output_id=output_id,
                request_id=request_id,
                reason="finished",
                duration_ms=data.duration_ms,
            ).model_dump(exclude_none=True)
        )
        if post_response_eye_emotion is not None:
            logger.warning(
                "[USAKI DIAG] emotion.update after voice output end "
                "device_id=%s output_id=%s emotion=%s",
                device_id,
                output_id,
                post_response_eye_emotion.emotion,
            )
            yield VoiceOutputFrame.json(
                post_response_eye_emotion.model_dump(exclude_none=True),
                message_type="emotion.update",
            )
        if motion_routine:
            await start_motion_routine(device_id, motion_routine)
