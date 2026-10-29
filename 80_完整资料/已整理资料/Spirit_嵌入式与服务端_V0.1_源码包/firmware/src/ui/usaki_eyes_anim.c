#include "ui/usaki_eyes_internal.h"

static char ascii_lower_char(char c)
{
    if (c >= 'A' && c <= 'Z') {
        return (char)(c + ('a' - 'A'));
    }
    return c;
}

bool usaki_eye_text_contains_token(const char *text, const char *token)
{
    if (text == NULL || token == NULL || token[0] == '\0') {
        return false;
    }
    for (const char *p = text; *p != '\0'; ++p) {
        const char *a = p;
        const char *b = token;
        while (*a != '\0' && *b != '\0' && ascii_lower_char(*a) == ascii_lower_char(*b)) {
            ++a;
            ++b;
        }
        if (*b == '\0') {
            return true;
        }
    }
    return false;
}

bool usaki_eye_emotion_from_name(const char *name, usaki_eye_emotion_t *out)
{
    if (name == NULL || out == NULL) {
        return false;
    }

    if (usaki_eye_text_contains_token(name, "fire") ||
        usaki_eye_text_contains_token(name, "furious") ||
        usaki_eye_text_contains_token(name, "rage") ||
        usaki_eye_text_contains_token(name, "发火") ||
        usaki_eye_text_contains_token(name, "暴怒") ||
        usaki_eye_text_contains_token(name, "火大") ||
        usaki_eye_text_contains_token(name, "炸毛")) {
        *out = USAKI_EYE_EMOTION_FIRE;
        return true;
    }
    if (usaki_eye_text_contains_token(name, "wronged") ||
        usaki_eye_text_contains_token(name, "sad") ||
        usaki_eye_text_contains_token(name, "委屈") ||
        usaki_eye_text_contains_token(name, "难过") ||
        usaki_eye_text_contains_token(name, "伤心") ||
        usaki_eye_text_contains_token(name, "想哭") ||
        usaki_eye_text_contains_token(name, "低落")) {
        *out = USAKI_EYE_EMOTION_WRONGED;
        return true;
    }
    if (usaki_eye_text_contains_token(name, "heart") ||
        usaki_eye_text_contains_token(name, "love") ||
        usaki_eye_text_contains_token(name, "happy") ||
        usaki_eye_text_contains_token(name, "心心") ||
        usaki_eye_text_contains_token(name, "爱心") ||
        usaki_eye_text_contains_token(name, "喜欢") ||
        usaki_eye_text_contains_token(name, "爱你") ||
        usaki_eye_text_contains_token(name, "贴贴") ||
        usaki_eye_text_contains_token(name, "开心")) {
        *out = USAKI_EYE_EMOTION_HEART;
        return true;
    }
    if (usaki_eye_text_contains_token(name, "star") ||
        usaki_eye_text_contains_token(name, "excited") ||
        usaki_eye_text_contains_token(name, "surprised") ||
        usaki_eye_text_contains_token(name, "curious") ||
        usaki_eye_text_contains_token(name, "星星") ||
        usaki_eye_text_contains_token(name, "惊喜") ||
        usaki_eye_text_contains_token(name, "好奇") ||
        usaki_eye_text_contains_token(name, "兴奋")) {
        *out = USAKI_EYE_EMOTION_STAR;
        return true;
    }
    if (usaki_eye_text_contains_token(name, "angry") ||
        usaki_eye_text_contains_token(name, "glare") ||
        usaki_eye_text_contains_token(name, "mad") ||
        usaki_eye_text_contains_token(name, "怒") ||
        usaki_eye_text_contains_token(name, "生气") ||
        usaki_eye_text_contains_token(name, "瞪") ||
        usaki_eye_text_contains_token(name, "凶")) {
        *out = USAKI_EYE_EMOTION_ANGRY;
        return true;
    }
    if (usaki_eye_text_contains_token(name, "scan") ||
        usaki_eye_text_contains_token(name, "thinking") ||
        usaki_eye_text_contains_token(name, "loading") ||
        usaki_eye_text_contains_token(name, "思考") ||
        usaki_eye_text_contains_token(name, "扫描")) {
        *out = USAKI_EYE_EMOTION_SCAN;
        return true;
    }
    if (usaki_eye_text_contains_token(name, "sleepy") ||
        usaki_eye_text_contains_token(name, "困")) {
        *out = USAKI_EYE_EMOTION_SLEEPY;
        return true;
    }
    if (usaki_eye_text_contains_token(name, "sleep") ||
        usaki_eye_text_contains_token(name, "睡")) {
        *out = USAKI_EYE_EMOTION_SLEEP;
        return true;
    }
    if (usaki_eye_text_contains_token(name, "low_battery") ||
        usaki_eye_text_contains_token(name, "battery") ||
        usaki_eye_text_contains_token(name, "低电量")) {
        *out = USAKI_EYE_EMOTION_LOW_BATTERY;
        return true;
    }
    if (usaki_eye_text_contains_token(name, "idle") ||
        usaki_eye_text_contains_token(name, "normal") ||
        usaki_eye_text_contains_token(name, "calm") ||
        usaki_eye_text_contains_token(name, "默认") ||
        usaki_eye_text_contains_token(name, "正常") ||
        usaki_eye_text_contains_token(name, "恢复")) {
        *out = USAKI_EYE_EMOTION_IDLE;
        return true;
    }

    return false;
}
