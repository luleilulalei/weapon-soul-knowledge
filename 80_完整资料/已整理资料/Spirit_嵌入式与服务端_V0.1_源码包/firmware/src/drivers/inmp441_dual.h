#pragma once

#include <stddef.h>
#include <stdint.h>

#include "driver/gpio.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define INMP441_DUAL_DEFAULT_SAMPLE_RATE_HZ 16000
#define INMP441_DUAL_DEFAULT_READ_FRAMES 256
#define INMP441_DUAL_MAX_READ_FRAMES 512
#define INMP441_DUAL_DEFAULT_DMA_DESC_NUM 6
#define INMP441_DUAL_DEFAULT_SAMPLE_SHIFT_BITS 14

typedef struct {
    int i2s_port;
    gpio_num_t ws_gpio;
    gpio_num_t bclk_gpio;
    gpio_num_t data_gpio;
    uint32_t sample_rate_hz;
    size_t read_frames;
    uint32_t dma_desc_num;
    int sample_shift_bits;
} inmp441_dual_config_t;

typedef struct {
    int32_t left_avg;
    int32_t right_avg;
    int32_t left_peak;
    int32_t right_peak;
    uint32_t frames;
} inmp441_dual_level_t;

esp_err_t inmp441_dual_init(const inmp441_dual_config_t *config);
esp_err_t inmp441_dual_read_raw_interleaved_s32(int32_t *samples,
                                                size_t frame_capacity,
                                                size_t *frames_read,
                                                uint32_t timeout_ms);
esp_err_t inmp441_dual_read_level(inmp441_dual_level_t *level, uint32_t timeout_ms);
esp_err_t inmp441_dual_deinit(void);

#ifdef __cplusplus
}
#endif
