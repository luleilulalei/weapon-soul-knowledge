#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    const char *state;
    int reset_reason;
    int free_heap_bytes;
} device_reporter_status_t;

esp_err_t device_reporter_post_status(const device_reporter_status_t *status);
esp_err_t device_reporter_post_wakeup(const char *wake_word);

#ifdef __cplusplus
}
#endif
