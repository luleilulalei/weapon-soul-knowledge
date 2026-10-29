#include "app/motion_protocol_adapter.h"

#include "app/usaki_motion.h"
#include "board/usaki_board.h"
#include "esp_check.h"
#include "esp_log.h"

static const char *TAG = "motion_protocol_adapter";

UsakiMotionProtocolAdapter::~UsakiMotionProtocolAdapter()
{
    Stop();
}

esp_err_t UsakiMotionProtocolAdapter::Start()
{
    if (server_ != nullptr) {
        return ESP_OK;
    }

    usaki_server_call_config_t config = usaki_server_call_default_config();
    config.uri = USAKI_SERVER_MOTION_WS_URL;
    config.callbacks.connected = OnConnected;
    config.callbacks.disconnected = OnDisconnected;
    config.callbacks.motion_servo_batch = OnMotionServoBatch;
    config.callbacks.error = OnError;
    config.user_ctx = this;

    esp_err_t err = usaki_server_call_init(&config, &server_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "server_call init failed: %s", esp_err_to_name(err));
        return err;
    }

    err = usaki_server_call_start(server_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "server_call start failed: %s", esp_err_to_name(err));
        usaki_server_call_destroy(server_);
        server_ = nullptr;
        return err;
    }

    ESP_LOGI(TAG, "started: %s", USAKI_SERVER_MOTION_WS_URL);
    return ESP_OK;
}

void UsakiMotionProtocolAdapter::Stop()
{
    if (server_ != nullptr) {
        (void)usaki_server_call_stop(server_);
        (void)usaki_server_call_destroy(server_);
        server_ = nullptr;
    }
}

void UsakiMotionProtocolAdapter::SetCallbacks(const UsakiMotionProtocolAdapterCallbacks &callbacks)
{
    callbacks_ = callbacks;
}

void UsakiMotionProtocolAdapter::HandleConnected()
{
    ESP_LOGI(TAG, "motion websocket connected");
    if (callbacks_.on_connected) {
        callbacks_.on_connected();
    }
}

void UsakiMotionProtocolAdapter::HandleDisconnected()
{
    ESP_LOGW(TAG, "motion websocket disconnected");
    if (callbacks_.on_disconnected) {
        callbacks_.on_disconnected();
    }
}

void UsakiMotionProtocolAdapter::HandleMotionServoBatch(const usaki_protocol_server_message_t *message)
{
    if (message == nullptr || message->motion_servo_count <= 0) {
        ESP_LOGW(TAG, "ignore empty motion servo batch");
        return;
    }

    esp_err_t err = usaki_motion_apply_servo_batch(message);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "apply motion servo batch failed: %s", esp_err_to_name(err));
        if (callbacks_.on_error) {
            callbacks_.on_error(err, "apply motion servo batch failed");
        }
    }
}

void UsakiMotionProtocolAdapter::HandleError(esp_err_t err, const char *message)
{
    ESP_LOGW(TAG,
             "motion websocket error: %s (%s)",
             message != nullptr ? message : "",
             esp_err_to_name(err));
    if (callbacks_.on_error) {
        callbacks_.on_error(err, message);
    }
}

void UsakiMotionProtocolAdapter::OnConnected(void *user_ctx)
{
    static_cast<UsakiMotionProtocolAdapter *>(user_ctx)->HandleConnected();
}

void UsakiMotionProtocolAdapter::OnDisconnected(void *user_ctx)
{
    static_cast<UsakiMotionProtocolAdapter *>(user_ctx)->HandleDisconnected();
}

void UsakiMotionProtocolAdapter::OnMotionServoBatch(const usaki_protocol_server_message_t *message, void *user_ctx)
{
    static_cast<UsakiMotionProtocolAdapter *>(user_ctx)->HandleMotionServoBatch(message);
}

void UsakiMotionProtocolAdapter::OnError(esp_err_t err, const char *message, void *user_ctx)
{
    static_cast<UsakiMotionProtocolAdapter *>(user_ctx)->HandleError(err, message);
}
