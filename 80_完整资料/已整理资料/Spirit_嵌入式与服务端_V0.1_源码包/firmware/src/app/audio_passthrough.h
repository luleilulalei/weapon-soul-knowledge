#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t audio_passthrough_init(void);
void audio_passthrough_run(void);

#ifdef __cplusplus
}
#endif
