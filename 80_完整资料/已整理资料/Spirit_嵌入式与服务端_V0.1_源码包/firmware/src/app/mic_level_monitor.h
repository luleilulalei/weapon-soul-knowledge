#pragma once

#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int32_t direction_delta_floor;
    int32_t direction_delta_divisor;
    uint32_t read_timeout_ms;
} mic_level_monitor_config_t;

esp_err_t mic_level_monitor_init(const mic_level_monitor_config_t *config);
void mic_level_monitor_print_once(void);
void mic_level_monitor_log_if_sound(void);

#ifdef __cplusplus
}
#endif
