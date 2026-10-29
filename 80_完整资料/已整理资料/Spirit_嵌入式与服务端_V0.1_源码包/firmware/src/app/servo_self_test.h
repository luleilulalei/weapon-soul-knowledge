#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t servo_self_test_run(void);
esp_err_t servo_self_test_run_ear_reset(void);
esp_err_t servo_self_test_run_ear_swing_30(void);
esp_err_t servo_self_test_run_arm_swing(void);
esp_err_t servo_self_test_run_body_swing(void);

#ifdef __cplusplus
}
#endif
