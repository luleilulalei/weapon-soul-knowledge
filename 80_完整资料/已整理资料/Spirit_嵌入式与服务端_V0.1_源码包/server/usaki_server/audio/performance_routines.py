from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from usaki_server.api.model import EmotionUpdateData, MotionScriptPlayData, now_ms

logger = logging.getLogger(__name__)

SHOTA_WAIST_TWIST_ROUTINE = "shota_waist_twist_30s_no_ears"
_SHOTA_TRIGGER_ANGRY_MS = 8000
_SHOTA_DANCE_STAR_MS = 33000
_ROUTINE_SCRIPT_PATHS = {
    SHOTA_WAIST_TWIST_ROUTINE: Path(__file__).resolve().parents[3]
    / "tools"
    / "motion_lab"
    / "dances"
    / "shota-waist-twist.json",
}


def scripted_reply_for_text(text: str) -> str | None:
    normalized = _normalize(text)
    if not normalized:
        return None
    if _is_shota_setup(normalized):
        return "可我早就不扭了。"
    if _is_shota_dance_trigger(normalized):
        return "什么，把我的领带拿来。"
    return None


def motion_routine_for_text(text: str) -> str | None:
    normalized = _normalize(text)
    if not normalized:
        return None
    if _is_shota_dance_trigger(normalized):
        return SHOTA_WAIST_TWIST_ROUTINE
    return None


def pre_response_eye_emotion_for_text(text: str) -> EmotionUpdateData | None:
    normalized = _normalize(text)
    if not normalized:
        return None
    if _is_shota_setup(normalized):
        return EmotionUpdateData(emotion="idle", intensity=1.0)
    if _is_shota_dance_trigger(normalized):
        return EmotionUpdateData(
            emotion="angry",
            intensity=1.0,
            duration_ms=_SHOTA_TRIGGER_ANGRY_MS,
        )
    return None


def output_start_eye_emotion_for_text(text: str) -> EmotionUpdateData | None:
    normalized = _normalize(text)
    if not normalized:
        return None
    if _is_shota_setup(normalized):
        return EmotionUpdateData(emotion="idle", intensity=1.0)
    if _is_shota_dance_trigger(normalized):
        return EmotionUpdateData(
            emotion="angry",
            intensity=1.0,
            duration_ms=_SHOTA_TRIGGER_ANGRY_MS,
        )
    return None


def post_response_eye_emotion_for_text(text: str) -> EmotionUpdateData | None:
    normalized = _normalize(text)
    if not normalized:
        return None
    if _is_shota_dance_trigger(normalized):
        return EmotionUpdateData(
            emotion="star",
            intensity=1.0,
            duration_ms=_SHOTA_DANCE_STAR_MS,
        )
    return None


async def start_motion_routine(device_id: str, routine: str) -> bool:
    from usaki_server.api.motion import compile_script_moments, motion_hub

    if device_id not in motion_hub.devices:
        logger.warning(
            "[USAKI CHOREO] skip routine; motion device offline device_id=%s routine=%s",
            device_id,
            routine,
        )
        return False

    script = load_motion_script(routine)
    if script is None:
        return False

    moments = compile_script_moments(script)
    if not moments:
        logger.warning("[USAKI CHOREO] skip empty routine routine=%s", routine)
        return False

    script_id = f"voice_{routine}_{now_ms()}"
    play = MotionScriptPlayData(
        script_id=script_id,
        source="voice_choreography",
        interrupt=True,
        loop=bool(script.get("loop")),
        script=script,
    )
    motion_hub.cancel_script(device_id)
    motion_hub.cancel_auto_stops(device_id, "all")
    task = asyncio.create_task(
        motion_hub.run_script(
            device_id,
            f"voice_choreography_{now_ms()}",
            play,
            moments,
        )
    )
    motion_hub.script_tasks[device_id] = task
    logger.warning(
        "[USAKI CHOREO] started routine device_id=%s routine=%s script_id=%s moments=%d",
        device_id,
        routine,
        script_id,
        len(moments),
    )
    return True


def load_motion_script(routine: str) -> dict[str, Any] | None:
    path = _ROUTINE_SCRIPT_PATHS.get(routine)
    if path is None:
        logger.warning("[USAKI CHOREO] unknown routine=%s", routine)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.warning("[USAKI CHOREO] read routine failed path=%s error=%s", path, exc)
    except json.JSONDecodeError as exc:
        logger.warning("[USAKI CHOREO] parse routine failed path=%s error=%s", path, exc)
    return None


def _is_shota_setup(text: str) -> bool:
    return all(
        token in text
        for token in (
            "正太",
            "扭",
        )
    ) and _has_any(text, ("妹子", "扭不过", "隔壁"))


def _is_shota_dance_trigger(text: str) -> bool:
    if _has_any(text, ("emo也在", "emo在", "可是语数也在", "语数也在", "语速也在")):
        return True
    if "emo" in text and _has_any(text, ("也在", "在")):
        return True
    if "领带" in text and _has_any(text, ("拿来", "给我", "把我", "开始")):
        return True
    if _has_any(text, ("开始跳这段舞", "跳这段舞", "正太扭腰舞")):
        return True
    return False


def _normalize(text: str) -> str:
    return "".join(str(text or "").strip().lower().split())


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)
