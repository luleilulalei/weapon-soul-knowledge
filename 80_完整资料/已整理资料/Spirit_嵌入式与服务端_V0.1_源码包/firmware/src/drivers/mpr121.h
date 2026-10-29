#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct mpr121 *mpr121_handle_t;

typedef struct {
    i2c_port_num_t i2c_port;
    gpio_num_t sda_gpio;
    gpio_num_t scl_gpio;
    uint32_t i2c_freq_hz;
    uint8_t i2c_addr;
} mpr121_config_t;

esp_err_t mpr121_create(const mpr121_config_t *config, mpr121_handle_t *out_handle);
esp_err_t mpr121_read_register(mpr121_handle_t handle, uint8_t reg, uint8_t *value);
esp_err_t mpr121_read_touched(mpr121_handle_t handle, uint16_t *touched_mask);
esp_err_t mpr121_read_electrode(mpr121_handle_t handle, uint8_t electrode, uint16_t *filtered, uint8_t *baseline);
esp_err_t mpr121_destroy(mpr121_handle_t handle);

#ifdef __cplusplus
}
#endif
