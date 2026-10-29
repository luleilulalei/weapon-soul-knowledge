from __future__ import annotations

import time
from typing import Any, Callable, Literal, Optional
import uuid

from pydantic import BaseModel, Field
from dataclasses import dataclass


ProtocolType = Literal[
    "voice.wake.detected",
    "voice.input.start",
    "voice.input.end",
    "voice.input.cancel",
    "voice.output.start",
    "voice.output.end",
    "voice.output.cancel",
    "voice.interrupt",
    "emotion.update",
    "eye.animation",
    "body.action",
    "motion.command",
    "motion.script.play",
    "motion.script.stop",
    "motion.stop",
    "motion.servo.batch",
    "motion.ack",
    "motion.state",
    "touch.event",
    "sensor.update",
    "notification.push",
    "error",
]


def now_ms() -> int:
    return int(time.time() * 1000)


class ApiResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: Any = Field(default_factory=dict)


class WsMessage(BaseModel):
    id: str
    type: ProtocolType
    device_id: str
    timestamp: int = Field(default_factory=now_ms)
    seq: int = Field(ge=0)
    data: dict[str, Any] = Field(default_factory=dict)


class DeviceCapabilities(BaseModel):
    audio_input: bool = True
    audio_output: bool = True
    touch: bool = True
    screen: bool = True
    body: bool = False
    haptic: bool = False
    blade: bool = False
    imu: bool = False
    battery: bool = False
    nfc: bool = False

    def as_list(self) -> list[str]:
        return [name for name, enabled in self.model_dump().items() if enabled]


class DeviceConnectRequest(BaseModel):
    device_id: str
    firmware_version: str | None = None
    hardware_version: str | None = None
    protocol_version: str = "1.1"
    capabilities: DeviceCapabilities = Field(default_factory=DeviceCapabilities)


class DeviceConnectResponse(BaseModel):
    token: str
    config_version: int = 1


class VoiceInputStartData(BaseModel):
    request_id: str | None = None
    codec: str = "opus"
    sample_rate: int = 16000
    channels: int = 1
    sample_bits: int = 16
    frame_duration_ms: int = 60
    mode: str = "stream"
    vad: dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "source": "device"})


class VoiceInputEndData(BaseModel):
    request_id: str | None = None
    reason: str = "vad_end"
    duration_ms: int | None = None


class VoiceInputCancelData(BaseModel):
    request_id: str | None = None
    reason: str = "user_cancel"


class VoiceWakeDetectedData(BaseModel):
    wake_word: str
    confidence: float = 0.0
    input_mode: str = "wake_word"
    will_start_input: bool = True


class VoiceOutputStartData(BaseModel):
    output_id: str
    request_id: str | None = None
    codec: str = "opus"
    sample_rate: int = 16000
    channels: int = 1
    sample_bits: int = 16
    frame_duration_ms: int = 60
    play_mode: str = "stream"


class VoiceOutputEndData(BaseModel):
    output_id: str
    request_id: str | None = None
    reason: str = "finished"
    duration_ms: int | None = None


class VoiceOutputCancelData(BaseModel):
    output_id: str
    request_id: str | None = None
    reason: str = "interrupted"


class VoiceInterruptData(BaseModel):
    output_id: str
    reason: str = "user_speaking"


class EmotionUpdateData(BaseModel):
    emotion: str
    intensity: float = Field(default=1.0, ge=0.0, le=1.0)
    duration_ms: int | None = None


class EyeAnimationData(BaseModel):
    name: str
    duration_ms: int | None = None
    loop: bool = False
    priority: int = 0


class BodyActionItem(BaseModel):
    part: str
    action: str
    angle: int | None = None
    count: int | None = None
    duration_ms: int | None = None


class BodyActionData(BaseModel):
    actions: list[BodyActionItem]


class MotionCommandData(BaseModel):
    command_id: str | None = None
    source: str = "motion_lab"
    mode: str = "manual"
    part: str
    op: str
    direction: str | None = None
    physical_direction: str | None = None
    speed: str | None = None
    angle: int | None = None
    pulse_us: int | None = None
    duration_ms: int | None = None
    ttl_ms: int | None = None
    interrupt: bool = True


class MotionScriptPlayData(BaseModel):
    script_id: str | None = None
    source: str = "motion_lab"
    interrupt: bool = True
    loop: bool = False
    script: dict[str, Any]
    low_level: dict[str, Any] | None = None


class MotionScriptStopData(BaseModel):
    script_id: str | None = None
    source: str = "motion_lab"
    reason: str = "manual"


class MotionServoItem(BaseModel):
    part: str
    channel: int
    kind: str
    op: str
    direction: str | None = None
    speed: str | None = None
    pulse_us: int | None = None
    angle: int | None = None
    duration_ms: int | None = None
    ttl_ms: int | None = None


class MotionServoBatchData(BaseModel):
    ref_id: str | None = None
    command_id: str | None = None
    source: str = "motion_server"
    priority: int = 80
    interrupt: bool = True
    ttl_ms: int | None = None
    servos: list[MotionServoItem]


class MotionAckData(BaseModel):
    ref_id: str | None = None
    command_id: str | None = None
    stage: str
    ok: bool = True
    message: str | None = None


class MotionStateData(BaseModel):
    online: bool
    busy: bool = False
    queue_depth: int = 0
    servos: dict[str, Any] = Field(default_factory=dict)
    devices: dict[str, Any] = Field(default_factory=dict)


class TouchEventData(BaseModel):
    area: str
    event: str
    value: int | float | str | None = None
    duration_ms: int | None = None


class SensorUpdateData(BaseModel):
    imu: dict[str, float] | None = None
    light: int | float | None = None
    distance: int | float | None = None


class NotificationPushData(BaseModel):
    notification_id: str
    category: str
    title: str
    content: str
    speak: bool = False
    emotion: str | None = None


class ErrorData(BaseModel):
    ref_id: str | None = None
    code: int
    message: str
    retryable: bool = False


class DeviceRegisterRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    sn: str | None = Field(default=None, max_length=64)
    hardware_version: str | None = Field(default=None, max_length=64)
    firmware_version: str | None = Field(default=None, max_length=64)
    mac: str | None = Field(default=None, max_length=32)


class DeviceDetailRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)


class DeviceConfigGetRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)


class DeviceConfigUpdateRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)


def build_ws_message(
    *,
    message_id: str,
    message_type: ProtocolType,
    device_id: str,
    seq: int,
    data: BaseModel | dict[str, Any] | None = None,
) -> WsMessage:
    if isinstance(data, BaseModel):
        payload = data.model_dump(exclude_none=True)
    else:
        payload = data or {}
    return WsMessage(id=message_id, type=message_type, device_id=device_id, seq=seq, data=payload)


@dataclass
class WsProtocolState:
    device_id: str | None = None
    seq: int = 1
    input_audio_bytes: int = 0

WsMessageHandler = Callable[[WsMessage, WsProtocolState], Optional[WsMessage]]



def error_response(message: WsMessage, seq: int, code: int, text: str) -> WsMessage:
    return build_ws_message(
        message_id=f"msg_{uuid.uuid4().hex}",
        message_type="error",
        device_id=message.device_id,
        seq=seq,
        data=ErrorData(ref_id=message.id, code=code, message=text, retryable=False),
    )
