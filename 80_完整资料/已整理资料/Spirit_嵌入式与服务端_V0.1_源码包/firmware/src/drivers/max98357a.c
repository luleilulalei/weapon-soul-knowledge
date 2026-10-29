#include "drivers/max98357a.h"

#include <stdlib.h>

#include "driver/i2s_common.h"
#include "driver/i2s_std.h"
#include "esp_check.h"
#include "esp_log.h"

static const char *TAG = "max98357a";

struct max98357a {
    i2s_chan_handle_t tx_chan;
    max98357a_config_t config;
};

esp_err_t max98357a_create(const max98357a_config_t *config, max98357a_handle_t *out_handle)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG, "config is null");
    ESP_RETURN_ON_FALSE(out_handle != NULL, ESP_ERR_INVALID_ARG, TAG, "out_handle is null");
    ESP_RETURN_ON_FALSE(config->sample_rate_hz > 0, ESP_ERR_INVALID_ARG, TAG, "sample_rate_hz is zero");
    ESP_RETURN_ON_FALSE(config->dma_desc_num > 0, ESP_ERR_INVALID_ARG, TAG, "dma_desc_num is zero");
    ESP_RETURN_ON_FALSE(config->dma_frame_num > 0, ESP_ERR_INVALID_ARG, TAG, "dma_frame_num is zero");

    max98357a_handle_t handle = calloc(1, sizeof(*handle));
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_NO_MEM, TAG, "alloc handle failed");
    handle->config = *config;

    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(handle->config.i2s_port, I2S_ROLE_MASTER);
    chan_cfg.auto_clear = true; // Silence on underrun, never repeat stale DMA audio.
    chan_cfg.dma_desc_num = handle->config.dma_desc_num;
    chan_cfg.dma_frame_num = handle->config.dma_frame_num;

    esp_err_t err = i2s_new_channel(&chan_cfg, &handle->tx_chan, NULL);
    if (err != ESP_OK) {
        free(handle);
        return err;
    }

    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(handle->config.sample_rate_hz),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = handle->config.bclk_gpio,
            .ws = handle->config.ws_gpio,
            .dout = handle->config.data_gpio,
            .din = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false,
            },
        },
    };

    err = i2s_channel_init_std_mode(handle->tx_chan, &std_cfg);
    if (err != ESP_OK) {
        i2s_del_channel(handle->tx_chan);
        free(handle);
        return err;
    }

    err = i2s_channel_enable(handle->tx_chan);
    if (err != ESP_OK) {
        i2s_del_channel(handle->tx_chan);
        free(handle);
        return err;
    }

    *out_handle = handle;
    ESP_LOGI(TAG,
             "initialized: bclk=%d ws=%d data=%d sample_rate=%lu",
             handle->config.bclk_gpio,
             handle->config.ws_gpio,
             handle->config.data_gpio,
             (unsigned long)handle->config.sample_rate_hz);
    return ESP_OK;
}

esp_err_t max98357a_write_interleaved_i16(max98357a_handle_t handle,
                                          const int16_t *samples,
                                          size_t sample_count,
                                          uint32_t timeout_ms)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(samples != NULL, ESP_ERR_INVALID_ARG, TAG, "samples is null");
    ESP_RETURN_ON_FALSE(sample_count > 0, ESP_ERR_INVALID_ARG, TAG, "sample_count is zero");

    size_t bytes_written = 0;
    const size_t bytes_to_write = sample_count * sizeof(samples[0]);
    return i2s_channel_write(handle->tx_chan, samples, bytes_to_write, &bytes_written, timeout_ms);
}

esp_err_t max98357a_write_silence(max98357a_handle_t handle, size_t frame_count, uint32_t timeout_ms)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");

    int16_t silence[64 * 2] = {0};
    while (frame_count > 0) {
        const size_t frames_now = frame_count > 64 ? 64 : frame_count;
        ESP_RETURN_ON_ERROR(max98357a_write_interleaved_i16(handle, silence, frames_now * 2, timeout_ms),
                            TAG,
                            "write silence failed");
        frame_count -= frames_now;
    }
    return ESP_OK;
}

esp_err_t max98357a_destroy(max98357a_handle_t handle)
{
    if (handle == NULL) {
        return ESP_OK;
    }

    esp_err_t err = i2s_channel_disable(handle->tx_chan);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "disable failed: %s", esp_err_to_name(err));
    }

    err = i2s_del_channel(handle->tx_chan);
    free(handle);
    return err;
}
