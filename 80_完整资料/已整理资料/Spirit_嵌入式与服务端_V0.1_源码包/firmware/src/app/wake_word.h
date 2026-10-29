#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t wake_word_handle_detected(const char *wake_word);
esp_err_t wake_word_engine_start(void);

#ifdef __cplusplus
}
#endif
