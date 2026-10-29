"""Development-only effect gateway; not an authenticated deployment API.

No cloud or LLM can initiate effects. Telemetry never enters conversational memory.
All transport writes are serialized; only one pending command per device.
"""
import asyncio
import json
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from usaki_server.devices.spirit import SpiritAck, SpiritEffect, SpiritMessage, SpiritTelemetry

router = APIRouter()
MAX_FRAME_BYTES = 4096
MAX_DEVICES = 32


@dataclass
class Connection:
    ws: WebSocket
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    telemetry: SpiritTelemetry | None = None
    seen_at: float = 0
    seq: int = -1
    outbound_seq: int = 0
    pending: str | None = None
    pending_until: float = 0
    last_ack: SpiritAck | None = None
    used_ids: set[str] = field(default_factory=set)


connections: dict[str, Connection] = {}


@router.websocket("/device")
async def device_socket(ws: WebSocket):
    device_id = ws.query_params.get("device_id", "")
    import re
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", device_id):
        await ws.close(code=1008)
        return
    if device_id in connections or len(connections) >= MAX_DEVICES:
        await ws.close(code=1008)
        return
    await ws.accept()
    connection = Connection(ws)
    connections[device_id] = connection
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
                await ws.close(code=1009)
                return
            try:
                message = SpiritMessage.model_validate(json.loads(raw))
                if message.device_id != device_id or message.seq <= connection.seq:
                    raise ValueError("identity or sequence mismatch")
                if message.type == "spirit.telemetry":
                    telemetry = SpiritTelemetry.model_validate(message.data)
                    connection.telemetry = telemetry
                    connection.seen_at = time.monotonic()
                else:
                    ack = SpiritAck.model_validate(message.data)
                    if ack.command_id not in connection.used_ids:
                        raise ValueError("unexpected acknowledgment")
                    # A stop may supersede a running command. Its late ACK must
                    # not disconnect the session or clear the newer pending stop.
                    if ack.command_id == connection.pending:
                        connection.last_ack = ack
                        connection.pending = None
                connection.seq = message.seq
            except (ValidationError, ValueError, TypeError):
                # Do not reflect untrusted payloads or NFC identifiers into logs.
                await ws.close(code=1008)
                return
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if connections.get(device_id) is connection:
            connections.pop(device_id, None)


@router.get("/{device_id}/state")
async def device_state(device_id: str):
    connection = connections.get(device_id)
    if connection is None:
        raise HTTPException(404, "device offline")
    # No NFC UID in operator status; raw UID is ephemeral, unauthenticated telemetry.
    return {"online": True,
            "telemetry": connection.telemetry.model_dump(exclude={"nfc_uid"}) if connection.telemetry else None,
            "telemetry_age_ms": int((time.monotonic()-connection.seen_at)*1000) if connection.seen_at else None,
            "pending_command": connection.pending,
            "last_ack": connection.last_ack.model_dump() if connection.last_ack else None}


@router.post("/{device_id}/effects", status_code=202)
async def send_effect(device_id: str, effect: SpiritEffect):
    connection = connections.get(device_id)
    if connection is None:
        raise HTTPException(409, "device offline")
    async with connection.lock:
        now = time.monotonic()
        if effect.command_id in connection.used_ids:
            raise HTTPException(409, "duplicate command_id")
        if len(connection.used_ids) >= 1024:
            raise HTTPException(409, "session command limit; reconnect required")
        if effect.effect != "stop":
            if connection.pending and now <= connection.pending_until:
                raise HTTPException(409, "command awaiting acknowledgment")
            state = connection.telemetry
            if not state or now-connection.seen_at > 3:
                raise HTTPException(409, "fresh telemetry required")
            if effect.effect == "blade":
                raise HTTPException(422, "blade protocol not verified")
            if not state.haptic_ready:
                raise HTTPException(409, "haptic calibration not confirmed")
        connection.outbound_seq += 1
        payload = {"id": effect.command_id, "type": "spirit.effect", "device_id": device_id,
                   "seq": connection.outbound_seq, "data": effect.model_dump()}
        connection.used_ids.add(effect.command_id)
        connection.pending = effect.command_id
        connection.pending_until = now + effect.ttl_ms/1000
        try:
            await connection.ws.send_json(payload)
        except (WebSocketDisconnect, RuntimeError):
            connection.pending = None
            raise HTTPException(409, "device disconnected")
    return {"command_id": effect.command_id, "status": "sent", "applied": False}
