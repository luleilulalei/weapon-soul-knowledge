#include "app/robot.h"
#include "app/voice_runtime.h"
#include "app/spirit_privacy.h"
#include "app/spirit_link.h"
#include "app/wifi_station.h"
#include "board/usaki_board.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ui/usaki_eyes.h"
#include "spirit_peripherals/spirit_peripherals.h"
#include <cstring>
#include <string>
static const char *TAG = "spirit";
static bool started;
static void key_task(void *)
{
    // Active low, 30ms stable debounce; 1.5s hold toggles persistent privacy.
    bool down = false, held = false;
    unsigned stable = 0;
    int last = 1;
    TickType_t pressed = 0;
    while (true) {
        int level = gpio_get_level(SPIRIT_KEY_GPIO);
        if (level == last) ++stable; else { stable = 0; last = level; }
        if (stable >= 3) {
            if (!level && !down) { down = true; held = false; pressed = xTaskGetTickCount(); }
            if (down && !level && !held && xTaskGetTickCount() - pressed >= pdMS_TO_TICKS(1500)) {
                held = true;
                esp_err_t err = voice_runtime_set_privacy_mute(!spirit_privacy_muted());
                ESP_LOGI(TAG, "Software microphone privacy: %s (%s)", spirit_privacy_muted() ? "MUTED" : "unmuted", esp_err_to_name(err));
                usaki_eyes_set_emotion(spirit_privacy_muted() ? USAKI_EYE_EMOTION_SLEEPY : USAKI_EYE_EMOTION_IDLE);
            }
            if (level && down) {
                down = false;
                if (!held && !spirit_privacy_muted()) {
                    const auto state = voice_runtime_get_state();
                    if (state == USAKI_VOICE_RUNTIME_STATE_LISTENING) (void)voice_runtime_stop_listening();
                    else if (state == USAKI_VOICE_RUNTIME_STATE_SPEAKING) (void)voice_runtime_interrupt();
                    else (void)voice_runtime_start_listening();
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
static void peripheral_ui_task(void *)
{
    uint8_t previous_touch = 0;
    bool previous_dock = false;
    while (true) {
        spirit_peripherals_status_t status = {};
        if (spirit_peripherals_get_status(&status) == ESP_OK) {
            if (status.touch_valid) {
                if (status.touch_mask & ~previous_touch) {
                    usaki_eyes_blink();
                    // Touch is local feedback only: it never unmutes or uploads.
                    ESP_LOGI(TAG, "CAP1296 touch mask=0x%02x", status.touch_mask);
                }
                previous_touch = status.touch_mask;
            }
            if (status.expander_valid && status.docked != previous_dock) {
                previous_dock = status.docked;
                ESP_LOGI(TAG, "dock=%d charging=%d power_good=%d", status.docked, status.charging, status.power_good);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}
static void voice_task(void *)
{
    // Offline local UI/peripherals continue when credentials are not configured.
    if (USAKI_WIFI_SSID[0] == '\0') {
        ESP_LOGW(TAG, "Offline: configure Spirit Wi-Fi and server URLs in menuconfig");
        vTaskDelete(nullptr); return;
    }
    esp_err_t err = wifi_station_connect();
    if (err == ESP_OK) {
        esp_err_t link_err = spirit_link_start();
        if (link_err != ESP_OK) ESP_LOGW(TAG, "Spirit telemetry unavailable: %s", esp_err_to_name(link_err));
        if (std::string(USAKI_SERVER_VOICE_WS_URL).find("example.invalid") != std::string::npos) { vTaskDelete(nullptr); return; }
        err = voice_runtime_init();
    }
    if (err == ESP_OK) voice_runtime_run();
    ESP_LOGE(TAG, "Voice unavailable: %s (local UI remains active)", esp_err_to_name(err));
    vTaskDelete(nullptr);
}
esp_err_t start_robot(void)
{
    if (started) return ESP_OK;
    // Do not auto-erase NVS: it contains the user's privacy preference.
    esp_err_t err = nvs_flash_init();
    if (err != ESP_OK) return err;
    err = spirit_privacy_init();
    if (err != ESP_OK) return err;
    gpio_config_t cfg = {};
    cfg.pin_bit_mask = (1ULL << SPIRIT_LCD_BL_GPIO) | (1ULL << SPIRIT_AMP_EN_GPIO);
    cfg.mode = GPIO_MODE_OUTPUT;
    err = gpio_config(&cfg); if (err != ESP_OK) return err;
    gpio_set_level(SPIRIT_AMP_EN_GPIO, 0);
    gpio_set_level(SPIRIT_LCD_BL_GPIO, 0);
    err = usaki_eyes_start(); if (err != ESP_OK) return err;
    gpio_set_level(SPIRIT_LCD_BL_GPIO, 1);
    esp_err_t peripheral_err = spirit_peripherals_init();
    if (peripheral_err == ESP_OK) peripheral_err = spirit_peripherals_start();
    if (peripheral_err != ESP_OK) ESP_LOGW(TAG, "peripherals degraded: %s", esp_err_to_name(peripheral_err));
    else if (xTaskCreate(peripheral_ui_task, "peripheral_ui", 3072, nullptr, 3, nullptr) != pdPASS)
        ESP_LOGW(TAG, "peripheral UI task unavailable");
    usaki_eyes_set_emotion(USAKI_EYE_EMOTION_IDLE);
    cfg = {};
    cfg.pin_bit_mask = 1ULL << SPIRIT_KEY_GPIO;
    cfg.mode = GPIO_MODE_INPUT;
    cfg.pull_up_en = GPIO_PULLUP_ENABLE;
    err = gpio_config(&cfg); if (err != ESP_OK) return err;
    if (xTaskCreate(key_task, "spirit_key", 4096, nullptr, 4, nullptr) != pdPASS) return ESP_ERR_NO_MEM;
    if (xTaskCreate(voice_task, "voice_runtime", USAKI_VOICE_RUNTIME_TASK_STACK_BYTES, nullptr,
                    USAKI_VOICE_RUNTIME_TASK_PRIORITY, nullptr) != pdPASS) return ESP_ERR_NO_MEM;
    started = true;
    ESP_LOGI(TAG, "Spirit v0.1: single display/PDM; software privacy %s", spirit_privacy_muted() ? "MUTED" : "unmuted");
    return ESP_OK;
}
