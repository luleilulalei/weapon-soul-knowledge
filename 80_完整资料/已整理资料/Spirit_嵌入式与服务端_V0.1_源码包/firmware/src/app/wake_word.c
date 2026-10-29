#include "app/wake_word.h"

#include "board/usaki_board.h"
#include "drivers/inmp441_dual.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_wn_iface.h"
#include "esp_wn_models.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "model_path.h"

#include <stdbool.h>
#include <stdint.h>

static const char *TAG = "wake_word";
static const esp_wn_iface_t *s_wn_handle;
static model_iface_data_t *s_wn_data;
static const char *s_wn_model_name;
static bool s_starting;
static bool s_wake_reported;
static size_t s_wake_frames;
static int32_t s_raw_samples[USAKI_WAKE_WORD_RAW_FRAMES * 2];
static int16_t s_wn_samples[USAKI_WAKE_WORD_RAW_FRAMES];
static int64_t s_last_level_log_us;

typedef struct {
    int32_t left_avg;
    int32_t right_avg;
    int32_t left_peak;
    int32_t right_peak;
    const char *active_channel;
} wake_word_level_t;

esp_err_t wake_word_handle_detected(const char *wake_word)
{
    ESP_RETURN_ON_FALSE(wake_word != NULL, ESP_ERR_INVALID_ARG, TAG, "wake_word is null");

    ESP_LOGI(TAG, "wake word detected: %s", wake_word);
    return ESP_OK;
}

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

static int64_t abs_i32(int32_t value)
{
    return value < 0 ? -(int64_t)value : value;
}

static void convert_stereo_s32_to_mono_s16(size_t frames, wake_word_level_t *level)
{
    int64_t left_sum = 0;
    int64_t right_sum = 0;
    int32_t left_peak = 0;
    int32_t right_peak = 0;

    for (size_t i = 0; i < frames; ++i) {
        int32_t left = s_raw_samples[i * 2] >> USAKI_WAKE_WORD_SAMPLE_SHIFT_BITS;
        int32_t right = s_raw_samples[i * 2 + 1] >> USAKI_WAKE_WORD_SAMPLE_SHIFT_BITS;
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

    level->left_avg = (int32_t)(left_sum / frames);
    level->right_avg = (int32_t)(right_sum / frames);
    level->left_peak = left_peak;
    level->right_peak = right_peak;

    bool use_left = level->left_avg >= level->right_avg;
    level->active_channel = use_left ? "left" : "right";

    for (size_t i = 0; i < frames; ++i) {
        int32_t left = s_raw_samples[i * 2] >> USAKI_WAKE_WORD_SAMPLE_SHIFT_BITS;
        int32_t right = s_raw_samples[i * 2 + 1] >> USAKI_WAKE_WORD_SAMPLE_SHIFT_BITS;
        s_wn_samples[i] = clamp_i16(use_left ? left : right);
    }
}

static bool level_has_sound(const wake_word_level_t *level)
{
    return level->left_avg >= USAKI_WAKE_WORD_SOUND_AVG_THRESHOLD ||
           level->right_avg >= USAKI_WAKE_WORD_SOUND_AVG_THRESHOLD ||
           level->left_peak >= USAKI_WAKE_WORD_SOUND_PEAK_THRESHOLD ||
           level->right_peak >= USAKI_WAKE_WORD_SOUND_PEAK_THRESHOLD;
}

static void log_level_if_sound(const wake_word_level_t *level)
{
    if (!level_has_sound(level)) {
        return;
    }

    int64_t now_us = esp_timer_get_time();
    if (now_us - s_last_level_log_us < (int64_t)USAKI_WAKE_WORD_LEVEL_LOG_INTERVAL_MS * 1000) {
        return;
    }

    s_last_level_log_us = now_us;
    ESP_LOGI(TAG,
             "mic sound active=%s left_avg=%ld right_avg=%ld left_peak=%ld right_peak=%ld",
             level->active_channel,
             (long)level->left_avg,
             (long)level->right_avg,
             (long)level->left_peak,
             (long)level->right_peak);
}

static void wake_word_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "wake word task started, phrase=%s", USAKI_WAKE_WORD_NAME);

    while (1) {
        size_t frames_read = 0;
        esp_err_t err = inmp441_dual_read_raw_interleaved_s32(s_raw_samples,
                                                              USAKI_WAKE_WORD_RAW_FRAMES,
                                                              &frames_read,
                                                              USAKI_MIC_READ_TIMEOUT_MS);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "read mic failed: %s", esp_err_to_name(err));
            continue;
        }
        if (frames_read != s_wake_frames) {
            ESP_LOGW(TAG, "unexpected mic frame count: expected=%u actual=%u", (unsigned)s_wake_frames, (unsigned)frames_read);
            continue;
        }

        wake_word_level_t level = {0};
        convert_stereo_s32_to_mono_s16(frames_read, &level);
        log_level_if_sound(&level);

        wakenet_state_t result = s_wn_handle->detect(s_wn_data, s_wn_samples);
        if (result == WAKENET_DETECTED && !s_wake_reported) {
            ESP_LOGI(TAG,
                     "WakeNet detected wake word: phrase=%s model=%s active=%s left_avg=%ld right_avg=%ld",
                     USAKI_WAKE_WORD_NAME,
                     s_wn_model_name,
                     level.active_channel,
                     (long)level.left_avg,
                     (long)level.right_avg);
            s_wake_reported = true;
            (void)wake_word_handle_detected(USAKI_WAKE_WORD_NAME);
        } else if (result == WAKENET_NO_DETECT) {
            s_wake_reported = false;
        }
    }
}

