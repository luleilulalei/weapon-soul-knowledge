#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"
#ifdef __cplusplus
extern "C" {
#endif
esp_err_t spirit_pdm_init(void);
esp_err_t spirit_pdm_enable(bool enable);
esp_err_t spirit_pdm_read(int16_t *samples, size_t count, size_t *read_count);
void spirit_pdm_deinit(void);
#ifdef __cplusplus
}
#endif
