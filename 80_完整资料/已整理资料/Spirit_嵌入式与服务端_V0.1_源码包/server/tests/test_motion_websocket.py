import asyncio
import time

from fastapi.testclient import TestClient

from usaki_server.api.model import MotionScriptPlayData, now_ms
from usaki_server.api.motion import MotionHub, compile_low_level_moments, motion_hub
from usaki_server.main import app


def _message(message_type: str, seq: int, data: dict | None = None) -> dict:
    return {
        "id": f"msg_{seq}",
        "type": message_type,
        "device_id": "test-device",
        "timestamp": now_ms(),
        "seq": seq,
        "data": data or {},
    }


def test_motion_lab_command_is_pushed_to_motion_device() -> None:
    motion_hub.reset_for_tests()
    client = TestClient(app)

    with client.websocket_connect("/api/v1/motion/device?device_id=test-device") as device_ws:
        with client.websocket_connect("/api/v1/motion/lab?device_id=test-device") as lab_ws:
            initial = lab_ws.receive_json()
            assert initial["type"] == "motion.state"
            assert initial["data"]["online"] is True

            lab_ws.send_json(
                _message(
                    "motion.command",
                    1,
                    {
                        "command_id": "cmd_left_arm",
                        "source": "motion_lab",
                        "part": "left_arm",
                        "op": "drive",
                        "direction": "cw",
                        "speed": "fast",
                        "ttl_ms": 700,
                    },
                )
            )

            accepted = lab_ws.receive_json()
            assert accepted["type"] == "motion.ack"
            assert accepted["data"]["stage"] == "server_accepted"
            assert accepted["data"]["ok"] is True

            batch = device_ws.receive_json()
            assert batch["type"] == "motion.servo.batch"
            assert batch["data"]["ref_id"] == "msg_1"
            assert batch["data"]["servos"] == [
                {
                    "part": "left_arm",
                    "channel": 2,
                    "kind": "continuous",
                    "op": "drive",
                    "direction": "ccw",
                    "speed": "fast",
                    "pulse_us": 1150,
                    "ttl_ms": 700,
                }
            ]

            sent = lab_ws.receive_json()
            assert sent["type"] == "motion.ack"
            assert sent["data"]["stage"] == "device_sent"


def test_motion_stop_pushes_all_safe_outputs() -> None:
    motion_hub.reset_for_tests()
    client = TestClient(app)

    with client.websocket_connect("/api/v1/motion/device?device_id=test-device") as device_ws:
        with client.websocket_connect("/api/v1/motion/lab?device_id=test-device") as lab_ws:
            assert lab_ws.receive_json()["type"] == "motion.state"

            lab_ws.send_json(_message("motion.stop", 2, {"part": "all"}))

            assert lab_ws.receive_json()["data"]["stage"] == "server_accepted"
            batch = device_ws.receive_json()
            assert batch["type"] == "motion.servo.batch"
            assert batch["data"]["servos"] == [
                {"part": "left_ear", "channel": 0, "kind": "continuous", "op": "stop", "pulse_us": 1500},
                {"part": "right_ear", "channel": 1, "kind": "continuous", "op": "stop", "pulse_us": 1500},
                {"part": "left_arm", "channel": 2, "kind": "continuous", "op": "stop", "pulse_us": 1500},
                {"part": "right_arm", "channel": 3, "kind": "continuous", "op": "stop", "pulse_us": 1500},
                {"part": "body", "channel": 4, "kind": "positional", "op": "set_angle", "angle": 90, "pulse_us": 1500},
            ]


def test_ear_drive_is_limited_to_safe_duration() -> None:
    motion_hub.reset_for_tests()
    client = TestClient(app)

    with client.websocket_connect("/api/v1/motion/device?device_id=test-device") as device_ws:
        with client.websocket_connect("/api/v1/motion/lab?device_id=test-device") as lab_ws:
            assert lab_ws.receive_json()["type"] == "motion.state"

            lab_ws.send_json(
                _message(
                    "motion.command",
                    3,
                    {
                        "command_id": "cmd_left_ear",
                        "source": "motion_lab",
                        "part": "left_ear",
                        "op": "drive",
                        "direction": "cw",
                        "speed": "fast",
                        "duration_ms": 5000,
                    },
                )
            )

            assert lab_ws.receive_json()["data"]["stage"] == "server_accepted"
            batch = device_ws.receive_json()
            assert batch["data"]["servos"] == [
                {
                    "part": "left_ear",
                    "channel": 0,
                    "kind": "continuous",
                    "op": "drive",
                    "direction": "cw",
                    "speed": "fast",
                    "pulse_us": 1850,
                    "duration_ms": 207,
                }
            ]

            assert lab_ws.receive_json()["data"]["stage"] == "device_sent"


