#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    USAKI_EYE_EMOTION_IDLE = 0,
    USAKI_EYE_EMOTION_HAPPY,
    USAKI_EYE_EMOTION_SLEEPY,
    USAKI_EYE_EMOTION_SLEEP,
    USAKI_EYE_EMOTION_ANGRY,
    USAKI_EYE_EMOTION_SURPRISED,
    USAKI_EYE_EMOTION_SCAN,
    USAKI_EYE_EMOTION_LOW_BATTERY,
    USAKI_EYE_EMOTION_STAR,
    USAKI_EYE_EMOTION_HEART,
    USAKI_EYE_EMOTION_FIRE,
    USAKI_EYE_EMOTION_WRONGED,
} usaki_eye_emotion_t;

esp_err_t usaki_eyes_start(void);
void usaki_eyes_set_emotion(usaki_eye_emotion_t emotion);
bool usaki_eyes_set_emotion_name(const char *emotion);
bool usaki_eyes_set_emotion_name_for(const char *emotion, uint32_t duration_ms);
void usaki_eyes_wake(void);
void usaki_eyes_sleep(void);
void usaki_eyes_blink(void);
bool usaki_eyes_play_animation_name(const char *name);

/* Optional realtime overlays for voice/battery linkage. */
void usaki_eyes_set_speaking(bool speaking);
void usaki_eyes_set_battery(uint8_t percent);

#ifdef __cplusplus
}
#endif
