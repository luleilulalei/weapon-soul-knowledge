#pragma once

#include <functional>

#include "app/protocol.h"
#include "app/server_call.h"
#include "esp_err.h"

struct UsakiMotionProtocolAdapterCallbacks {
    std::function<void(void)> on_connected;
    std::function<void(void)> on_disconnected;
    std::function<void(esp_err_t err, const char *message)> on_error;
};

class UsakiMotionProtocolAdapter {
public:
    UsakiMotionProtocolAdapter() = default;
    ~UsakiMotionProtocolAdapter();

    esp_err_t Start();
    void Stop();
    void SetCallbacks(const UsakiMotionProtocolAdapterCallbacks &callbacks);

private:
    UsakiMotionProtocolAdapterCallbacks callbacks_;
    usaki_server_call_handle_t server_ = nullptr;

    void HandleConnected();
    void HandleDisconnected();
    void HandleMotionServoBatch(const usaki_protocol_server_message_t *message);
    void HandleError(esp_err_t err, const char *message);

    static void OnConnected(void *user_ctx);
    static void OnDisconnected(void *user_ctx);
    static void OnMotionServoBatch(const usaki_protocol_server_message_t *message, void *user_ctx);
    static void OnError(esp_err_t err, const char *message, void *user_ctx);
};
