"""Test multiple concurrent WS connections — each gets its own VoiceConnectionHandler."""
import asyncio
import json
import sys

import websockets


async def connect_and_say(device_id: str) -> str:
    """Open a WS, send voice.input.start + end, return device_id."""
    uri = f"ws://127.0.0.1:8000/api/v1/voice/voice?device_id={device_id}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "id": "msg_1", "type": "voice.input.start", "device_id": device_id,
            "seq": 1, "data": {
                "request_id": "req_1", "codec": "opus", "sample_rate": 16000,
                "channels": 1, "sample_bits": 16, "frame_duration_ms": 60,
                "mode": "stream", "vad": {"enabled": True, "source": "device"},
            },
        }))
        await asyncio.sleep(0.2)
        await ws.send(json.dumps({
            "id": "msg_2", "type": "voice.input.end", "device_id": device_id,
            "seq": 2, "data": {"request_id": "req_1", "reason": "manual"},
        }))
        # Read response
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        return device_id, len(resp)


async def main():
    results = await asyncio.gather(
        connect_and_say("dev-a"),
        connect_and_say("dev-b"),
        connect_and_say("dev-c"),
    )
    for dev, size in results:
        print(f"{dev}: got response {size}B", file=sys.stderr)
    print("ALL OK", file=sys.stderr)


asyncio.run(main())