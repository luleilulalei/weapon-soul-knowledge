from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from usaki_server.api.model import (
    ErrorData,
    SensorUpdateData,
    TouchEventData,
    VoiceInputCancelData,
    VoiceInputEndData,
    VoiceInputStartData,
    VoiceWakeDetectedData,
    VoiceInterruptData,
    WsMessage,
    WsProtocolState,
    build_ws_message,
    error_response,
)
from usaki_server.audio.providers import VoiceProviders
from usaki_server.audio.provider_factory import create_voice_providers
from usaki_server.audio.voice_interaction import VoiceInteractionFlow, VoiceOutputFrame
from usaki_server.audio.voice_session import VoiceSession
from usaki_server.config import get_settings, Settings
from usaki_server.devices.registry import device_registry
from usaki_server.global_providers import get_voice_providers

router = APIRouter()
logger = logging.getLogger(__name__)
_voice_flow_cache: dict[str, VoiceInteractionFlow] = {}
_OUTPUT_INITIAL_BURST_FRAMES = 2


def _get_or_create_voice_flow(
    device_id: str,
    settings: Settings,
    providers: VoiceProviders | None = None,
) -> VoiceInteractionFlow:
    flow = _voice_flow_cache.get(device_id)
    if flow is not None:
        return flow
    flow = VoiceInteractionFlow(VoiceSession(settings, _resolve_voice_providers(settings, providers)))
    _voice_flow_cache[device_id] = flow
    return flow


def _resolve_voice_providers(
    settings: Settings,
    providers: VoiceProviders | None = None,
) -> VoiceProviders:
    if providers is not None:
        return providers
    try:
        return get_voice_providers()
    except AssertionError:
        return create_voice_providers(settings)


