from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from usaki_server.api.model import (
    ErrorData,
    MotionAckData,
    MotionCommandData,
    MotionScriptPlayData,
    MotionScriptStopData,
    MotionServoBatchData,
    MotionStateData,
    WsMessage,
    build_ws_message,
)
from usaki_server.devices.registry import device_registry

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_DEVICE_ID = "usaki-esp32s3-dev-001"
SCRIPT_STEP_MS = 50
EAR_PARTS = {"left_ear", "right_ear"}
EAR_MAX_OFFSET_DEG = 30
CONTINUOUS_SLOW_SCALE = 0.45

SERVO_PARTS: dict[str, dict[str, Any]] = {
    "left_ear": {
        "channel": 0,
        "kind": "continuous",
        "reverse": False,
        "drive_reverse": False,
        "stop_us": 1500,
        "slow_cw_us": 1660,
        "slow_ccw_us": 1340,
        "fast_cw_us": 1850,
        "fast_ccw_us": 1150,
        "ms_per_90_deg": 620,
        "max_deg": EAR_MAX_OFFSET_DEG,
    },
    "right_ear": {
        "channel": 1,
        "kind": "continuous",
        "reverse": True,
        "drive_reverse": True,
        "stop_us": 1500,
        "slow_cw_us": 1660,
        "slow_ccw_us": 1340,
        "fast_cw_us": 1850,
        "fast_ccw_us": 1150,
        "ms_per_90_deg": 620,
        "max_deg": EAR_MAX_OFFSET_DEG,
    },
    "left_arm": {
        "channel": 2,
        "kind": "continuous",
        "reverse": True,
        "drive_reverse": True,
        "stop_us": 1500,
        "slow_cw_us": 1660,
        "slow_ccw_us": 1340,
        "fast_cw_us": 1850,
        "fast_ccw_us": 1150,
        "ms_per_90_deg": 620,
    },
    "right_arm": {
        "channel": 3,
        "kind": "continuous",
        "reverse": False,
        "drive_reverse": False,
        "stop_us": 1500,
        "slow_cw_us": 1660,
        "slow_ccw_us": 1340,
        "fast_cw_us": 1850,
        "fast_ccw_us": 1150,
        "ms_per_90_deg": 620,
    },
    "body": {
        "channel": 4,
        "kind": "positional",
        "min_deg": 0,
        "center_deg": 90,
        "max_deg": 180,
        "min_pulse_us": 1000,
        "center_pulse_us": 1500,
        "max_pulse_us": 2000,
    },
}

PART_ALIASES = {
    "left_hand": "left_arm",
    "right_hand": "right_arm",
    "turntable": "body",
    "base": "body",
}

PART_GROUPS = {
    "all": ["left_ear", "right_ear", "left_arm", "right_arm", "body"],
    "ears": ["left_ear", "right_ear"],
    "both_ears": ["left_ear", "right_ear"],
    "arms": ["left_arm", "right_arm"],
    "both_arms": ["left_arm", "right_arm"],
    "hands": ["left_arm", "right_arm"],
    "both_hands": ["left_arm", "right_arm"],
}


