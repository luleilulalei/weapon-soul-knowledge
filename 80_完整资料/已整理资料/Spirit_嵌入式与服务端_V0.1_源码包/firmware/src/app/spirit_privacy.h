#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#ifdef __cplusplus
#include <mutex>
std::recursive_mutex &spirit_privacy_gate();
extern "C" {
#endif
// NVS must already be initialized. Missing/unreadable setting defaults muted.
esp_err_t spirit_privacy_init(void);
bool spirit_privacy_muted(void);
uint32_t spirit_privacy_epoch(void);
esp_err_t spirit_privacy_set_muted(bool muted);
#ifdef __cplusplus
}
#endif
