#pragma once

#include "esp_err.h"
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define USAKI_VOICE_RUNTIME_TASK_STACK_BYTES (16 * 1024)
#define USAKI_VOICE_RUNTIME_TASK_PRIORITY 5
#define USAKI_VOICE_RUNTIME_TASK_CORE 1

typedef enum {
    USAKI_VOICE_RUNTIME_STATE_BOOTING = 0,
    USAKI_VOICE_RUNTIME_STATE_IDLE,
    USAKI_VOICE_RUNTIME_STATE_CONNECTING,
    USAKI_VOICE_RUNTIME_STATE_LISTENING,
    USAKI_VOICE_RUNTIME_STATE_SPEAKING,
    USAKI_VOICE_RUNTIME_STATE_INTERRUPTED,
    USAKI_VOICE_RUNTIME_STATE_ERROR,
} usaki_voice_runtime_state_t;

esp_err_t voice_runtime_set_privacy_mute(bool mute);
esp_err_t voice_runtime_init(void);
void voice_runtime_run(void);
esp_err_t voice_runtime_start_listening(void);
esp_err_t voice_runtime_stop_listening(void);
esp_err_t voice_runtime_interrupt(void);
esp_err_t voice_runtime_play_sleepy_sound(void);
usaki_voice_runtime_state_t voice_runtime_get_state(void);

#ifdef __cplusplus
}
#endif
