#include "drivers/inmp441_dual.h"

#include <stdbool.h>
#include <stdlib.h>

#include "driver/i2s_common.h"
#include "driver/i2s_std.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"

static const char *TAG = "inmp441_dual";

static i2s_chan_handle_t s_rx_chan;
static inmp441_dual_config_t s_config;
static int32_t *s_samples = NULL;

static int64_t abs_i32(int32_t value)
{
    return value < 0 ? -(int64_t)value : value;
}

esp_err_t inmp441_dual_init(const inmp441_dual_config_t *config)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG, "config is null");
    ESP_RETURN_ON_FALSE(s_rx_chan == NULL, ESP_ERR_INVALID_STATE, TAG, "driver already initialized");
    ESP_RETURN_ON_FALSE(config->sample_rate_hz > 0, ESP_ERR_INVALID_ARG, TAG, "sample_rate_hz is zero");
    ESP_RETURN_ON_FALSE(config->read_frames > 0, ESP_ERR_INVALID_ARG, TAG, "read_frames is zero");
    ESP_RETURN_ON_FALSE(config->read_frames <= INMP441_DUAL_MAX_READ_FRAMES,
                        ESP_ERR_INVALID_ARG,
                        TAG,
                        "read_frames exceeds max");
    ESP_RETURN_ON_FALSE(config->dma_desc_num > 0, ESP_ERR_INVALID_ARG, TAG, "dma_desc_num is zero");
    ESP_RETURN_ON_FALSE(config->sample_shift_bits >= 0 && config->sample_shift_bits < 31,
                        ESP_ERR_INVALID_ARG,
                        TAG,
                        "invalid sample_shift_bits");

    s_config = *config;

    /* Allocate read buffer in PSRAM to save internal DRAM */
    if (s_samples == NULL) {
        const size_t buf_size = INMP441_DUAL_MAX_READ_FRAMES * 2 * sizeof(int32_t);
        s_samples = (int32_t *)heap_caps_malloc(buf_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (s_samples == NULL) {
            ESP_LOGW(TAG, "failed to allocate PSRAM buffer, fallback to internal");
            s_samples = (int32_t *)heap_caps_malloc(buf_size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
            if (s_samples == NULL) {
                i2s_del_channel(s_rx_chan);
                s_rx_chan = NULL;
                return ESP_ERR_NO_MEM;
            }
        }
    }

    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(s_config.i2s_port, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num = s_config.dma_desc_num;
    chan_cfg.dma_frame_num = s_config.read_frames;

    ESP_RETURN_ON_ERROR(i2s_new_channel(&chan_cfg, NULL, &s_rx_chan), TAG, "new i2s rx channel failed");

    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(s_config.sample_rate_hz),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = s_config.bclk_gpio,
            .ws = s_config.ws_gpio,
            .dout = I2S_GPIO_UNUSED,
            .din = s_config.data_gpio,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false,
            },
        },
    };

    esp_err_t err = i2s_channel_init_std_mode(s_rx_chan, &std_cfg);
    if (err != ESP_OK) {
        i2s_del_channel(s_rx_chan);
        s_rx_chan = NULL;
        return err;
    }

    err = i2s_channel_enable(s_rx_chan);
    if (err != ESP_OK) {
        i2s_del_channel(s_rx_chan);
        s_rx_chan = NULL;
        return err;
    }

    ESP_LOGI(TAG,
             "initialized: ws=%d bclk=%d data=%d sample_rate=%lu",
             s_config.ws_gpio,
             s_config.bclk_gpio,
             s_config.data_gpio,
             (unsigned long)s_config.sample_rate_hz);
    return ESP_OK;
}

esp_err_t inmp441_dual_read_raw_interleaved_s32(int32_t *samples,
                                                size_t frame_capacity,
                                                size_t *frames_read,
                                                uint32_t timeout_ms)
{
    ESP_RETURN_ON_FALSE(samples != NULL, ESP_ERR_INVALID_ARG, TAG, "samples is null");
    ESP_RETURN_ON_FALSE(frames_read != NULL, ESP_ERR_INVALID_ARG, TAG, "frames_read is null");
    ESP_RETURN_ON_FALSE(frame_capacity > 0, ESP_ERR_INVALID_ARG, TAG, "frame_capacity is zero");
    ESP_RETURN_ON_FALSE(s_rx_chan != NULL, ESP_ERR_INVALID_STATE, TAG, "driver is not initialized");

    size_t bytes_read = 0;
    const size_t read_size = frame_capacity * 2 * sizeof(samples[0]);
    ESP_RETURN_ON_ERROR(i2s_channel_read(s_rx_chan, samples, read_size, &bytes_read, timeout_ms),
                        TAG,
                        "i2s read failed");

    const size_t sample_count = bytes_read / sizeof(samples[0]);
    *frames_read = sample_count / 2;
    ESP_RETURN_ON_FALSE(*frames_read > 0, ESP_ERR_INVALID_SIZE, TAG, "no i2s frames read");
    return ESP_OK;
}

esp_err_t inmp441_dual_read_level(inmp441_dual_level_t *level, uint32_t timeout_ms)
{
    ESP_RETURN_ON_FALSE(level != NULL, ESP_ERR_INVALID_ARG, TAG, "level is null");
    ESP_RETURN_ON_FALSE(s_rx_chan != NULL, ESP_ERR_INVALID_STATE, TAG, "driver is not initialized");

    size_t frame_count = 0;
    ESP_RETURN_ON_ERROR(inmp441_dual_read_raw_interleaved_s32(s_samples,
                                                              s_config.read_frames,
                                                              &frame_count,
                                                              timeout_ms),
                        TAG,
                        "read raw samples failed");

    int64_t left_sum = 0;
    int64_t right_sum = 0;
    int32_t left_peak = 0;
    int32_t right_peak = 0;

    for (size_t frame = 0; frame < frame_count; ++frame) {
        // INMP441 provides 24 valid bits in a 32-bit I2S slot.
        int32_t left = s_samples[frame * 2] >> s_config.sample_shift_bits;
        int32_t right = s_samples[frame * 2 + 1] >> s_config.sample_shift_bits;

        int64_t left_abs = abs_i32(left);
        int64_t right_abs = abs_i32(right);

        left_sum += left_abs;
        right_sum += right_abs;

        if (left_abs > left_peak) {
            left_peak = (int32_t)left_abs;
        }
        if (right_abs > right_peak) {
            right_peak = (int32_t)right_abs;
        }
    }

    level->left_avg = (int32_t)(left_sum / frame_count);
    level->right_avg = (int32_t)(right_sum / frame_count);
    level->left_peak = left_peak;
    level->right_peak = right_peak;
    level->frames = (uint32_t)frame_count;
    return ESP_OK;
}

esp_err_t inmp441_dual_deinit(void)
{
    if (s_rx_chan == NULL) {
        return ESP_OK;
    }

    esp_err_t err = i2s_channel_disable(s_rx_chan);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "disable failed: %s", esp_err_to_name(err));
    }

    err = i2s_del_channel(s_rx_chan);
    s_rx_chan = NULL;

    if (s_samples != NULL) {
        free(s_samples);
        s_samples = NULL;
    }
    return err;
}
