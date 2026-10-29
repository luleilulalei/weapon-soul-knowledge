#include "app/mic_level_monitor.h"

#include "board/usaki_board.h"
#include "drivers/inmp441_dual.h"
#include "esp_err.h"
#include "esp_log.h"

static const char *TAG = "mic_monitor";

static mic_level_monitor_config_t s_monitor_config;

static const char *detect_direction(const inmp441_dual_level_t *level)
{
    const int32_t right_delta =
        level->right_avg / s_monitor_config.direction_delta_divisor + s_monitor_config.direction_delta_floor;
    const int32_t left_delta =
        level->left_avg / s_monitor_config.direction_delta_divisor + s_monitor_config.direction_delta_floor;

    if (level->left_avg > level->right_avg + right_delta) {
        return "left";
    }
    if (level->right_avg > level->left_avg + left_delta) {
        return "right";
    }
    return "center";
}

static bool has_sound(const inmp441_dual_level_t *level)
{
    return level->left_avg >= USAKI_MIC_SOUND_AVG_THRESHOLD ||
           level->right_avg >= USAKI_MIC_SOUND_AVG_THRESHOLD ||
           level->left_peak >= USAKI_MIC_SOUND_PEAK_THRESHOLD ||
           level->right_peak >= USAKI_MIC_SOUND_PEAK_THRESHOLD;
}

esp_err_t mic_level_monitor_init(const mic_level_monitor_config_t *config)
{
    if (config == NULL || config->direction_delta_divisor <= 0) {
        return ESP_ERR_INVALID_ARG;
    }

    s_monitor_config = *config;

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

    return inmp441_dual_init(&mic_config);
}

void mic_level_monitor_print_once(void)
{
    inmp441_dual_level_t level = {0};
    esp_err_t err = inmp441_dual_read_level(&level, s_monitor_config.read_timeout_ms);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "read level failed: %s", esp_err_to_name(err));
        return;
    }

    ESP_LOGI(TAG,
             "level: L avg=%ld peak=%ld | R avg=%ld peak=%ld | dir=%s | frames=%lu",
             (long)level.left_avg,
             (long)level.left_peak,
             (long)level.right_avg,
             (long)level.right_peak,
             detect_direction(&level),
             (unsigned long)level.frames);
}

void mic_level_monitor_log_if_sound(void)
{
    inmp441_dual_level_t level = {0};
    esp_err_t err = inmp441_dual_read_level(&level, s_monitor_config.read_timeout_ms);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "read level failed: %s", esp_err_to_name(err));
        return;
    }

    if (!has_sound(&level)) {
        return;
    }

    ESP_LOGI(TAG,
             "sound detected: L avg=%ld peak=%ld | R avg=%ld peak=%ld | dir=%s | frames=%lu",
             (long)level.left_avg,
             (long)level.left_peak,
             (long)level.right_avg,
             (long)level.right_peak,
             detect_direction(&level),
             (unsigned long)level.frames);
}