@dataclass
class MotionDeviceConnection:
    device_id: str
    websocket: WebSocket
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class MotionHub:
    def __init__(self) -> None:
        self.devices: dict[str, MotionDeviceConnection] = {}
        self.lab_clients: set[WebSocket] = set()
        self.servo_state: dict[str, dict[str, Any]] = {}
        self.script_tasks: dict[str, asyncio.Task[None]] = {}
        self.auto_stop_tasks: dict[tuple[str, str], asyncio.Task[None]] = {}
        self._seq = 1
        self._lock = asyncio.Lock()

    async def connect_device(self, websocket: WebSocket, device_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self.devices[device_id] = MotionDeviceConnection(device_id=device_id, websocket=websocket)
            self.servo_state.setdefault(device_id, _default_servo_state())
        device_registry.connect(device_id, ["motion", "body"])
        await self.broadcast_state(device_id)
        logger.warning("[USAKI MOTION] device connected device_id=%s", device_id)

    async def disconnect_device(self, websocket: WebSocket, device_id: str) -> None:
        async with self._lock:
            current = self.devices.get(device_id)
            if current is not None and current.websocket is websocket:
                self.devices.pop(device_id, None)
        self.cancel_auto_stops(device_id, "all")
        await self.broadcast_state(device_id)
        logger.warning("[USAKI MOTION] device disconnected device_id=%s", device_id)

    async def connect_lab(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.lab_clients.add(websocket)
        await self.send_state(websocket, websocket.query_params.get("device_id") or DEFAULT_DEVICE_ID)
        logger.warning("[USAKI MOTION] lab connected")

    async def disconnect_lab(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.lab_clients.discard(websocket)
        logger.warning("[USAKI MOTION] lab disconnected")

    async def handle_device_text(self, raw_text: str, fallback_device_id: str) -> None:
        try:
            message = WsMessage.model_validate(json.loads(raw_text))
        except Exception as exc:
            logger.warning("[USAKI MOTION] invalid device message: %s", exc)
            return

        device_id = message.device_id or fallback_device_id
        device_registry.touch(device_id)
        if message.type in {"motion.ack", "motion.state", "error"}:
            await self.broadcast_message(message)

    async def handle_lab_text(self, websocket: WebSocket, raw_text: str) -> None:
        try:
            message = WsMessage.model_validate(json.loads(raw_text))
        except Exception as exc:
            await self.send_error(websocket, DEFAULT_DEVICE_ID, None, 71001, str(exc))
            return

        if message.type == "motion.command":
            await self.handle_motion_command(websocket, message)
            return
        if message.type == "motion.stop":
            await self.handle_motion_stop(websocket, message)
            return
        if message.type == "motion.script.play":
            await self.handle_script_play(websocket, message)
            return
        if message.type == "motion.script.stop":
            await self.handle_script_stop(websocket, message)
            return

        await self.send_error(
            websocket,
            message.device_id,
            message.id,
            71002,
            f"unsupported motion lab message: {message.type}",
        )

    async def handle_motion_command(self, websocket: WebSocket, message: WsMessage) -> None:
        try:
            command = MotionCommandData.model_validate(message.data)
        except ValidationError as exc:
            await self.send_error(websocket, message.device_id, message.id, 71003, str(exc))
            return

        servos = build_servos_for_command(command)
        if not servos:
            await self.send_ack(
                websocket,
                message.device_id,
                message.id,
                "server_rejected",
                False,
                f"unsupported motion command: {command.part} {command.op}",
                command.command_id,
            )
            return

        await self.send_ack(websocket, message.device_id, message.id, "server_accepted", True, command_id=command.command_id)
        sent = await self.send_batch(
            device_id=message.device_id,
            ref_id=message.id,
            command_id=command.command_id,
            source=command.source,
            interrupt=command.interrupt,
            ttl_ms=command.ttl_ms,
            servos=servos,
        )
        if sent:
            self.schedule_auto_stops(message.device_id, message.id, command.command_id, command.source, servos)

    async def handle_motion_stop(self, websocket: WebSocket, message: WsMessage) -> None:
        part = str(message.data.get("part") or "all")
        source = str(message.data.get("source") or "motion_lab")
        self.cancel_script(message.device_id)
        self.cancel_auto_stops(message.device_id, part)
        servos = build_stop_servos(part)
        await self.send_ack(websocket, message.device_id, message.id, "server_accepted", True)
        await self.send_batch(
            device_id=message.device_id,
            ref_id=message.id,
            command_id=str(message.data.get("command_id") or ""),
            source=source,
            interrupt=True,
            ttl_ms=None,
            servos=servos,
        )

    async def handle_script_play(self, websocket: WebSocket, message: WsMessage) -> None:
        try:
            play = MotionScriptPlayData.model_validate(message.data)
        except ValidationError as exc:
            await self.send_error(websocket, message.device_id, message.id, 71004, str(exc))
            return

        if play.interrupt:
            self.cancel_script(message.device_id)
            self.cancel_auto_stops(message.device_id, "all")

        moments = compile_low_level_moments(play.low_level) if play.low_level else compile_script_moments(play.script)
        if not moments:
            await self.send_ack(websocket, message.device_id, message.id, "server_rejected", False, "empty script")
            return

        await self.send_ack(websocket, message.device_id, message.id, "server_accepted", True)
        task = asyncio.create_task(self.run_script(message.device_id, message.id, play, moments))
        self.script_tasks[message.device_id] = task

    async def handle_script_stop(self, websocket: WebSocket, message: WsMessage) -> None:
        try:
            stop = MotionScriptStopData.model_validate(message.data)
        except ValidationError as exc:
            await self.send_error(websocket, message.device_id, message.id, 71005, str(exc))
            return

        self.cancel_script(message.device_id)
        self.cancel_auto_stops(message.device_id, "all")
        await self.send_ack(websocket, message.device_id, message.id, "server_accepted", True, command_id=stop.script_id)
        await self.send_batch(
            device_id=message.device_id,
            ref_id=message.id,
            command_id=stop.script_id,
            source=stop.source,
            interrupt=True,
            ttl_ms=None,
            servos=build_stop_servos("all"),
        )

    async def run_script(
        self,
        device_id: str,
        ref_id: str,
        play: MotionScriptPlayData,
        moments: list[tuple[int, list[dict[str, Any]]]],
    ) -> None:
        try:
            await self.broadcast_ack(device_id, ref_id, "script_started", True, command_id=play.script_id)
            cycle_duration_ms = script_cycle_duration_ms(play, moments)
            while True:
                started_at = time.monotonic()
                for at_ms, servos in moments:
                    delay = started_at + at_ms / 1000 - time.monotonic()
                    if delay > 0:
                        await asyncio.sleep(delay)
                    await self.send_batch(
                        device_id=device_id,
                        ref_id=ref_id,
                        command_id=play.script_id,
                        source=play.source,
                        interrupt=False,
                        ttl_ms=None,
                        servos=servos,
                    )
                remaining = started_at + cycle_duration_ms / 1000 - time.monotonic()
                if remaining > 0:
                    await asyncio.sleep(remaining)
                if not play.loop:
                    break
            await self.broadcast_ack(device_id, ref_id, "script_finished", True, command_id=play.script_id)
        except asyncio.CancelledError:
            await self.broadcast_ack(device_id, ref_id, "script_cancelled", True, command_id=play.script_id)
            raise
        finally:
            current = self.script_tasks.get(device_id)
            if current is asyncio.current_task():
                self.script_tasks.pop(device_id, None)
            await self.broadcast_state(device_id)

    def cancel_script(self, device_id: str) -> None:
        task = self.script_tasks.pop(device_id, None)
        if task is not None and not task.done():
            task.cancel()

    def schedule_auto_stops(
        self,
        device_id: str,
        ref_id: str | None,
        command_id: str | None,
        source: str,
        servos: list[dict[str, Any]],
    ) -> None:
        for servo in servos:
            part = str(servo.get("part") or "")
            duration_ms = int(servo.get("duration_ms") or 0)
            if servo.get("kind") != "continuous" or servo.get("op") != "drive" or duration_ms <= 0:
                continue
            key = (device_id, part)
            self.cancel_auto_stop_key(key)
            self.auto_stop_tasks[key] = asyncio.create_task(
                self.run_auto_stop(device_id, part, duration_ms, ref_id, command_id, source)
            )

    async def run_auto_stop(
        self,
        device_id: str,
        part: str,
        duration_ms: int,
        ref_id: str | None,
        command_id: str | None,
        source: str,
    ) -> None:
        key = (device_id, part)
        try:
            await asyncio.sleep(duration_ms / 1000)
            await self.send_batch(
                device_id=device_id,
                ref_id=ref_id,
                command_id=f"{command_id or ref_id or part}:auto_stop",
                source=source,
                interrupt=False,
                ttl_ms=None,
                servos=[build_stop_servo(part)],
            )
        except asyncio.CancelledError:
            raise
        finally:
            if self.auto_stop_tasks.get(key) is asyncio.current_task():
                self.auto_stop_tasks.pop(key, None)

    def cancel_auto_stops(self, device_id: str, part: str) -> None:
        targets = target_parts(part)
        if part == "all" or not targets:
            keys = [key for key in self.auto_stop_tasks if key[0] == device_id]
        else:
            keys = [(device_id, target) for target in targets]
        for key in keys:
            self.cancel_auto_stop_key(key)

    def cancel_auto_stop_key(self, key: tuple[str, str]) -> None:
        task = self.auto_stop_tasks.pop(key, None)
        if task is not None and not task.done():
            task.cancel()

    async def send_batch(
        self,
        *,
        device_id: str,
        ref_id: str | None,
        command_id: str | None,
        source: str,
        interrupt: bool,
        ttl_ms: int | None,
        servos: list[dict[str, Any]],
    ) -> bool:
        connection = self.devices.get(device_id)
        if connection is None:
            await self.broadcast_ack(device_id, ref_id, "device_unavailable", False, "motion device is offline", command_id)
            await self.broadcast_state(device_id)
            return False

        batch = MotionServoBatchData(
            ref_id=ref_id,
            command_id=command_id or None,
            source=source,
            interrupt=interrupt,
            ttl_ms=ttl_ms,
            servos=servos,
        )
        message = self.build_message("motion.servo.batch", device_id, batch)
        try:
            async with connection.send_lock:
                await connection.websocket.send_json(message.model_dump(exclude_none=True))
        except Exception as exc:
            logger.warning("[USAKI MOTION] send batch failed device_id=%s: %s", device_id, exc)
            await self.disconnect_device(connection.websocket, device_id)
            await self.broadcast_ack(device_id, ref_id, "device_send_failed", False, str(exc), command_id)
            return False

        self.apply_desired_state(device_id, batch.model_dump(exclude_none=True))
        await self.broadcast_ack(device_id, ref_id, "device_sent", True, command_id=command_id)
        await self.broadcast_state(device_id)
        return True

    def apply_desired_state(self, device_id: str, batch: dict[str, Any]) -> None:
        state = self.servo_state.setdefault(device_id, _default_servo_state())
        for servo in batch.get("servos", []):
            part = servo.get("part")
            if part not in state:
                continue
            op = servo.get("op")
            if op == "drive":
                state[part].update(
                    {
                        "state": "driving",
                        "direction": servo.get("direction"),
                        "speed": servo.get("speed"),
                        "pulse_us": servo.get("pulse_us"),
                    }
                )
            elif op in {"stop", "disable"}:
                state[part].update({"state": "stopped", "pulse_us": servo.get("pulse_us")})
                state[part].pop("direction", None)
                state[part].pop("speed", None)
            elif op == "set_angle":
                state[part].update({"state": "at_angle", "angle": servo.get("angle"), "pulse_us": servo.get("pulse_us")})

    def build_message(self, message_type: str, device_id: str, data: Any) -> WsMessage:
        message = build_ws_message(
            message_id=f"msg_{uuid.uuid4().hex}",
            message_type=message_type,  # type: ignore[arg-type]
            device_id=device_id,
            seq=self._seq,
            data=data,
        )
        self._seq += 1
        return message

    async def send_state(self, websocket: WebSocket, device_id: str) -> None:
        await websocket.send_json(self.state_message(device_id).model_dump(exclude_none=True))

    async def broadcast_state(self, device_id: str) -> None:
        await self.broadcast_message(self.state_message(device_id))

    def state_message(self, device_id: str) -> WsMessage:
        devices = {
            item_device_id: {
                "online": True,
                "capabilities": ["motion", "body"],
            }
            for item_device_id in self.devices
        }
        data = MotionStateData(
            online=device_id in self.devices,
            busy=device_id in self.script_tasks,
            queue_depth=0,
            servos=self.servo_state.get(device_id, _default_servo_state()),
            devices=devices,
        )
        return self.build_message("motion.state", device_id, data)

    async def send_ack(
        self,
        websocket: WebSocket,
        device_id: str,
        ref_id: str | None,
        stage: str,
        ok: bool,
        message: str | None = None,
        command_id: str | None = None,
    ) -> None:
        data = MotionAckData(ref_id=ref_id, command_id=command_id or None, stage=stage, ok=ok, message=message)
        await websocket.send_json(self.build_message("motion.ack", device_id, data).model_dump(exclude_none=True))

    async def broadcast_ack(
        self,
        device_id: str,
        ref_id: str | None,
        stage: str,
        ok: bool,
        message: str | None = None,
        command_id: str | None = None,
    ) -> None:
        data = MotionAckData(ref_id=ref_id, command_id=command_id or None, stage=stage, ok=ok, message=message)
        await self.broadcast_message(self.build_message("motion.ack", device_id, data))

    async def send_error(
        self,
        websocket: WebSocket,
        device_id: str,
        ref_id: str | None,
        code: int,
        message: str,
    ) -> None:
        data = ErrorData(ref_id=ref_id, code=code, message=message, retryable=False)
        await websocket.send_json(self.build_message("error", device_id, data).model_dump(exclude_none=True))

    async def broadcast_message(self, message: WsMessage) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self.lab_clients):
            try:
                await websocket.send_json(message.model_dump(exclude_none=True))
            except Exception:
                stale.append(websocket)
        if stale:
            async with self._lock:
                for websocket in stale:
                    self.lab_clients.discard(websocket)

    def reset_for_tests(self) -> None:
        for task in self.script_tasks.values():
            task.cancel()
        for task in self.auto_stop_tasks.values():
            task.cancel()
        self.devices.clear()
        self.lab_clients.clear()
        self.servo_state.clear()
        self.script_tasks.clear()
        self.auto_stop_tasks.clear()
        self._seq = 1


motion_hub = MotionHub()


@router.websocket("/device")
async def motion_device(websocket: WebSocket) -> None:
    device_id = websocket.query_params.get("device_id") or DEFAULT_DEVICE_ID
    await motion_hub.connect_device(websocket, device_id)
    try:
        while True:
            raw_text = await websocket.receive_text()
            await motion_hub.handle_device_text(raw_text, device_id)
    except WebSocketDisconnect:
        pass
    finally:
        await motion_hub.disconnect_device(websocket, device_id)


@router.websocket("/lab")
async def motion_lab(websocket: WebSocket) -> None:
    await motion_hub.connect_lab(websocket)
    try:
        while True:
            raw_text = await websocket.receive_text()
            await motion_hub.handle_lab_text(websocket, raw_text)
    except WebSocketDisconnect:
        pass
    finally:
        await motion_hub.disconnect_lab(websocket)


def build_servos_for_command(command: MotionCommandData) -> list[dict[str, Any]]:
    op = command.op
    targets = target_parts(command.part)
    if op == "center":
        return build_stop_servos(command.part)
    if op == "stop":
        return [build_stop_servo(part) for part in targets if SERVO_PARTS[part]["kind"] == "continuous"]
    if op == "drive":
        return [
            build_drive_servo(
                part,
                command.direction or "cw",
                command.speed or "fast",
                command.pulse_us,
                command.ttl_ms,
                command.duration_ms,
                command.physical_direction,
            )
            for part in targets
            if SERVO_PARTS[part]["kind"] == "continuous"
        ]
    if op == "set_angle":
        return [
            build_body_servo(
                command.angle if command.angle is not None else SERVO_PARTS[part]["center_deg"],
                command.pulse_us,
            )
            for part in targets
            if SERVO_PARTS[part]["kind"] == "positional"
        ]
    return []


def build_stop_servos(part: str) -> list[dict[str, Any]]:
    servos: list[dict[str, Any]] = []
    for target in target_parts(part):
        spec = SERVO_PARTS[target]
        if spec["kind"] == "continuous":
            servos.append(build_stop_servo(target))
        elif part in {"all", "body", "turntable", "base"}:
            servos.append(build_body_servo(spec["center_deg"]))
    return servos


def build_drive_servo(
    part: str,
    direction: str,
    speed: str,
    pulse_us: int | None = None,
    ttl_ms: int | None = None,
    duration_ms: int | None = None,
    physical_direction: str | None = None,
) -> dict[str, Any]:
    spec = SERVO_PARTS[part]
    physical_direction = (
        normalize_direction(physical_direction)
        if physical_direction
        else physical_direction_for_visual(part, direction)
    )
    normalized_speed = "slow" if speed == "slow" else "fast"
    if pulse_us is None:
        pulse_us = pulse_for_continuous(part, physical_direction, normalized_speed)
    servo = {
        "part": part,
        "channel": spec["channel"],
        "kind": "continuous",
        "op": "drive",
        "direction": physical_direction,
        "speed": normalized_speed,
        "pulse_us": int(pulse_us),
        "ttl_ms": ttl_ms,
    }
    limited_duration_ms = safe_continuous_duration_ms(part, normalized_speed, duration_ms)
    if limited_duration_ms is not None:
        servo["duration_ms"] = limited_duration_ms
    return servo


def build_stop_servo(part: str) -> dict[str, Any]:
    spec = SERVO_PARTS[part]
    return {
        "part": part,
        "channel": spec["channel"],
        "kind": "continuous",
        "op": "stop",
        "pulse_us": spec["stop_us"],
    }


def build_body_servo(angle: int | float, pulse_us: int | None = None) -> dict[str, Any]:
    spec = SERVO_PARTS["body"]
    limited = clamp(float(angle), spec["min_deg"], spec["max_deg"])
    return {
        "part": "body",
        "channel": spec["channel"],
        "kind": "positional",
        "op": "set_angle",
        "angle": int(round(limited)),
        "pulse_us": int(pulse_us) if pulse_us is not None else pulse_for_body(limited),
    }


def compile_script_moments(script: dict[str, Any]) -> list[tuple[int, list[dict[str, Any]]]]:
    tracks = script.get("tracks") if isinstance(script, dict) else None
    if not isinstance(tracks, dict):
        return []

    moments: dict[int, list[dict[str, Any]]] = {}

    def add(at_ms: int, servo: dict[str, Any]) -> None:
        moments.setdefault(max(0, int(at_ms)), []).append(servo)

    for part in ("left_ear", "right_ear", "left_arm", "right_arm"):
        events = tracks.get(part) or []
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict) or event.get("action", "spin") != "spin":
                continue
            speed = str(event.get("speed") or "fast")
            duration_ms = max(0, int(event.get("duration_ms") or 0))
            duration_ms = safe_continuous_duration_ms(part, speed, duration_ms) or 0
            if duration_ms <= 0:
                continue
            at_ms = max(0, int(event.get("at") or 0))
            add(at_ms, build_drive_servo(part, str(event.get("direction") or "cw"), speed, duration_ms=duration_ms))
            add(at_ms + duration_ms, build_stop_servo(part))

    body_events = tracks.get("body") or []
    if isinstance(body_events, list):
        current_angle = SERVO_PARTS["body"]["center_deg"]
        for event in sorted((item for item in body_events if isinstance(item, dict)), key=lambda item: int(item.get("at") or 0)):
            if "angle" not in event:
                continue
            at_ms = max(0, int(event.get("at") or 0))
            target_angle = clamp(float(event.get("angle")), 0, 180)
            duration_ms = max(0, int(event.get("duration_ms") or 0))
            if duration_ms <= 0:
                add(at_ms, build_body_servo(target_angle))
            else:
                steps = max(1, min(60, math.ceil(duration_ms / SCRIPT_STEP_MS)))
                for step in range(1, steps + 1):
                    t = step / steps
                    eased = ease_in_out(t)
                    angle = current_angle + (target_angle - current_angle) * eased
                    add(at_ms + round(duration_ms * t), build_body_servo(angle))
            current_angle = target_angle

    return sorted(moments.items(), key=lambda item: item[0])


def compile_low_level_moments(low_level: dict[str, Any] | None) -> list[tuple[int, list[dict[str, Any]]]]:
    commands = low_level.get("commands") if isinstance(low_level, dict) else None
    if not isinstance(commands, list):
        return []

    moments: dict[int, list[dict[str, Any]]] = {}

    def add(at_ms: int, servo: dict[str, Any]) -> None:
        moments.setdefault(max(0, int(at_ms)), []).append(servo)

    for command in commands:
        if not isinstance(command, dict):
            continue
        part = str(command.get("part") or "")
        if part not in SERVO_PARTS:
            continue
        at_ms = max(0, int(command.get("at") or 0))
        kind = str(command.get("type") or SERVO_PARTS[part]["kind"])
        if kind == "continuous":
            speed = "slow" if command.get("speed") == "slow" else "fast"
            duration_ms = max(0, int(command.get("duration_ms") or 0))
            duration_ms = safe_continuous_duration_ms(part, speed, duration_ms) or 0
            if duration_ms <= 0:
                continue
            physical_direction = "ccw" if command.get("physical_direction") == "ccw" else "cw"
            pulse_us = (
                int(command.get("pulse_us"))
                if command.get("pulse_us") is not None
                else pulse_for_continuous(part, physical_direction, speed)
            )
            add(
                at_ms,
                {
                    "part": part,
                    "channel": SERVO_PARTS[part]["channel"],
                    "kind": "continuous",
                    "op": "drive",
                    "direction": physical_direction,
                    "speed": speed,
                    "pulse_us": pulse_us,
                    "duration_ms": duration_ms,
                },
            )
            add(at_ms + duration_ms, build_stop_servo(part))
        elif kind == "positional":
            add(
                at_ms,
                build_body_servo(
                    command.get("angle") if command.get("angle") is not None else 90,
                    int(command.get("pulse_us")) if command.get("pulse_us") is not None else None,
                ),
            )

    return sorted(moments.items(), key=lambda item: item[0])


def script_cycle_duration_ms(
    play: MotionScriptPlayData,
    moments: list[tuple[int, list[dict[str, Any]]]],
) -> int:
    duration_ms = max(_duration_ms(play.script), _duration_ms(play.low_level))
    if moments:
        duration_ms = max(duration_ms, int(moments[-1][0]))
    return max(1, duration_ms)


def _duration_ms(value: dict[str, Any] | None) -> int:
    if not isinstance(value, dict):
        return 0
    try:
        return max(0, int(value.get("duration_ms") or 0))
    except (TypeError, ValueError):
        return 0


def target_parts(part: str | None) -> list[str]:
    normalized = str(part or "all")
    normalized = PART_ALIASES.get(normalized, normalized)
    if normalized in PART_GROUPS:
        return PART_GROUPS[normalized]
    if normalized in SERVO_PARTS:
        return [normalized]
    return []


def physical_direction_for_visual(part: str, direction: str) -> str:
    normalized = normalize_direction(direction)
    drive_reverse = SERVO_PARTS[part].get("drive_reverse", SERVO_PARTS[part].get("reverse"))
    if not drive_reverse:
        return normalized
    return "cw" if normalized == "ccw" else "ccw"


def normalize_direction(direction: str | None) -> str:
    return "ccw" if direction == "ccw" else "cw"


def pulse_for_continuous(part: str, physical_direction: str, speed: str) -> int:
    spec = SERVO_PARTS[part]
    if speed == "slow":
        return spec["slow_cw_us"] if physical_direction == "cw" else spec["slow_ccw_us"]
    return spec["fast_cw_us"] if physical_direction == "cw" else spec["fast_ccw_us"]


def safe_continuous_duration_ms(part: str, speed: str, duration_ms: int | None) -> int | None:
    normalized_duration_ms = int(duration_ms or 0)
    if part not in EAR_PARTS:
        return normalized_duration_ms if normalized_duration_ms > 0 else None

    max_duration_ms = max_continuous_duration_ms(part, speed)
    if normalized_duration_ms <= 0:
        return max_duration_ms
    return min(normalized_duration_ms, max_duration_ms)


def max_continuous_duration_ms(part: str, speed: str) -> int:
    spec = SERVO_PARTS[part]
    speed_scale = CONTINUOUS_SLOW_SCALE if speed == "slow" else 1.0
    deg_per_ms = (90 / max(1, int(spec.get("ms_per_90_deg") or 620))) * speed_scale
    max_deg = min(EAR_MAX_OFFSET_DEG, int(spec.get("max_deg") or EAR_MAX_OFFSET_DEG))
    return max(1, round(max_deg / deg_per_ms))


def pulse_for_body(angle: float) -> int:
    spec = SERVO_PARTS["body"]
    normalized = (angle - spec["min_deg"]) / max(1, spec["max_deg"] - spec["min_deg"])
    return round(spec["min_pulse_us"] + (spec["max_pulse_us"] - spec["min_pulse_us"]) * normalized)


def _default_servo_state() -> dict[str, Any]:
    return {
        "left_ear": {"channel": 0, "kind": "continuous", "state": "stopped", "pulse_us": 1500},
        "right_ear": {"channel": 1, "kind": "continuous", "state": "stopped", "pulse_us": 1500},
        "left_arm": {"channel": 2, "kind": "continuous", "state": "stopped", "pulse_us": 1500},
        "right_arm": {"channel": 3, "kind": "continuous", "state": "stopped", "pulse_us": 1500},
        "body": {"channel": 4, "kind": "positional", "state": "at_angle", "angle": 90, "pulse_us": 1500},
    }


def clamp(value: float, min_value: int | float, max_value: int | float) -> float:
    return max(float(min_value), min(float(max_value), value))


def ease_in_out(t: float) -> float:
    limited = clamp(t, 0, 1)
    if limited < 0.5:
        return 2 * limited * limited
    return 1 - ((-2 * limited + 2) ** 2) / 2
