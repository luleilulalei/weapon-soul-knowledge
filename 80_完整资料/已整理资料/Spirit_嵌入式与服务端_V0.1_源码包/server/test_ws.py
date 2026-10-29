#!D:\code\usaki\usaki_server\.conda\python.exe
import sys
sys.path.insert(0, "D:\\code\\usaki\\usaki_server")

import asyncio
import json
import sys
import time

import websockets


async def test():
    uri = "ws://127.0.0.1:8000/api/v1/voice/voice?device_id=test-001"
    async with websockets.connect(uri) as ws:
        print("connected", file=sys.stderr)

        # voice.input.start
        msg = {
            "id": "msg_1",
            "type": "voice.input.start",
            "device_id": "test-001",
            "seq": 1,
            "data": {
                "request_id": "req_1",
                "codec": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "sample_bits": 16,
                "frame_duration_ms": 60,
                "mode": "stream",
                "vad": {"enabled": True, "source": "device"},
            },
        }
        await ws.send(json.dumps(msg))
        print("sent voice.input.start", file=sys.stderr)

        await asyncio.sleep(0.5)

        # voice.input.end
        msg2 = {
            "id": "msg_2",
            "type": "voice.input.end",
            "device_id": "test-001",
            "seq": 2,
            "data": {"request_id": "req_1", "reason": "manual", "duration_ms": 500},
        }
        await ws.send(json.dumps(msg2))
        print("sent voice.input.end", file=sys.stderr)

        # 等待最多 5 秒的回复
        try:
            async for m in ws:
                if isinstance(m, str):
                    print(f"recv text: {m[:200]}", file=sys.stderr)
                    parsed = json.loads(m)
                    if parsed.get("type") == "voice.output.end":
                        print("got voice.output.end, done", file=sys.stderr)
                        break
                else:
                    print(f"recv bytes: {len(m)}B", file=sys.stderr)
                break  # 只读一条
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)


asyncio.run(test())