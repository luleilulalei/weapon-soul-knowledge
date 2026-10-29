#include "app/audio_passthrough.h"

#include <stdint.h>
#include <stdio.h>

#include "board/usaki_board.h"
#include "drivers/inmp441_dual.h"
#include "drivers/max98357a.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "audio_passthrough";

static max98357a_handle_t s_amp;
static int32_t s_mic_samples[USAKI_AUDIO_PASSTHROUGH_FRAMES * 2];
static int16_t s_amp_samples[USAKI_AUDIO_PASSTHROUGH_FRAMES * 2];

static int16_t clamp_i16(int32_t value)
{
    if (value > INT16_MAX) {
        return INT16_MAX;
    }
    if (value < INT16_MIN) {
        return INT16_MIN;
    }
    return (int16_t)value;
}

static void convert_mic_to_amp_samples(size_t frames)
{
    for (size_t i = 0; i < frames * 2; ++i) {
        int32_t sample = s_mic_samples[i] >> USAKI_AUDIO_PASSTHROUGH_SHIFT_BITS;
        sample = (sample * USAKI_AUDIO_PASSTHROUGH_GAIN_NUMERATOR) /
                 USAKI_AUDIO_PASSTHROUGH_GAIN_DENOMINATOR;
        s_amp_samples[i] = clamp_i16(sample);
    }
}

esp_err_t audio_passthrough_init(void)
{
    const inmp441_dual_config_t mic_config = {
        .i2s_port = USAKI_MIC_I2S_PORT,
        .ws_gpio = USAKI_MIC_WS_GPIO,
        .bclk_gpio = USAKI_MIC_BCLK_GPIO,
        .data_gpio = USAKI_MIC_DATA_GPIO,
        .sample_rate_hz = USAKI_MIC_SAMPLE_RATE_HZ,
        .read_frames = USAKI_MIC_READ_FRAMES,
        .dma_desc_num = USAKI_MIC_DMA_DESC_NUM,
        .sample_shift_bits = USAKI_MIC_SAMPLE_SHIFT_BITS,
    };

    const max98357a_config_t amp_config = {
        .i2s_port = USAKI_AMP_I2S_PORT,
        .bclk_gpio = USAKI_AMP_BCLK_GPIO,
        .ws_gpio = USAKI_AMP_LRC_GPIO,
        .data_gpio = USAKI_AMP_DIN_GPIO,
        .sample_rate_hz = USAKI_AMP_SAMPLE_RATE_HZ,
        .dma_desc_num = USAKI_AMP_DMA_DESC_NUM,
        .dma_frame_num = USAKI_AMP_DMA_FRAME_NUM,
    };

    ESP_RETURN_ON_FALSE(USAKI_AUDIO_PASSTHROUGH_GAIN_DENOMINATOR > 0,
                        ESP_ERR_INVALID_ARG,
                        TAG,
                        "invalid gain denominator");

    ESP_RETURN_ON_ERROR(inmp441_dual_init(&mic_config), TAG, "mic init failed");
    ESP_RETURN_ON_ERROR(max98357a_create(&amp_config, &s_amp), TAG, "amp init failed");
    return ESP_OK;
}

void audio_passthrough_run(void)
{
    printf("Audio passthrough starts after %d ms...\n", USAKI_AUDIO_PASSTHROUGH_DELAY_MS);
    vTaskDelay(pdMS_TO_TICKS(USAKI_AUDIO_PASSTHROUGH_DELAY_MS));
    printf("Audio passthrough running. Keep speaker away from microphones to avoid feedback.\n");

    while (1) {
        size_t frames_read = 0;
        esp_err_t err = inmp441_dual_read_raw_interleaved_s32(s_mic_samples,
                                                              USAKI_AUDIO_PASSTHROUGH_FRAMES,
                                                              &frames_read,
                                                              USAKI_MIC_READ_TIMEOUT_MS);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "mic read failed: %s", esp_err_to_name(err));
            continue;
        }

        convert_mic_to_amp_samples(frames_read);
        err = max98357a_write_interleaved_i16(s_amp, s_amp_samples, frames_read * 2, 1000);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "amp write failed: %s", esp_err_to_name(err));
        }
    }
}
