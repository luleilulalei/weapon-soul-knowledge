from __future__ import annotations

import re

from usaki_server.api.model import BodyActionData, BodyActionItem


def body_actions_for_text(text: str) -> BodyActionData | None:
    normalized = text.strip().lower()
    if not normalized:
        return None

    if _has_any(normalized, ("停", "停止", "别动", "不要动", "停下")):
        return BodyActionData(actions=[BodyActionItem(part="all", action="stop")])

    actions: list[BodyActionItem] = []

    if _has_any(normalized, ("跳舞", "动起来", "活动一下", "表演一下")):
        actions.append(BodyActionItem(part="all", action="dance", count=1))
        return BodyActionData(actions=actions)

    body_angle_action = _body_angle_action_for_text(normalized)
    if body_angle_action is not None:
        return BodyActionData(actions=[body_angle_action])

    rotation_degrees = _rotation_degrees_for_text(normalized)
    if rotation_degrees is not None:
        actions.append(
            BodyActionItem(
                part=_rotation_part_for_text(normalized),
                action="rotate_degrees",
                angle=rotation_degrees,
            )
        )
        return BodyActionData(actions=actions)

    if _has_any(normalized, ("耳朵", "摇耳", "动耳")) and _has_any(
        normalized, ("摇", "动", "摆", "晃", "转")
    ):
        actions.append(
            BodyActionItem(part="both_ears", action="wiggle", count=2, duration_ms=520)
        )

    if _has_any(
        normalized,
        (
            "挥手",
            "挥挥手",
            "招手",
            "左手",
            "右手",
            "双手",
            "两个手",
            "两只手",
            "手臂",
            "胳膊",
            "小手",
        ),
    ) and _has_any(
        normalized, ("挥", "动", "摇", "摆", "抬", "转")
    ):
        actions.append(
            BodyActionItem(
                part=_arm_part_for_text(normalized),
                action="wave",
                count=2,
                duration_ms=680,
            )
        )

    if _has_any(
        normalized,
        (
            "身体",
            "身子",
            "转台",
            "底座",
            "转身",
            "旋转",
            "摇摆",
            "左转",
            "右转",
            "向左",
            "向右",
            "转一圈",
            "转个圈",
            "转一下",
            "摇一摇",
            "扭一扭",
            "晃一晃",
            "晃晃",
            "晃身体",
            "晃身子",
        ),
    ) and _has_any(normalized, ("转", "摇", "摆", "扭", "动", "晃")):
        actions.append(_body_action_for_text(normalized))

    if not actions:
        return None
    return BodyActionData(actions=actions[:6])


def _arm_part_for_text(text: str) -> str:
    if _has_any(text, ("左手", "左臂", "左边手", "左手臂")):
        return "left_arm"
    if _has_any(text, ("右手", "右臂", "右边手", "右手臂")):
        return "right_arm"
    if _has_any(text, ("双手", "两个手", "两只手", "双臂")):
        return "both_arms"
    return "both_arms"


def _body_action_for_text(text: str) -> BodyActionItem:
    if _has_any(text, ("左转", "往左", "向左")):
        return BodyActionItem(part="body", action="rotate_left", duration_ms=900)
    if _has_any(text, ("右转", "往右", "向右")):
        return BodyActionItem(part="body", action="rotate_right", duration_ms=900)
    return BodyActionItem(part="body", action="sway", count=2, duration_ms=650)


def _body_angle_action_for_text(text: str) -> BodyActionItem | None:
    if not _is_body_text(text):
        return None

    if _has_any(text, ("回中", "归中", "居中", "回正", "正中", "中间", "回到中间")):
        return BodyActionItem(part="body", action="set_angle", angle=90)

    degrees = _extract_degrees(text)
    if degrees is None:
        return None

    if _has_any(text, ("转到", "转至", "到", "设到", "设置到", "定位到", "停在", "回到")) and not _has_any(
        text,
        ("顺时针", "逆时针", "正转", "反转", "左转", "右转", "往左", "往右", "向左", "向右"),
    ):
        return BodyActionItem(
            part="body",
            action="set_angle",
            angle=max(0, min(180, degrees)),
        )

    return None


def _rotation_part_for_text(text: str) -> str:
    if _has_any(text, ("耳朵", "摇耳", "动耳", "左耳", "右耳")):
        if _has_any(text, ("左耳", "左边耳")):
            return "left_ear"
        if _has_any(text, ("右耳", "右边耳")):
            return "right_ear"
        return "both_ears"
    if _has_any(text, ("手", "手臂", "胳膊", "臂")):
        return _arm_part_for_text(text)
    if _has_any(text, ("身体", "身子", "转台", "底座", "转身")):
        return "body"
    return "body"


def _is_body_text(text: str) -> bool:
    return _has_any(text, ("身体", "身子", "转台", "底座", "转身"))


def _rotation_degrees_for_text(text: str) -> int | None:
    if not _has_any(text, ("度", "90", "45", "180", "九十", "四十五", "一百八十", "一圈", "半圈")):
        return None
    if not _has_any(text, ("转", "旋", "顺时针", "逆时针", "正转", "反转", "左转", "右转")):
        return None

    degrees = _extract_degrees(text)
    if degrees is None:
        return None
    degrees = max(1, min(360, degrees))

    if _has_any(text, ("逆时针", "反转", "左转", "往左", "向左")):
        return -degrees
    return degrees


def _extract_degrees(text: str) -> int | None:
    match = re.search(r"(?P<value>\d{1,3})\s*度", text)
    if match:
        return int(match.group("value"))

    for word, value in (
        ("三百六十", 360),
        ("一百八十", 180),
        ("九十", 90),
        ("四十五", 45),
        ("三十", 30),
        ("六十", 60),
        ("一圈", 360),
        ("半圈", 180),
    ):
        if word in text:
            return value
    return None


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)
