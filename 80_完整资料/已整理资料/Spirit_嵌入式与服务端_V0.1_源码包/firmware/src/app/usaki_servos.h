#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    USAKI_SERVO_LEFT_EAR = 0,
    USAKI_SERVO_RIGHT_EAR,
    USAKI_SERVO_LEFT_ARM,
    USAKI_SERVO_RIGHT_ARM,
    USAKI_SERVO_TURNTABLE,
    USAKI_SERVO_COUNT,
} usaki_servo_id_t;

typedef struct {
    usaki_servo_id_t id;
    const char *name;
    uint8_t channel;
    uint16_t min_pulse_us;
    uint16_t center_pulse_us;
    uint16_t max_pulse_us;
} usaki_servo_spec_t;

esp_err_t usaki_servos_init(void);
esp_err_t usaki_servos_init_outputs_disabled(void);
esp_err_t usaki_servos_deinit(void);
esp_err_t usaki_servos_set_pulse_us(usaki_servo_id_t id, uint16_t pulse_us);
esp_err_t usaki_servos_set_angle(usaki_servo_id_t id, uint8_t angle_deg);
esp_err_t usaki_servos_center(usaki_servo_id_t id);
esp_err_t usaki_servos_center_all(void);
esp_err_t usaki_servos_disable(usaki_servo_id_t id);
esp_err_t usaki_servos_disable_all(void);
const usaki_servo_spec_t *usaki_servos_get_specs(size_t *count);

#ifdef __cplusplus
}
#endif
