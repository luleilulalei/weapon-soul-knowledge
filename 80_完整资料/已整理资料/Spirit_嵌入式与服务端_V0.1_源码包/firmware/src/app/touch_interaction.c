#include "app/touch_interaction.h"

#include <stdbool.h>
#include <stdint.h>

#include "app/voice_runtime.h"
#include "board/usaki_board.h"
#include "drivers/mpr121.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ui/usaki_eyes.h"

static const char *TAG = "touch_interaction";

#define TOUCH_INTERACTION_TASK_STACK_BYTES 4096
#define TOUCH_INTERACTION_TASK_PRIORITY 4
#define TOUCH_INTERACTION_TASK_CORE 0
#define TOUCH_INTERACTION_POLL_MS 50
#define TOUCH_INTERACTION_SETTLE_MS 1200
#define TOUCH_INTERACTION_SLEEPY_MS 9000
#define TOUCH_INTERACTION_HEART_MS 10000

static bool s_started;

static void handle_pressed_mask(uint16_t pressed_mask)
{
    if ((pressed_mask & (1U << 0)) != 0) {
        ESP_LOGI(TAG, "touch ELE0: sleepy eyes + sleepy sound");
        if (!usaki_eyes_set_emotion_name_for("sleepy", TOUCH_INTERACTION_SLEEPY_MS)) {
            ESP_LOGW(TAG, "queue sleepy emotion failed");
        }
        esp_err_t err = voice_runtime_play_sleepy_sound();
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "play sleepy sound failed: %s", esp_err_to_name(err));
        }
    }

    if ((pressed_mask & (1U << 1)) != 0) {
        ESP_LOGI(TAG, "touch ELE1: heart eyes");
        if (!usaki_eyes_set_emotion_name_for("heart", TOUCH_INTERACTION_HEART_MS)) {
            ESP_LOGW(TAG, "queue heart emotion failed");
        }
    }
}

static void touch_interaction_task(void *arg)
{
    (void)arg;

    const mpr121_config_t config = {
        .i2c_port = USAKI_TOUCH_I2C_PORT,
        .sda_gpio = USAKI_TOUCH_I2C_SDA_GPIO,
        .scl_gpio = USAKI_TOUCH_I2C_SCL_GPIO,
        .i2c_freq_hz = USAKI_TOUCH_I2C_FREQ_HZ,
        .i2c_addr = USAKI_TOUCH_I2C_ADDR,
    };

    mpr121_handle_t touch = NULL;
    esp_err_t err = mpr121_create(&config, &touch);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "mpr121 init failed: %s", esp_err_to_name(err));
        s_started = false;
        vTaskDelete(NULL);
        return;
    }

    vTaskDelay(pdMS_TO_TICKS(TOUCH_INTERACTION_SETTLE_MS));

    uint16_t last_mask = 0;
    err = mpr121_read_touched(touch, &last_mask);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "initial touch read failed: %s", esp_err_to_name(err));
        last_mask = 0;
    }

    ESP_LOGI(TAG, "touch interaction started: ELE0=sleepy ELE1=heart");

    while (true) {
        uint16_t touched_mask = 0;
        err = mpr121_read_touched(touch, &touched_mask);
        if (err == ESP_OK) {
            const uint16_t pressed_mask = (uint16_t)(touched_mask & ~last_mask);
            handle_pressed_mask(pressed_mask);
            last_mask = touched_mask;
        } else {
            ESP_LOGW(TAG, "read touched failed: %s", esp_err_to_name(err));
        }

        vTaskDelay(pdMS_TO_TICKS(TOUCH_INTERACTION_POLL_MS));
    }
}

esp_err_t usaki_touch_interaction_start(void)
{
    if (s_started) {
        return ESP_OK;
    }

    BaseType_t ok = xTaskCreatePinnedToCore(touch_interaction_task,
                                            "touch_interaction",
                                            TOUCH_INTERACTION_TASK_STACK_BYTES,
                                            NULL,
                                            TOUCH_INTERACTION_TASK_PRIORITY,
                                            NULL,
                                            TOUCH_INTERACTION_TASK_CORE);
    if (ok != pdPASS) {
        return ESP_ERR_NO_MEM;
    }

    s_started = true;
    return ESP_OK;
}