class VoiceConnectionHandler:
    """每个 WebSocket 连接对应一个独立实例，借鉴 xiaozhi ConnectionHandler 的按连接隔离模式。"""

    def __init__(
        self,
        websocket: WebSocket,
        settings: Settings,
        providers: VoiceProviders,
    ) -> None:
        self.websocket = websocket
        self.settings = settings
        self.state = WsProtocolState()
        initial_device_id = websocket.query_params.get("device_id")
        self.flow = (
            _get_or_create_voice_flow(initial_device_id, settings, providers)
            if initial_device_id
            else VoiceInteractionFlow(VoiceSession(settings, providers))
        )
        self._send_queue: asyncio.Queue[VoiceOutputFrame | None] = asyncio.Queue()
        self._send_task: asyncio.Task | None = None
        self._process_tasks: set[asyncio.Task] = set()
        self._server_vad_endpoint_logged = False
        self._server_vad_too_early_logged = False
        self._input_turn_finalized = False
        self._current_request_id: str | None = None
        self._input_started_at: float | None = None

    async def handle(self) -> None:
        await self.websocket.accept()

        self.state.device_id = self.websocket.query_params.get("device_id")

        self._send_task = asyncio.create_task(self._send_loop())

        try:
            while True:
                incoming = await self.websocket.receive()
                if incoming.get("type") == "websocket.disconnect":
                    break

                if incoming.get("bytes") is not None:
                    await self._handle_binary(incoming["bytes"])
                    continue

                raw_text = incoming.get("text")
                if raw_text is None:
                    continue

                await self._handle_text(raw_text)
        except WebSocketDisconnect:
            logger.warning(
                "[USAKI CONNECTION] websocket disconnected device_id=%s",
                self.state.device_id,
            )
        except Exception as exc:
            logger.error(
                "[USAKI CONNECTION] connection error device_id=%s: %s",
                self.state.device_id,
                exc,
            )
        finally:
            for task in self._process_tasks:
                task.cancel()
            self._send_queue.put_nowait(None)
            if self._send_task is not None:
                await self._send_task
            logger.warning(
                "[USAKI CONNECTION] connection closed device_id=%s",
                self.state.device_id,
            )

    async def _send_loop(self) -> None:
        """后台发送协程：从队列取 frame 并发送，不阻塞接收循环。"""
        output_frame_duration_seconds = 0.0
        output_burst_frames_remaining = 0
        while True:
            frame = await self._send_queue.get()
            if frame is None:
                break

            if frame.kind == "binary":
                await self.websocket.send_bytes(frame.data)
                if output_burst_frames_remaining > 0:
                    output_burst_frames_remaining -= 1
                elif output_frame_duration_seconds > 0:
                    await asyncio.sleep(output_frame_duration_seconds)
                continue

            data = frame.data
            message_type = frame.message_type or (
                "voice.output.end"
                if isinstance(data, dict) and "reason" in data
                else "voice.output.start"
            )
            if message_type == "voice.output.start" and isinstance(data, dict):
                output_frame_duration_seconds = _frame_duration_seconds(data)
                output_burst_frames_remaining = _OUTPUT_INITIAL_BURST_FRAMES
            elif message_type in {"voice.output.end", "voice.output.cancel"}:
                output_frame_duration_seconds = 0.0
                output_burst_frames_remaining = 0
            await self._send_ws_message(
                build_ws_message(
                    message_id=f"msg_{uuid.uuid4().hex}",
                    message_type=message_type,
                    device_id=self.state.device_id or "unknown",
                    seq=self.state.seq,
                    data=data,
                ),
            )

    async def _handle_binary(self, chunk: bytes) -> None:
        if self._input_turn_finalized:
            return
        should_finalize = self.flow.append_audio(chunk)
        self.state.input_audio_bytes = self.flow.input_audio_bytes
        input_duration_ms = self._input_duration_ms()

        if (
            self.flow.active_device_id is not None
            and input_duration_ms is not None
            and input_duration_ms >= self.settings.audio_max_utterance_ms
        ):
            logger.warning(
                "[USAKI VOICE] max utterance reached; finalizing input "
                "duration_ms=%d max_ms=%d",
                input_duration_ms,
                self.settings.audio_max_utterance_ms,
            )
            self._finalize_current_input(reason="max_utterance")
            return

        if should_finalize and self.flow.active_device_id is not None:
            min_auto_end_ms = self.settings.audio_server_vad_auto_end_min_input_ms
            if not self.settings.audio_server_vad_auto_end:
                if not self._server_vad_endpoint_logged:
                    self._server_vad_endpoint_logged = True
                    logger.warning(
                        "[USAKI VOICE] server vad endpoint observed; waiting for device "
                        "voice.input.end duration_ms=%s",
                        input_duration_ms,
                    )
            elif input_duration_ms is not None and input_duration_ms >= min_auto_end_ms:
                if not self._server_vad_endpoint_logged:
                    self._server_vad_endpoint_logged = True
                    logger.warning(
                        "[USAKI VOICE] server vad endpoint observed; finalizing input "
                        "duration_ms=%d min_ms=%d",
                        input_duration_ms,
                        min_auto_end_ms,
                    )
                    self._finalize_current_input(reason="server_vad_end")
            elif not self._server_vad_too_early_logged:
                self._server_vad_too_early_logged = True
                logger.warning(
                    "[USAKI VOICE] server vad endpoint ignored as too early "
                    "duration_ms=%s min_ms=%d auto_end=%s",
                    input_duration_ms,
                    min_auto_end_ms,
                    self.settings.audio_server_vad_auto_end,
                )

    async def _handle_text(self, raw_text: str) -> None:
        ok, message = self._parse_ws_message(raw_text)
        if not ok:
            await self._send_ws_message(message)
            return
        await self._handle_text_message(message)

    def _parse_ws_message(self, raw_text: str) -> tuple[bool, WsMessage]:
        try:
            message = WsMessage.model_validate(json.loads(raw_text))
            self.state.seq = max(self.state.seq, message.seq + 1)
            self.state.device_id = self.state.device_id or message.device_id
            return True, message
        except Exception as exc:
            return False, build_ws_message(
                message_id=f"msg_{uuid.uuid4().hex}",
                message_type="error",
                device_id=self.state.device_id or "unknown",
                seq=self.state.seq,
                data=ErrorData(code=70001, message=str(exc), retryable=False),
            )

    async def _handle_text_message(self, message: WsMessage) -> None:
        try:
            if message.type == "voice.wake.detected":
                wake_data = VoiceWakeDetectedData.model_validate(message.data)
                device_registry.touch(message.device_id)
                logger.warning(
                    "[USAKI VOICE] wake detected device_id=%s wake_word=%s input_mode=%s will_start_input=%s",
                    message.device_id,
                    wake_data.wake_word,
                    wake_data.input_mode,
                    wake_data.will_start_input,
                )
                return

            if message.type == "voice.input.start":
                start_data = VoiceInputStartData.model_validate(message.data)
                self.flow.start_input(start_data, device_id=message.device_id)
                self.state.input_audio_bytes = 0
                self._server_vad_endpoint_logged = False
                self._server_vad_too_early_logged = False
                self._input_turn_finalized = False
                self._current_request_id = start_data.request_id
                self._input_started_at = time.monotonic()
                logger.warning(
                    "[USAKI VOICE] input started device_id=%s",
                    message.device_id,
                )
                return

            if message.type == "voice.input.end":
                end_data = VoiceInputEndData.model_validate(message.data)
                if self._input_turn_finalized:
                    logger.warning(
                        "[USAKI VOICE] ignoring duplicate voice.input.end device_id=%s reason=%s",
                        message.device_id,
                        end_data.reason,
                    )
                    return
                self._finalize_current_input(end_data=end_data)
                return

            if message.type == "voice.input.cancel":
                cancel = VoiceInputCancelData.model_validate(message.data)
                if cancel.reason in {"privacy", "privacy_muted", "privacy_mute"}:
                    self._cancel_output_tasks()
                elif cancel.request_id is not None and cancel.request_id != self._current_request_id:
                    return  # A delayed cancellation must not discard a newer input.
                self.flow.cancel_input()
                self.state.input_audio_bytes = 0
                self._server_vad_endpoint_logged = False
                self._server_vad_too_early_logged = False
                self._input_turn_finalized = True
                self._current_request_id = None
                self._input_started_at = None
                return

            if message.type == "voice.interrupt":
                VoiceInterruptData.model_validate(message.data)
                self._cancel_output_tasks()
                self.flow.cancel_input()
                self.state.input_audio_bytes = 0
                self._server_vad_endpoint_logged = False
                self._server_vad_too_early_logged = False
                self._input_turn_finalized = True
                self._current_request_id = None
                self._input_started_at = None
                return

            if message.type == "touch.event":
                TouchEventData.model_validate(message.data)
                device_registry.touch(message.device_id)
                return

            if message.type == "sensor.update":
                SensorUpdateData.model_validate(message.data)
                device_registry.touch(message.device_id)
                return

            await self._send_ws_message(
                error_response(
                    message,
                    self.state.seq,
                    70002,
                    f"unsupported voice message: {message.type}",
                ),
            )
        except Exception as exc:
            await self._send_ws_message(
                build_ws_message(
                    message_id=f"msg_{uuid.uuid4().hex}",
                    message_type="error",
                    device_id=message.device_id,
                    seq=self.state.seq,
                    data=ErrorData(ref_id=message.id, code=70001, message=str(exc), retryable=False),
                ),
            )

    def _cancel_output_tasks(self) -> None:
        for task in tuple(self._process_tasks):
            task.cancel()
        while not self._send_queue.empty():
            try:
                self._send_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _spawn_voice_output_turn(self, end_data: VoiceInputEndData) -> None:
        """启动独立 task 处理 STT→LLM→TTS，不阻塞接收循环。"""
        device_id = self.state.device_id or "unknown"
        seq = self.state.seq
        task = asyncio.create_task(self._process_voice_output_turn(end_data, device_id, seq))
        self._process_tasks.add(task)
        task.add_done_callback(self._process_tasks.discard)

    def _finalize_current_input(
        self,
        *,
        reason: str | None = None,
        end_data: VoiceInputEndData | None = None,
    ) -> None:
        if self._input_turn_finalized:
            return
        self._input_turn_finalized = True
        self.state.input_audio_bytes = self.flow.input_audio_bytes

        if end_data is None:
            end_data = VoiceInputEndData(
                request_id=self._current_request_id,
                reason=reason or "server_vad_end",
                duration_ms=self._input_duration_ms(),
            )
        elif end_data.duration_ms is None:
            end_data = end_data.model_copy(update={"duration_ms": self._input_duration_ms()})

        logger.warning(
            "[USAKI PERF] input finalized device_id=%s reason=%s audio_bytes=%d duration_ms=%s",
            self.state.device_id or self.flow.active_device_id or "unknown",
            end_data.reason,
            self.state.input_audio_bytes,
            end_data.duration_ms,
        )
        self._spawn_voice_output_turn(end_data)
        self._current_request_id = None
        self._input_started_at = None

    def _input_duration_ms(self) -> int | None:
        if self._input_started_at is None:
            return None
        return int((time.monotonic() - self._input_started_at) * 1000)

    async def _process_voice_output_turn(
        self,
        end_data: VoiceInputEndData,
        device_id: str,
        seq: int,
    ) -> None:
        """独立协程：执行 finish_input 并放入发送队列。"""
        try:
            async for frame in self.flow.finish_input(end_data, device_id=device_id, seq=seq):
                await self._send_queue.put(frame)
        except asyncio.CancelledError:
            logger.warning(
                "[USAKI VOICE] voice output turn cancelled device_id=%s",
                device_id,
            )
        except Exception as exc:
            logger.error(
                "[USAKI VOICE] voice output turn error device_id=%s: %s",
                device_id,
                exc,
            )

    async def _send_ws_message(self, message: WsMessage) -> None:
        if message.type in {
            "body.action",
            "emotion.update",
            "eye.animation",
            "voice.output.start",
            "voice.output.end",
            "voice.output.cancel",
        }:
            logger.warning(
                "[USAKI WS] send json type=%s seq=%d data=%s",
                message.type,
                self.state.seq,
                message.data,
            )
        await self.websocket.send_json(message.model_dump(exclude_none=True))
        self.state.seq += 1


@router.websocket("/voice")
async def voice(websocket: WebSocket) -> None:
    settings = get_settings()
    providers = _resolve_voice_providers(settings)
    handler = VoiceConnectionHandler(websocket, settings, providers)
    await handler.handle()


def _frame_duration_seconds(data: dict) -> float:
    if str(data.get("codec", "")).lower() != "opus":
        return 0.0
    frame_duration_ms = int(data.get("frame_duration_ms") or 0)
    return frame_duration_ms / 1000 if frame_duration_ms > 0 else 0.0
