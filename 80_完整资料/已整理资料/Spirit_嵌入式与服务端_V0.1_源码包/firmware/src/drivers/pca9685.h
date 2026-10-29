#pragma once

#include <stdint.h>

#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct pca9685 *pca9685_handle_t;

typedef struct {
    i2c_port_num_t i2c_port;
    gpio_num_t sda_gpio;
    gpio_num_t scl_gpio;
    uint32_t i2c_freq_hz;
    uint8_t i2c_addr;
    uint16_t pwm_freq_hz;
} pca9685_config_t;

esp_err_t pca9685_create(const pca9685_config_t *config, pca9685_handle_t *out_handle);
esp_err_t pca9685_set_pwm(pca9685_handle_t handle, uint8_t channel, uint16_t on_tick, uint16_t off_tick);
esp_err_t pca9685_set_channel_off(pca9685_handle_t handle, uint8_t channel);
esp_err_t pca9685_set_servo_pulse_us(pca9685_handle_t handle, uint8_t channel, uint16_t pulse_us);
esp_err_t pca9685_destroy(pca9685_handle_t handle);

#ifdef __cplusplus
}
#endif
