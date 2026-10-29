#pragma once
#include "esp_err.h"
#ifdef __cplusplus
extern "C" {
#endif
// Start only after Wi-Fi. Empty/example.invalid URL deliberately leaves link off.
// Local development control only; not a provisioned/authenticated product API.
esp_err_t spirit_link_start(void);
#ifdef __cplusplus
}
#endif
