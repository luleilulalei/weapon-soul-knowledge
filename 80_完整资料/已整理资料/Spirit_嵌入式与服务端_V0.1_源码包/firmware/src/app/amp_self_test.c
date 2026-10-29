#include "app/amp_self_test.h"

#include <stdint.h>

#include "board/usaki_board.h"
#include "drivers/max98357a.h"
#include "esp_check.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "amp_self_test";

static const int16_t SINE_32[32] = {
    0,      6393,   12539,  18204,  23170,  27245,  30273,  32137,
    32767,  32137,  30273,  27245,  23170,  18204,  12539,  6393,
    0,     -6393,  -12539, -18204, -23170, -27245, -30273, -32137,
    -32767, -32137, -30273, -27245, -23170, -18204, -12539, -6393,
};

static esp_err_t play_tone(max98357a_handle_t amp,
                           uint32_t frequency_hz,
                           uint32_t duration_ms,
                           int16_t amplitude)
{
    int16_t buffer[USAKI_AMP_TONE_FRAMES * 2];
    uint32_t phase = 0;
    const uint32_t phase_step = (frequency_hz * 32U * 65536U) / USAKI_AMP_SAMPLE_RATE_HZ;
    uint32_t frames_left = (USAKI_AMP_SAMPLE_RATE_HZ * duration_ms) / 1000U;

    while (frames_left > 0) {
        const uint32_t frames_now = frames_left > USAKI_AMP_TONE_FRAMES ? USAKI_AMP_TONE_FRAMES : frames_left;
        for (uint32_t i = 0; i < frames_now; ++i) {
            const uint32_t index = (phase >> 16) & 31U;
            const int16_t sample = (int16_t)((SINE_32[index] * (int32_t)amplitude) / 32767);
            buffer[i * 2] = sample;
            buffer[i * 2 + 1] = sample;
            phase += phase_step;
        }

        ESP_RETURN_ON_ERROR(max98357a_write_interleaved_i16(amp, buffer, frames_now * 2, 1000),
                            TAG,
                            "write tone failed");
        frames_left -= frames_now;
    }

    return max98357a_write_silence(amp, USAKI_AMP_SAMPLE_RATE_HZ / 20, 1000);
}

esp_err_t amp_self_test_play_startup_chime(void)
{
    const max98357a_config_t amp_config = {
        .i2s_port = USAKI_AMP_I2S_PORT,
        .bclk_gpio = USAKI_AMP_BCLK_GPIO,
        .ws_gpio = USAKI_AMP_LRC_GPIO,
        .data_gpio = USAKI_AMP_DIN_GPIO,
        .sample_rate_hz = USAKI_AMP_SAMPLE_RATE_HZ,
        .dma_desc_num = USAKI_AMP_DMA_DESC_NUM,
        .dma_frame_num = USAKI_AMP_DMA_FRAME_NUM,
    };

    max98357a_handle_t amp = NULL;
    ESP_RETURN_ON_ERROR(max98357a_create(&amp_config, &amp), TAG, "create amp failed");

    esp_err_t err = play_tone(amp, 523, 120, USAKI_AMP_TEST_AMPLITUDE);
    if (err == ESP_OK) {
        vTaskDelay(pdMS_TO_TICKS(80));
        err = play_tone(amp, 784, 160, USAKI_AMP_TEST_AMPLITUDE);
    }

    esp_err_t destroy_err = max98357a_destroy(amp);
    return err == ESP_OK ? destroy_err : err;
}
