from __future__ import annotations

from usaki_server.api.model import EmotionUpdateData, EyeAnimationData

_EXPLICIT_EYE_EMOTION_DURATION_MS = 10000


def eye_emotion_for_text(text: str) -> EmotionUpdateData | None:
    normalized = text.strip().lower()
    if not normalized:
        return None

    if _has_any(normalized, ("发火眼", "发火", "暴怒", "火大", "炸毛", "furious", "rage", "fire")):
        return EmotionUpdateData(emotion="fire", intensity=1.0, duration_ms=_EXPLICIT_EYE_EMOTION_DURATION_MS)
    if _has_any(normalized, ("委屈眼", "委屈", "难过", "伤心", "想哭", "低落", "sad", "wronged")):
        return EmotionUpdateData(emotion="wronged", intensity=0.92, duration_ms=_EXPLICIT_EYE_EMOTION_DURATION_MS)
    if _has_any(normalized, ("心心眼", "爱心眼", "爱心", "喜欢", "爱你", "贴贴", "heart", "love")):
        return EmotionUpdateData(emotion="heart", intensity=1.0, duration_ms=_EXPLICIT_EYE_EMOTION_DURATION_MS)
    if _has_any(normalized, ("星星眼", "星星", "惊喜", "好奇", "兴奋", "star", "excited", "curious")):
        return EmotionUpdateData(emotion="star", intensity=1.0, duration_ms=_EXPLICIT_EYE_EMOTION_DURATION_MS)
    if _has_any(normalized, ("怒目", "瞪眼", "瞪我", "生气", "凶一点", "angry", "glare", "mad")):
        return EmotionUpdateData(emotion="angry", intensity=0.95, duration_ms=_EXPLICIT_EYE_EMOTION_DURATION_MS)
    if _has_any(normalized, ("恢复正常", "普通眼", "默认眼", "正常", "冷静", "idle", "normal", "calm")):
        return EmotionUpdateData(emotion="idle", intensity=1.0)
    return None


def eye_animation_for_text(text: str) -> EyeAnimationData | None:
    normalized = text.strip().lower()
    if not normalized:
        return None

    if _has_any(normalized, ("眨眼", "眨一下", "眨眨眼", "blink")):
        return EyeAnimationData(name="blink", duration_ms=340, priority=4)
    return None


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)
