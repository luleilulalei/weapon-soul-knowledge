#pragma once

#include <stddef.h>
#include <stdint.h>

#include "driver/gpio.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MAX98357A_DEFAULT_SAMPLE_RATE_HZ 16000
#define MAX98357A_DEFAULT_DMA_DESC_NUM 4
#define MAX98357A_DEFAULT_DMA_FRAME_NUM 256

typedef struct max98357a *max98357a_handle_t;

typedef struct {
    int i2s_port;
    gpio_num_t bclk_gpio;
    gpio_num_t ws_gpio;
    gpio_num_t data_gpio;
    uint32_t sample_rate_hz;
    uint32_t dma_desc_num;
    uint32_t dma_frame_num;
} max98357a_config_t;

esp_err_t max98357a_create(const max98357a_config_t *config, max98357a_handle_t *out_handle);
esp_err_t max98357a_write_interleaved_i16(max98357a_handle_t handle,
                                          const int16_t *samples,
                                          size_t sample_count,
                                          uint32_t timeout_ms);
esp_err_t max98357a_write_silence(max98357a_handle_t handle, size_t frame_count, uint32_t timeout_ms);
esp_err_t max98357a_destroy(max98357a_handle_t handle);

#ifdef __cplusplus
}
#endif
