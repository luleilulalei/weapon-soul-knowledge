#include "app/motion_runtime.h"

#include <memory>

#include "app/motion_protocol_adapter.h"
#include "esp_log.h"

static const char *TAG = "motion_runtime";

static std::unique_ptr<UsakiMotionProtocolAdapter> s_motion_adapter;

static void on_motion_connected()
{
    ESP_LOGI(TAG, "motion runtime connected");
}

static void on_motion_disconnected()
{
    ESP_LOGW(TAG, "motion runtime disconnected");
}

static void on_motion_error(esp_err_t err, const char *message)
{
    ESP_LOGW(TAG,
             "motion runtime error: %s (%s)",
             message != nullptr ? message : "",
             esp_err_to_name(err));
}

esp_err_t motion_runtime_init(void)
{
    if (s_motion_adapter != nullptr) {
        return ESP_OK;
    }

    s_motion_adapter = std::make_unique<UsakiMotionProtocolAdapter>();
    UsakiMotionProtocolAdapterCallbacks callbacks = {};
    callbacks.on_connected = on_motion_connected;
    callbacks.on_disconnected = on_motion_disconnected;
    callbacks.on_error = on_motion_error;
    s_motion_adapter->SetCallbacks(callbacks);

    esp_err_t err = s_motion_adapter->Start();
    if (err != ESP_OK) {
        s_motion_adapter.reset();
        ESP_LOGW(TAG, "motion runtime start failed: %s", esp_err_to_name(err));
        return err;
    }

    ESP_LOGI(TAG, "motion runtime initialized");
    return ESP_OK;
}
