from usaki_server.audio.body_actions import body_actions_for_text


def _dump(text: str) -> dict:
    action = body_actions_for_text(text)
    assert action is not None
    return action.model_dump(exclude_none=True)


def test_generic_arm_command_targets_both_arms_with_larger_duration() -> None:
    assert _dump("挥挥手") == {
        "actions": [
            {
                "part": "both_arms",
                "action": "wave",
                "count": 2,
                "duration_ms": 680,
            }
        ]
    }


def test_right_arm_command_still_targets_right_arm() -> None:
    assert _dump("挥挥右手")["actions"][0]["part"] == "right_arm"


def test_body_sway_uses_larger_duration() -> None:
    assert _dump("身体摇一摇") == {
        "actions": [
            {
                "part": "body",
                "action": "sway",
                "count": 2,
                "duration_ms": 650,
            }
        ]
    }


def test_body_sway_accepts_wiggle_wording() -> None:
    assert _dump("晃晃身体") == {
        "actions": [
            {
                "part": "body",
                "action": "sway",
                "count": 2,
                "duration_ms": 650,
            }
        ]
    }


def test_ear_wiggle_uses_larger_duration() -> None:
    assert _dump("摇摇耳朵") == {
        "actions": [
            {
                "part": "both_ears",
                "action": "wiggle",
                "count": 2,
                "duration_ms": 520,
            }
        ]
    }