static void log_heap_state(const char *label)
{
    ESP_LOGI(TAG,
             "%s heap: free internal=%u free psram=%u largest internal=%u largest psram=%u",
             label,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM));
}

static esp_err_t wake_word_engine_init(void)
{
    srmodel_list_t *models = esp_srmodel_init("model");
    if (models == NULL) {
        ESP_LOGE(TAG, "model partition init failed");
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "loaded %d speech model(s)", models->num);

    if (models->num == 0) {
        ESP_LOGE(TAG, "no speech model found");
        return ESP_FAIL;
    }

    char *model_name = USAKI_WAKE_WORD_MODEL_NAME;
    if (esp_srmodel_exists(models, model_name) < 0) {
        ESP_LOGW(TAG, "preferred WakeNet model not found: %s", model_name);
        model_name = esp_srmodel_filter(models, ESP_WN_PREFIX, NULL);
    }
    if (model_name == NULL) {
        ESP_LOGE(TAG, "no WakeNet model found");
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "selected WakeNet model: %s", model_name);
    s_wn_model_name = model_name;

    s_wn_handle = esp_wn_handle_from_name(model_name);
    if (s_wn_handle == NULL) {
        ESP_LOGE(TAG, "WakeNet handle not found");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "creating WakeNet model: %s", model_name);
    log_heap_state("before WakeNet create");
    s_wn_data = s_wn_handle->create(model_name, DET_MODE_90);
    log_heap_state("after WakeNet create");
    if (s_wn_data == NULL) {
        ESP_LOGE(TAG, "WakeNet create failed: %s", model_name);
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "WakeNet model created");

    int sample_chunks = s_wn_handle->get_samp_chunksize(s_wn_data);
    ESP_RETURN_ON_FALSE(sample_chunks > 0, ESP_FAIL, TAG, "invalid WakeNet sample chunk size: %d", sample_chunks);
    ESP_RETURN_ON_FALSE(sample_chunks <= USAKI_WAKE_WORD_RAW_FRAMES,
                        ESP_ERR_INVALID_SIZE,
                        TAG,
                        "WakeNet sample chunk size exceeds buffer: %d > %d",
                        sample_chunks,
                        USAKI_WAKE_WORD_RAW_FRAMES);
    s_wake_frames = (size_t)sample_chunks;
    ESP_LOGI(TAG, "WakeNet sample chunk size: %u", (unsigned)s_wake_frames);

    BaseType_t created = xTaskCreatePinnedToCore(wake_word_task,
                                                 "wake_word",
                                                 USAKI_WAKE_WORD_TASK_STACK_BYTES,
                                                 NULL,
                                                 USAKI_WAKE_WORD_TASK_PRIORITY,
                                                 NULL,
                                                 USAKI_WAKE_WORD_TASK_CORE);
    ESP_RETURN_ON_FALSE(created == pdPASS, ESP_FAIL, TAG, "create wake word task failed");
    return ESP_OK;
}

static void wake_word_init_task(void *arg)
{
    (void)arg;

    ESP_LOGI(TAG, "wake word init task started on core %d", xPortGetCoreID());
    esp_err_t err = wake_word_engine_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "wake word init failed: %s", esp_err_to_name(err));
    }

    vTaskDelete(NULL);
}

esp_err_t wake_word_engine_start(void)
{
    ESP_RETURN_ON_FALSE(!s_starting && s_wn_data == NULL, ESP_ERR_INVALID_STATE, TAG, "wake word already started");

    s_starting = true;
    BaseType_t created = xTaskCreatePinnedToCore(wake_word_init_task,
                                                 "wake_word_init",
                                                 USAKI_WAKE_WORD_TASK_STACK_BYTES,
                                                 NULL,
                                                 USAKI_WAKE_WORD_TASK_PRIORITY,
                                                 NULL,
                                                 USAKI_WAKE_WORD_TASK_CORE);
    if (created != pdPASS) {
        s_starting = false;
        ESP_LOGE(TAG, "create wake word init task failed");
        return ESP_FAIL;
    }

    return ESP_OK;
}