def test_right_ear_visual_direction_maps_to_physical_reverse() -> None:
    motion_hub.reset_for_tests()
    client = TestClient(app)

    with client.websocket_connect("/api/v1/motion/device?device_id=test-device") as device_ws:
        with client.websocket_connect("/api/v1/motion/lab?device_id=test-device") as lab_ws:
            assert lab_ws.receive_json()["type"] == "motion.state"

            lab_ws.send_json(
                _message(
                    "motion.command",
                    4,
                    {
                        "command_id": "cmd_right_ear",
                        "source": "motion_lab",
                        "part": "right_ear",
                        "op": "drive",
                        "direction": "cw",
                        "speed": "fast",
                        "duration_ms": 120,
                    },
                )
            )

            assert lab_ws.receive_json()["data"]["stage"] == "server_accepted"
            batch = device_ws.receive_json()
            assert batch["data"]["servos"] == [
                {
                    "part": "right_ear",
                    "channel": 1,
                    "kind": "continuous",
                    "op": "drive",
                    "direction": "ccw",
                    "speed": "fast",
                    "pulse_us": 1150,
                    "duration_ms": 120,
                }
            ]

            assert lab_ws.receive_json()["data"]["stage"] == "device_sent"


def test_motion_command_can_override_physical_direction_and_pulse() -> None:
    motion_hub.reset_for_tests()
    client = TestClient(app)

    with client.websocket_connect("/api/v1/motion/device?device_id=test-device") as device_ws:
        with client.websocket_connect("/api/v1/motion/lab?device_id=test-device") as lab_ws:
            assert lab_ws.receive_json()["type"] == "motion.state"

            lab_ws.send_json(
                _message(
                    "motion.command",
                    5,
                    {
                        "command_id": "cmd_calibrated_right_ear",
                        "source": "motion_lab",
                        "part": "right_ear",
                        "op": "drive",
                        "direction": "cw",
                        "physical_direction": "cw",
                        "speed": "fast",
                        "pulse_us": 1850,
                        "duration_ms": 120,
                    },
                )
            )

            assert lab_ws.receive_json()["data"]["stage"] == "server_accepted"
            batch = device_ws.receive_json()
            assert batch["data"]["servos"] == [
                {
                    "part": "right_ear",
                    "channel": 1,
                    "kind": "continuous",
                    "op": "drive",
                    "direction": "cw",
                    "speed": "fast",
                    "pulse_us": 1850,
                    "duration_ms": 120,
                }
            ]

            assert lab_ws.receive_json()["data"]["stage"] == "device_sent"


def test_both_arms_visual_direction_maps_to_mirrored_physical_outputs() -> None:
    motion_hub.reset_for_tests()
    client = TestClient(app)

    with client.websocket_connect("/api/v1/motion/device?device_id=test-device") as device_ws:
        with client.websocket_connect("/api/v1/motion/lab?device_id=test-device") as lab_ws:
            assert lab_ws.receive_json()["type"] == "motion.state"

            lab_ws.send_json(
                _message(
                    "motion.command",
                    6,
                    {
                        "command_id": "cmd_both_arms_forward",
                        "source": "motion_lab",
                        "part": "both_arms",
                        "op": "drive",
                        "direction": "cw",
                        "speed": "fast",
                        "duration_ms": 120,
                    },
                )
            )

            assert lab_ws.receive_json()["data"]["stage"] == "server_accepted"
            batch = device_ws.receive_json()
            assert batch["data"]["servos"] == [
                {
                    "part": "left_arm",
                    "channel": 2,
                    "kind": "continuous",
                    "op": "drive",
                    "direction": "ccw",
                    "speed": "fast",
                    "pulse_us": 1150,
                    "duration_ms": 120,
                },
                {
                    "part": "right_arm",
                    "channel": 3,
                    "kind": "continuous",
                    "op": "drive",
                    "direction": "cw",
                    "speed": "fast",
                    "pulse_us": 1850,
                    "duration_ms": 120,
                },
            ]

            assert lab_ws.receive_json()["data"]["stage"] == "device_sent"


def test_script_loop_waits_for_declared_duration_before_next_cycle() -> None:
    class StopAfterSecondCycle(Exception):
        pass

    async def run() -> None:
        hub = MotionHub()
        play_data = {
            "script_id": "loop_test",
            "source": "motion_lab",
            "loop": True,
            "script": {
                "version": "0.1",
                "name": "loop_test",
                "duration_ms": 80,
                "loop": True,
                "tracks": {},
            },
            "low_level": {
                "version": "0.1",
                "name": "loop_test",
                "duration_ms": 80,
                "commands": [
                    {"at": 0, "part": "body", "type": "positional", "angle": 92, "pulse_us": 1511}
                ],
            },
        }
        moments = compile_low_level_moments(play_data["low_level"])
        sent_at: list[float] = []

        async def fake_broadcast_ack(*_args, **_kwargs) -> None:
            return None

        async def fake_broadcast_state(*_args, **_kwargs) -> None:
            return None

        async def fake_send_batch(*_args, **_kwargs) -> bool:
            sent_at.append(time.perf_counter())
            if len(sent_at) >= 2:
                raise StopAfterSecondCycle
            return True

        hub.broadcast_ack = fake_broadcast_ack  # type: ignore[method-assign]
        hub.broadcast_state = fake_broadcast_state  # type: ignore[method-assign]
        hub.send_batch = fake_send_batch  # type: ignore[method-assign]

        try:
            await hub.run_script(
                "test-device",
                "msg_loop",
                MotionScriptPlayData.model_validate(play_data),
                moments,
            )
        except StopAfterSecondCycle:
            pass

        assert len(sent_at) == 2
        assert sent_at[1] - sent_at[0] >= 0.05

    asyncio.run(run())
