#pragma once

#include <stdint.h>

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define GC9A01_WIDTH 240
#define GC9A01_HEIGHT 240
#define GC9A01_CMD_BITS 8
#define GC9A01_PARAM_BITS 8

typedef struct gc9a01 *gc9a01_handle_t;

typedef struct {
    spi_host_device_t host_id;
    gpio_num_t sclk_gpio;
    gpio_num_t mosi_gpio;
    gpio_num_t miso_gpio;
    int max_transfer_sz;
} gc9a01_bus_config_t;

typedef struct {
    spi_host_device_t host_id;
    gpio_num_t cs_gpio;
    gpio_num_t dc_gpio;
    gpio_num_t reset_gpio;
    int pixel_clock_hz;
    uint8_t madctl;
} gc9a01_config_t;

esp_err_t gc9a01_bus_init(const gc9a01_bus_config_t *config);
esp_err_t gc9a01_create(const gc9a01_config_t *config, gc9a01_handle_t *out_handle);
esp_err_t gc9a01_display_on(gc9a01_handle_t handle);
esp_err_t gc9a01_fill_screen(gc9a01_handle_t handle, uint16_t rgb565);
esp_err_t gc9a01_fill_rect(gc9a01_handle_t handle, int x, int y, int width, int height, uint16_t rgb565);
esp_err_t gc9a01_draw_bitmap(gc9a01_handle_t handle, int x0, int y0, int x1, int y1, const uint16_t *rgb565_pixels);
esp_err_t gc9a01_destroy(gc9a01_handle_t handle);

#ifdef __cplusplus
}
#endif
