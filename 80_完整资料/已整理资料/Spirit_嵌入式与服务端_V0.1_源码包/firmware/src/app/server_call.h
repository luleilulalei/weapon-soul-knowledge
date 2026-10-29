#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "app/protocol.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define USAKI_SERVER_CALL_DEFAULT_TX_BUFFER_BYTES 1024

typedef struct usaki_server_call usaki_server_call_t;
typedef usaki_server_call_t *usaki_server_call_handle_t;

typedef void (*usaki_server_call_connected_cb_t)(void *user_ctx);
typedef void (*usaki_server_call_disconnected_cb_t)(void *user_ctx);
typedef void (*usaki_server_call_text_cb_t)(const char *text, size_t len, void *user_ctx);
typedef void (*usaki_server_call_binary_cb_t)(const uint8_t *data, size_t len, void *user_ctx);
typedef void (*usaki_server_call_error_cb_t)(esp_err_t err, const char *message, void *user_ctx);
typedef void (*usaki_server_call_message_cb_t)(const usaki_protocol_server_message_t *message,
                                               void *user_ctx);

typedef struct
{
    usaki_server_call_connected_cb_t connected;
    usaki_server_call_disconnected_cb_t disconnected;
    usaki_server_call_text_cb_t unhandled_text;
    usaki_server_call_binary_cb_t binary;
    usaki_server_call_error_cb_t error;
    usaki_server_call_message_cb_t voice_output_start;
    usaki_server_call_message_cb_t voice_output_end;
    usaki_server_call_message_cb_t voice_output_cancel;
    usaki_server_call_message_cb_t emotion_update;
    usaki_server_call_message_cb_t eye_animation;
    usaki_server_call_message_cb_t body_action;
    usaki_server_call_message_cb_t motion_servo_batch;
    usaki_server_call_message_cb_t notification_push;
    usaki_server_call_message_cb_t server_error;
} usaki_server_call_callbacks_t;

typedef struct
{
    const char *uri;
    const char *connect_url;
    const char *device_id;
    const char *firmware_version;
    const char *hardware_version;
    int network_timeout_ms;
    int reconnect_timeout_ms;
    int send_timeout_ms;
    size_t tx_buffer_bytes;
    usaki_server_call_callbacks_t callbacks;
    void *user_ctx;
} usaki_server_call_config_t;

usaki_server_call_config_t usaki_server_call_default_config(void);

esp_err_t usaki_server_call_init(const usaki_server_call_config_t *config,
                                 usaki_server_call_handle_t *out);

esp_err_t usaki_server_call_start(usaki_server_call_handle_t handle);

esp_err_t usaki_server_call_stop(usaki_server_call_handle_t handle);

esp_err_t usaki_server_call_destroy(usaki_server_call_handle_t handle);

bool usaki_server_call_is_connected(usaki_server_call_handle_t handle);

int usaki_server_call_next_seq(usaki_server_call_handle_t handle);

esp_err_t usaki_server_call_send_voice_input_start(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_input_start_t *request);

esp_err_t usaki_server_call_send_voice_input_end(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_input_end_t *request);

esp_err_t usaki_server_call_send_voice_input_cancel(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_input_cancel_t *request);

esp_err_t usaki_server_call_send_voice_wake_detected(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_wake_detected_t *request);

esp_err_t usaki_server_call_send_voice_interrupt(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_interrupt_t *request);

esp_err_t usaki_server_call_send_touch_event(usaki_server_call_handle_t handle,
                                             const usaki_protocol_touch_event_t *request);

esp_err_t usaki_server_call_send_sensor_update(usaki_server_call_handle_t handle,
                                               const usaki_protocol_sensor_update_t *request);

esp_err_t usaki_server_call_send_error(usaki_server_call_handle_t handle,
                                       const usaki_protocol_error_t *request);

esp_err_t usaki_server_call_send_binary(usaki_server_call_handle_t handle,
                                        const uint8_t *data,
                                        size_t len);

esp_err_t usaki_server_call_handle_server_text(usaki_server_call_handle_t handle,
                                               const char *text,
                                               size_t len);

esp_err_t usaki_server_call_handle_server_binary(usaki_server_call_handle_t handle,
                                                 const uint8_t *data,
                                                 size_t len);

#ifdef __cplusplus
}
#endif
