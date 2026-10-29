#include "esp_crt_bundle.h"
#include "app/server_call.h"

#include <stdlib.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>

#include "board/usaki_board.h"
#include "esp_check.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_websocket_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "esp_heap_caps.h"

static const char *TAG = "server_call";

#ifndef USAKI_SERVER_DEVICE_CONNECT_URL
#define USAKI_SERVER_DEVICE_CONNECT_URL "http://example.invalid/api/v1/device/connect"
#endif

#ifndef USAKI_HARDWARE_VERSION
#define USAKI_HARDWARE_VERSION "esp32s3-n16r8"
#endif

// WebSocket dispatch runs under the library client lock. Never invoke protocol
// callbacks there: they can take adapter control locks and send back to the WS.
// Fixed pool bounds callback memory and allows non-blocking ownership transfer.
#define RX_EVENT_COUNT 8
#define RX_EVENT_BYTES USAKI_SERVER_CALL_WEBSOCKET_BUFFER_BYTES
#define RX_PAYLOAD_LIMIT (16 * 1024)
typedef struct {
    int32_t id;
    uint32_t session;
    esp_websocket_event_data_t event;
    char bytes[RX_EVENT_BYTES];
} queued_ws_event_t;

struct usaki_server_call
{
    esp_websocket_client_handle_t ws;
    usaki_server_call_config_t config;
    char *tx_buffer;
    char token[128];
    char ws_uri[320];
    uint8_t *rx_binary_buffer;
    size_t tx_buffer_bytes;
    size_t rx_binary_buffer_bytes;
    size_t rx_binary_expected_len;
    size_t rx_binary_received_len;
    _Atomic bool connected;
    _Atomic bool event_stopping;
    _Atomic bool event_overflow;
    _Atomic uint32_t event_session;
    QueueHandle_t event_free, event_ready;
    SemaphoreHandle_t event_exited;
    TaskHandle_t event_task;
    queued_ws_event_t *event_pool;
    int seq;
};

typedef esp_err_t (*server_call_dispatch_fn_t)(usaki_server_call_handle_t handle,
                                               const usaki_protocol_server_message_t *message);

typedef struct
{
    usaki_protocol_server_message_type_t type;
    server_call_dispatch_fn_t dispatch;
} server_call_dispatch_entry_t;

static esp_err_t dispatch_voice_output_start(usaki_server_call_handle_t handle,
                                             const usaki_protocol_server_message_t *message);
static esp_err_t dispatch_voice_output_end(usaki_server_call_handle_t handle,
                                           const usaki_protocol_server_message_t *message);
static esp_err_t dispatch_voice_output_cancel(usaki_server_call_handle_t handle,
                                              const usaki_protocol_server_message_t *message);
static esp_err_t dispatch_emotion_update(usaki_server_call_handle_t handle,
                                         const usaki_protocol_server_message_t *message);
static esp_err_t dispatch_eye_animation(usaki_server_call_handle_t handle,
                                        const usaki_protocol_server_message_t *message);
static esp_err_t dispatch_body_action(usaki_server_call_handle_t handle,
                                      const usaki_protocol_server_message_t *message);
static esp_err_t dispatch_motion_servo_batch(usaki_server_call_handle_t handle,
                                             const usaki_protocol_server_message_t *message);
static esp_err_t dispatch_notification_push(usaki_server_call_handle_t handle,
                                            const usaki_protocol_server_message_t *message);
static esp_err_t dispatch_server_error(usaki_server_call_handle_t handle,
                                       const usaki_protocol_server_message_t *message);

static const server_call_dispatch_entry_t SERVER_MESSAGE_DISPATCH[] = {
    {USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_START, dispatch_voice_output_start},
    {USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_END, dispatch_voice_output_end},
    {USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_CANCEL, dispatch_voice_output_cancel},
    {USAKI_PROTOCOL_SERVER_MESSAGE_EMOTION_UPDATE, dispatch_emotion_update},
    {USAKI_PROTOCOL_SERVER_MESSAGE_EYE_ANIMATION, dispatch_eye_animation},
    {USAKI_PROTOCOL_SERVER_MESSAGE_BODY_ACTION, dispatch_body_action},
    {USAKI_PROTOCOL_SERVER_MESSAGE_MOTION_SERVO_BATCH, dispatch_motion_servo_batch},
    {USAKI_PROTOCOL_SERVER_MESSAGE_NOTIFICATION_PUSH, dispatch_notification_push},
    {USAKI_PROTOCOL_SERVER_MESSAGE_ERROR, dispatch_server_error},
};

usaki_server_call_config_t usaki_server_call_default_config(void)
{
    return (usaki_server_call_config_t){
        .uri = USAKI_SERVER_VOICE_WS_URL,
        .connect_url = USAKI_SERVER_DEVICE_CONNECT_URL,
        .device_id = USAKI_DEVICE_ID,
        .firmware_version = USAKI_FIRMWARE_VERSION,
        .hardware_version = USAKI_HARDWARE_VERSION,
        .network_timeout_ms = USAKI_VOICE_CLIENT_WEBSOCKET_TIMEOUT_MS,
        .reconnect_timeout_ms = USAKI_VOICE_CLIENT_RECONNECT_TIMEOUT_MS,
        .send_timeout_ms = USAKI_VOICE_CLIENT_UPLOAD_TIMEOUT_MS,
        .tx_buffer_bytes = USAKI_SERVER_CALL_DEFAULT_TX_BUFFER_BYTES,
    };
}

static const char *config_string_or_default(const char *value, const char *default_value)
{
    return value != NULL ? value : default_value;
}

static void report_error(usaki_server_call_handle_t handle, esp_err_t err, const char *message)
{
    ESP_LOGW(TAG, "%s: %s", message, esp_err_to_name(err));
    if (handle != NULL && handle->config.callbacks.error != NULL)
    {
        handle->config.callbacks.error(err, message, handle->config.user_ctx);
    }
}

static void reset_rx_binary_fragment(usaki_server_call_handle_t handle)
{
    if (handle == NULL)
    {
        return;
    }
    handle->rx_binary_expected_len = 0;
    handle->rx_binary_received_len = 0;
}

static esp_err_t handle_server_binary_event(usaki_server_call_handle_t handle,
                                            const esp_websocket_event_data_t *event)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(event != NULL, ESP_ERR_INVALID_ARG, TAG, "event is null");
    ESP_RETURN_ON_FALSE(event->data_ptr != NULL || event->data_len == 0,
                        ESP_ERR_INVALID_ARG,
                        TAG,
                        "binary data is null");

    const size_t data_len = event->data_len > 0 ? (size_t)event->data_len : 0;
    const size_t payload_len = event->payload_len > 0 ? (size_t)event->payload_len : data_len;
    const size_t payload_offset = event->payload_offset > 0 ? (size_t)event->payload_offset : 0;

    if (payload_offset == 0 && data_len == payload_len)
    {
        reset_rx_binary_fragment(handle);
        return usaki_server_call_handle_server_binary(handle,
                                                      (const uint8_t *)event->data_ptr,
                                                      data_len);
    }

    ESP_RETURN_ON_FALSE(payload_len > 0,
                        ESP_ERR_INVALID_SIZE,
                        TAG,
                        "invalid fragmented binary payload length");
    if (payload_offset > payload_len || data_len > payload_len - payload_offset)
    {
        reset_rx_binary_fragment(handle);
        ESP_LOGW(TAG,
                 "invalid binary fragment: offset=%u len=%u payload=%u",
                 (unsigned)payload_offset,
                 (unsigned)data_len,
                 (unsigned)payload_len);
        return ESP_ERR_INVALID_SIZE;
    }

    if (handle->rx_binary_buffer_bytes < payload_len)
    {
        uint8_t *buffer = (uint8_t *)realloc(handle->rx_binary_buffer, payload_len);
        if (buffer == NULL)
        {
            reset_rx_binary_fragment(handle);
            return ESP_ERR_NO_MEM;
        }
        handle->rx_binary_buffer = buffer;
        handle->rx_binary_buffer_bytes = payload_len;
    }

    if (payload_offset == 0)
    {
        handle->rx_binary_expected_len = payload_len;
        handle->rx_binary_received_len = 0;
    }
    else if (handle->rx_binary_expected_len != payload_len ||
             handle->rx_binary_received_len != payload_offset)
    {
        ESP_LOGW(TAG,
                 "drop out-of-order binary fragment: offset=%u received=%u expected=%u payload=%u",
                 (unsigned)payload_offset,
                 (unsigned)handle->rx_binary_received_len,
                 (unsigned)handle->rx_binary_expected_len,
                 (unsigned)payload_len);
        reset_rx_binary_fragment(handle);
        return ESP_ERR_INVALID_STATE;
    }

    if (data_len > 0)
    {
        memcpy(handle->rx_binary_buffer + payload_offset, event->data_ptr, data_len);
    }
    handle->rx_binary_received_len = payload_offset + data_len;

    if (handle->rx_binary_received_len < handle->rx_binary_expected_len)
    {
        ESP_LOGD(TAG,
                 "buffer binary fragment: offset=%u len=%u payload=%u",
                 (unsigned)payload_offset,
                 (unsigned)data_len,
                 (unsigned)payload_len);
        return ESP_OK;
    }

    esp_err_t err = usaki_server_call_handle_server_binary(handle,
                                                           handle->rx_binary_buffer,
                                                           handle->rx_binary_expected_len);
    reset_rx_binary_fragment(handle);
    return err;
}

typedef struct
{
    char *buffer;
    int capacity;
    int length;
} http_response_buffer_t;

static esp_err_t http_event_handler(esp_http_client_event_t *event)
{
    if (event->event_id != HTTP_EVENT_ON_DATA || event->user_data == NULL)
    {
        return ESP_OK;
    }

    http_response_buffer_t *response = (http_response_buffer_t *)event->user_data;
    if (response->length >= response->capacity - 1)
    {
        return ESP_OK;
    }

    int copy_len = event->data_len;
    int remaining = response->capacity - response->length - 1;
    if (copy_len > remaining)
    {
        copy_len = remaining;
    }

    memcpy(response->buffer + response->length, event->data, copy_len);
    response->length += copy_len;
    response->buffer[response->length] = '\0';
    return ESP_OK;
}

static esp_err_t build_ws_uri_with_auth(usaki_server_call_handle_t handle)
{
    const char *separator = strchr(handle->config.uri, '?') == NULL ? "?" : "&";
    int written = snprintf(handle->ws_uri,
                           sizeof(handle->ws_uri),
                           "%s%sdevice_id=%s&token=%s",
                           handle->config.uri,
                           separator,
                           handle->config.device_id,
                           handle->token);
    ESP_RETURN_ON_FALSE(written > 0 && written < (int)sizeof(handle->ws_uri),
                        ESP_ERR_INVALID_SIZE,
                        TAG,
                        "websocket uri overflow");
    return ESP_OK;
}

static esp_err_t connect_device(usaki_server_call_handle_t handle)
{
    ESP_RETURN_ON_FALSE(handle->config.connect_url != NULL,
                        ESP_ERR_INVALID_ARG,
                        TAG,
                        "connect_url is null");

    usaki_protocol_device_connect_request_t request =
        usaki_protocol_device_connect_request_default();
    request.device_id = handle->config.device_id;
    request.firmware_version = handle->config.firmware_version;
    request.hardware_version = handle->config.hardware_version;

    esp_err_t err = usaki_protocol_build_device_connect_request(
        &request,
        handle->tx_buffer,
        handle->tx_buffer_bytes);
    ESP_RETURN_ON_ERROR(err, TAG, "build device connect request failed");

    char response_body[512] = {0};
    http_response_buffer_t response = {
        .buffer = response_body,
        .capacity = sizeof(response_body),
        .length = 0,
    };

    esp_http_client_config_t config = {
        .crt_bundle_attach = esp_crt_bundle_attach,
        .url = handle->config.connect_url,
        .method = HTTP_METHOD_POST,
        .timeout_ms = handle->config.network_timeout_ms,
        .event_handler = http_event_handler,
        .user_data = &response,
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    ESP_RETURN_ON_FALSE(client != NULL, ESP_FAIL, TAG, "http client init failed");

    ESP_LOGI(TAG, "connecting device: %s", handle->config.connect_url);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, handle->tx_buffer, strlen(handle->tx_buffer));

    err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    if (err == ESP_OK && status >= 200 && status < 300)
    {
        usaki_protocol_device_connect_response_t connect_response = {0};
        err = usaki_protocol_parse_device_connect_response(response.buffer,
                                                           (size_t)response.length,
                                                           &connect_response);
        if (err == ESP_OK)
        {
            strlcpy(handle->token, connect_response.token, sizeof(handle->token));
            ESP_LOGI(TAG,
                     "device connected, config_version=%d",
                     connect_response.config_version);
        }
    }
    else if (err == ESP_OK)
    {
        ESP_LOGW(TAG, "device connect failed, status=%d", status);
        err = ESP_FAIL;
    }
    else
    {
        ESP_LOGW(TAG, "device connect request failed: %s", esp_err_to_name(err));
    }

    esp_http_client_cleanup(client);
    return err;
}

static void process_websocket_event(void *handler_args,
                                    esp_event_base_t base,
                                    int32_t event_id,
                                    void *event_data)
{
    (void)base;

    usaki_server_call_handle_t handle = (usaki_server_call_handle_t)handler_args;
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;
    if (handle == NULL)
    {
        return;
    }

    switch (event_id)
    {
    case WEBSOCKET_EVENT_CONNECTED:
        handle->connected = true;
        ESP_LOGI(TAG, "websocket connected"); // URI may contain a bearer token.
        if (handle->config.callbacks.connected != NULL)
        {
            handle->config.callbacks.connected(handle->config.user_ctx);
        }
        break;

    case WEBSOCKET_EVENT_DISCONNECTED:
        handle->connected = false;
        ESP_LOGW(TAG, "websocket disconnected");
        if (handle->config.callbacks.disconnected != NULL)
        {
            handle->config.callbacks.disconnected(handle->config.user_ctx);
        }
        break;

    case WEBSOCKET_EVENT_DATA:
        if (data->op_code == 0x1)
        {
            esp_err_t err = usaki_server_call_handle_server_text(
                handle,
                data->data_ptr,
                (size_t)data->data_len);
            if (err != ESP_OK)
            {
                report_error(handle, err, "handle server text failed");
            }
        }
        else if (data->op_code == 0x2 ||
                 (data->op_code == 0x0 && handle->rx_binary_expected_len > 0))
        {
            esp_err_t err = handle_server_binary_event(handle, data);
            if (err != ESP_OK)
            {
                report_error(handle, err, "handle server binary failed");
            }
        }
        break;

    case WEBSOCKET_EVENT_ERROR:
        handle->connected = false;
        report_error(handle, ESP_FAIL, "websocket error");
        break;

    default:
        break;
    }
}

static void websocket_event_handler(void *arg, esp_event_base_t base,
                                    int32_t id, void *data)
{
    (void)base;
    usaki_server_call_handle_t h = arg;
    if (atomic_load(&h->event_stopping)) return;
    if (id == WEBSOCKET_EVENT_CONNECTED || id == WEBSOCKET_EVENT_DISCONNECTED || id == WEBSOCKET_EVENT_ERROR)
        atomic_fetch_add(&h->event_session, 1);
    if (id == WEBSOCKET_EVENT_DISCONNECTED || id == WEBSOCKET_EVENT_ERROR)
        atomic_store(&h->connected, false);
    const esp_websocket_event_data_t *e = data;
    if (id == WEBSOCKET_EVENT_DATA && (!e || e->data_len < 0 || e->data_len > RX_EVENT_BYTES ||
        e->payload_len < 0 || e->payload_len > RX_PAYLOAD_LIMIT || e->payload_offset < 0 ||
        e->payload_offset > e->payload_len || e->data_len > e->payload_len - e->payload_offset ||
        (e->data_len && !e->data_ptr))) {
        atomic_store(&h->event_overflow, true); return;
    }
    queued_ws_event_t *item = NULL;
    if (xQueueReceive(h->event_free, &item, 0) != pdTRUE) {
        atomic_store(&h->event_overflow, true); return;
    }
    item->id = id;
    item->session = atomic_load(&h->event_session);
    memset(&item->event, 0, sizeof(item->event));
    if (id == WEBSOCKET_EVENT_DATA) {
        // Preserve offsets, total frame length, opcode and FIN; no borrowed bytes.
        item->event = *e;
        if (e->data_len) memcpy(item->bytes, e->data_ptr, e->data_len);
        item->event.data_ptr = item->bytes;
    }
    if (xQueueSend(h->event_ready, &item, 0) != pdTRUE) {
        (void)xQueueSend(h->event_free, &item, 0);
        atomic_store(&h->event_overflow, true);
    }
}

static void discard_queued_events(usaki_server_call_handle_t h)
{
    queued_ws_event_t *item;
    while (xQueueReceive(h->event_ready, &item, 0) == pdTRUE)
        (void)xQueueSend(h->event_free, &item, 0);
}

static void websocket_event_worker(void *arg)
{
    usaki_server_call_handle_t h = arg;
    while (!atomic_load(&h->event_stopping)) {
        if (atomic_exchange(&h->event_overflow, false)) {
            // Fail the current turn, discard partial frames and reconnect from
            // this worker, never from the client-lock-owning callback.
            atomic_fetch_add(&h->event_session, 1);
            atomic_store(&h->connected, false);
            discard_queued_events(h);
            reset_rx_binary_fragment(h);
            process_websocket_event(h, WEBSOCKET_EVENTS, WEBSOCKET_EVENT_DISCONNECTED, NULL);
            if (!atomic_load(&h->event_stopping)) {
                (void)esp_websocket_client_stop(h->ws);
                if (!atomic_load(&h->event_stopping)) (void)esp_websocket_client_start(h->ws);
            }
            continue;
        }
        queued_ws_event_t *item = NULL;
        if (xQueueReceive(h->event_ready, &item, pdMS_TO_TICKS(50)) != pdTRUE) continue;
        if (!atomic_load(&h->event_stopping) && item->session == atomic_load(&h->event_session)) {
            if (item->id == WEBSOCKET_EVENT_CONNECTED) {
                // A reconnect may supersede a queued disconnect. Always clear
                // the old turn before delivering the newest connected event.
                reset_rx_binary_fragment(h);
                process_websocket_event(h, WEBSOCKET_EVENTS, WEBSOCKET_EVENT_DISCONNECTED, NULL);
            }
            process_websocket_event(h, WEBSOCKET_EVENTS, item->id, &item->event);
        }
        (void)xQueueSend(h->event_free, &item, 0);
    }
    discard_queued_events(h);
    xSemaphoreGive(h->event_exited);
    vTaskDelete(NULL);
}

static esp_err_t create_event_worker(usaki_server_call_handle_t h)
{
    h->event_free = xQueueCreate(RX_EVENT_COUNT, sizeof(queued_ws_event_t *));
    h->event_ready = xQueueCreate(RX_EVENT_COUNT, sizeof(queued_ws_event_t *));
    h->event_exited = xSemaphoreCreateBinary();
    h->event_pool = heap_caps_calloc(RX_EVENT_COUNT, sizeof(queued_ws_event_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!h->event_pool) h->event_pool = calloc(RX_EVENT_COUNT, sizeof(queued_ws_event_t));
    if (!h->event_free || !h->event_ready || !h->event_exited || !h->event_pool) return ESP_ERR_NO_MEM;
    for (size_t i = 0; i < RX_EVENT_COUNT; ++i) {
        queued_ws_event_t *item = &h->event_pool[i];
        (void)xQueueSend(h->event_free, &item, 0);
    }
    return xTaskCreate(websocket_event_worker, "voice_events", 8192, h, 5, &h->event_task) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}

static void destroy_event_worker(usaki_server_call_handle_t h)
{
    atomic_store(&h->event_stopping, true);
    if (h->event_task) { xSemaphoreTake(h->event_exited, portMAX_DELAY); h->event_task = NULL; }
    if (h->event_free) vQueueDelete(h->event_free);
    if (h->event_ready) vQueueDelete(h->event_ready);
    if (h->event_exited) vSemaphoreDelete(h->event_exited);
    free(h->event_pool);
    h->event_free = h->event_ready = NULL;
    h->event_exited = NULL; h->event_pool = NULL;
}

esp_err_t usaki_server_call_init(const usaki_server_call_config_t *config,
                                 usaki_server_call_handle_t *out)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG, "config is null");
    ESP_RETURN_ON_FALSE(out != NULL, ESP_ERR_INVALID_ARG, TAG, "out is null");
    ESP_RETURN_ON_FALSE(config->uri != NULL, ESP_ERR_INVALID_ARG, TAG, "uri is null");

    usaki_server_call_handle_t handle = (usaki_server_call_handle_t)calloc(1, sizeof(*handle));
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_NO_MEM, TAG, "alloc handle failed");

    handle->config = *config;
    handle->config.device_id = config_string_or_default(config->device_id, USAKI_DEVICE_ID);
    handle->config.connect_url = config_string_or_default(config->connect_url,
                                                          USAKI_SERVER_DEVICE_CONNECT_URL);
    handle->config.firmware_version = config_string_or_default(config->firmware_version,
                                                               USAKI_FIRMWARE_VERSION);
    handle->config.hardware_version = config_string_or_default(config->hardware_version,
                                                               USAKI_HARDWARE_VERSION);
    handle->config.network_timeout_ms = config->network_timeout_ms > 0
                                            ? config->network_timeout_ms
                                            : USAKI_VOICE_CLIENT_WEBSOCKET_TIMEOUT_MS;
    handle->config.reconnect_timeout_ms = config->reconnect_timeout_ms > 0
                                              ? config->reconnect_timeout_ms
                                              : USAKI_VOICE_CLIENT_RECONNECT_TIMEOUT_MS;
    handle->config.send_timeout_ms = config->send_timeout_ms > 0
                                         ? config->send_timeout_ms
                                         : USAKI_VOICE_CLIENT_UPLOAD_TIMEOUT_MS;
    handle->tx_buffer_bytes = config->tx_buffer_bytes > 0
                                  ? config->tx_buffer_bytes
                                  : USAKI_SERVER_CALL_DEFAULT_TX_BUFFER_BYTES;
    handle->seq = 1;

    handle->tx_buffer = (char *)calloc(1, handle->tx_buffer_bytes);
    if (handle->tx_buffer == NULL)
    {
        free(handle);
        return ESP_ERR_NO_MEM;
    }

    esp_err_t err = connect_device(handle);
    if (err != ESP_OK)
    {
        free(handle->tx_buffer);
        free(handle);
        return err;
    }

    err = build_ws_uri_with_auth(handle);
    if (err != ESP_OK)
    {
        free(handle->tx_buffer);
        free(handle);
        return err;
    }

    esp_websocket_client_config_t ws_config = {
        .crt_bundle_attach = esp_crt_bundle_attach,
        .uri = handle->ws_uri,
        .network_timeout_ms = handle->config.network_timeout_ms,
        .reconnect_timeout_ms = handle->config.reconnect_timeout_ms,
        .task_name = "websocket_task",
        .task_stack = USAKI_SERVER_CALL_WEBSOCKET_TASK_STACK_BYTES,
        .buffer_size = USAKI_SERVER_CALL_WEBSOCKET_BUFFER_BYTES,
    };

    handle->ws = esp_websocket_client_init(&ws_config);
    if (handle->ws == NULL)
    {
        free(handle->tx_buffer);
        free(handle);
        return ESP_FAIL;
    }

    err = esp_websocket_register_events(handle->ws,
                                        WEBSOCKET_EVENT_ANY,
                                        websocket_event_handler,
                                        handle);
    if (err != ESP_OK)
    {
        esp_websocket_client_destroy(handle->ws);
        free(handle->tx_buffer);
        free(handle);
        return err;
    }

    err = create_event_worker(handle);
    if (err != ESP_OK) {
        destroy_event_worker(handle);
        esp_websocket_client_destroy(handle->ws);
        free(handle->tx_buffer); free(handle); return err;
    }
    *out = handle;
    return ESP_OK;
}

esp_err_t usaki_server_call_start(usaki_server_call_handle_t handle)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    return esp_websocket_client_start(handle->ws);
}

esp_err_t usaki_server_call_stop(usaki_server_call_handle_t handle)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    return esp_websocket_client_stop(handle->ws);
}

esp_err_t usaki_server_call_destroy(usaki_server_call_handle_t handle)
{
    if (handle == NULL)
    {
        return ESP_OK;
    }
    // Stop the producer first; the worker can finish callbacks while all
    // protocol/adapter storage still exists. Destruction is outside control locks.
    atomic_store(&handle->event_stopping, true);
    if (handle->ws != NULL) (void)esp_websocket_client_stop(handle->ws);
    destroy_event_worker(handle);
    if (handle->ws != NULL) esp_websocket_client_destroy(handle->ws);
    free(handle->rx_binary_buffer);
    free(handle->tx_buffer);
    free(handle);
    return ESP_OK;
}

bool usaki_server_call_is_connected(usaki_server_call_handle_t handle)
{
    return handle != NULL && handle->connected && esp_websocket_client_is_connected(handle->ws);
}

int usaki_server_call_next_seq(usaki_server_call_handle_t handle)
{
    if (handle == NULL)
    {
        return 0;
    }
    return handle->seq++;
}

static esp_err_t send_text(usaki_server_call_handle_t handle, const char *text)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(text != NULL, ESP_ERR_INVALID_ARG, TAG, "text is null");
    if (!usaki_server_call_is_connected(handle))
    {
        handle->connected = false;
        ESP_LOGW(TAG, "skip send text: websocket is not connected");
        return ESP_ERR_INVALID_STATE;
    }

    int len = (int)strlen(text);
    int sent = esp_websocket_client_send_text(handle->ws,
                                              text,
                                              len,
                                              pdMS_TO_TICKS(handle->config.send_timeout_ms));
    if (sent != len)
    {
        handle->connected = false;
        ESP_LOGW(TAG, "send text failed: sent=%d expected=%d", sent, len);
        return ESP_FAIL;
    }
    return ESP_OK;
}

static esp_err_t build_and_send(usaki_server_call_handle_t handle,
                                esp_err_t (*builder)(void *request, char *buffer, size_t len),
                                void *request)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(builder != NULL, ESP_ERR_INVALID_ARG, TAG, "builder is null");

    esp_err_t err = builder(request, handle->tx_buffer, handle->tx_buffer_bytes);
    ESP_RETURN_ON_ERROR(err, TAG, "build request failed");
    return send_text(handle, handle->tx_buffer);
}

static esp_err_t build_voice_input_start_adapter(void *request, char *buffer, size_t len)
{
    return usaki_protocol_build_voice_input_start(
        (const usaki_protocol_voice_input_start_t *)request,
        buffer,
        len);
}

static esp_err_t build_voice_input_end_adapter(void *request, char *buffer, size_t len)
{
    return usaki_protocol_build_voice_input_end((const usaki_protocol_voice_input_end_t *)request,
                                                buffer,
                                                len);
}

static esp_err_t build_voice_input_cancel_adapter(void *request, char *buffer, size_t len)
{
    return usaki_protocol_build_voice_input_cancel(
        (const usaki_protocol_voice_input_cancel_t *)request,
        buffer,
        len);
}

static esp_err_t build_voice_wake_detected_adapter(void *request, char *buffer, size_t len)
{
    return usaki_protocol_build_voice_wake_detected(
        (const usaki_protocol_voice_wake_detected_t *)request,
        buffer,
        len);
}

static esp_err_t build_voice_interrupt_adapter(void *request, char *buffer, size_t len)
{
    return usaki_protocol_build_voice_interrupt(
        (const usaki_protocol_voice_interrupt_t *)request,
        buffer,
        len);
}

static esp_err_t build_touch_event_adapter(void *request, char *buffer, size_t len)
{
    return usaki_protocol_build_touch_event((const usaki_protocol_touch_event_t *)request,
                                            buffer,
                                            len);
}

static esp_err_t build_sensor_update_adapter(void *request, char *buffer, size_t len)
{
    return usaki_protocol_build_sensor_update((const usaki_protocol_sensor_update_t *)request,
                                              buffer,
                                              len);
}

static esp_err_t build_error_adapter(void *request, char *buffer, size_t len)
{
    return usaki_protocol_build_error((const usaki_protocol_error_t *)request, buffer, len);
}

static void fill_header_if_needed(usaki_server_call_handle_t handle,
                                  usaki_protocol_message_header_t *header,
                                  char *message_id_buffer,
                                  size_t message_id_buffer_len)
{
    if (header->seq <= 0)
    {
        header->seq = usaki_server_call_next_seq(handle);
    }
    if (header->device_id == NULL)
    {
        header->device_id = handle->config.device_id;
    }
    if (header->message_id == NULL)
    {
        snprintf(message_id_buffer, message_id_buffer_len, "msg_%d", header->seq);
        header->message_id = message_id_buffer;
    }
}

esp_err_t usaki_server_call_send_voice_input_start(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_input_start_t *request)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");
    usaki_protocol_voice_input_start_t local = *request;
    char message_id[32] = {0};
    fill_header_if_needed(handle, &local.header, message_id, sizeof(message_id));
    return build_and_send(handle, build_voice_input_start_adapter, &local);
}

esp_err_t usaki_server_call_send_voice_input_end(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_input_end_t *request)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");
    usaki_protocol_voice_input_end_t local = *request;
    char message_id[32] = {0};
    fill_header_if_needed(handle, &local.header, message_id, sizeof(message_id));
    return build_and_send(handle, build_voice_input_end_adapter, &local);
}

esp_err_t usaki_server_call_send_voice_input_cancel(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_input_cancel_t *request)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");
    usaki_protocol_voice_input_cancel_t local = *request;
    char message_id[32] = {0};
    fill_header_if_needed(handle, &local.header, message_id, sizeof(message_id));
    return build_and_send(handle, build_voice_input_cancel_adapter, &local);
}

esp_err_t usaki_server_call_send_voice_wake_detected(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_wake_detected_t *request)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");
    usaki_protocol_voice_wake_detected_t local = *request;
    char message_id[32] = {0};
    fill_header_if_needed(handle, &local.header, message_id, sizeof(message_id));
    return build_and_send(handle, build_voice_wake_detected_adapter, &local);
}

esp_err_t usaki_server_call_send_voice_interrupt(
    usaki_server_call_handle_t handle,
    const usaki_protocol_voice_interrupt_t *request)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");
    usaki_protocol_voice_interrupt_t local = *request;
    char message_id[32] = {0};
    fill_header_if_needed(handle, &local.header, message_id, sizeof(message_id));
    return build_and_send(handle, build_voice_interrupt_adapter, &local);
}

esp_err_t usaki_server_call_send_touch_event(usaki_server_call_handle_t handle,
                                             const usaki_protocol_touch_event_t *request)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");
    usaki_protocol_touch_event_t local = *request;
    char message_id[32] = {0};
    fill_header_if_needed(handle, &local.header, message_id, sizeof(message_id));
    return build_and_send(handle, build_touch_event_adapter, &local);
}

esp_err_t usaki_server_call_send_sensor_update(usaki_server_call_handle_t handle,
                                               const usaki_protocol_sensor_update_t *request)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");
    usaki_protocol_sensor_update_t local = *request;
    char message_id[32] = {0};
    fill_header_if_needed(handle, &local.header, message_id, sizeof(message_id));
    return build_and_send(handle, build_sensor_update_adapter, &local);
}

esp_err_t usaki_server_call_send_error(usaki_server_call_handle_t handle,
                                       const usaki_protocol_error_t *request)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");
    usaki_protocol_error_t local = *request;
    char message_id[32] = {0};
    fill_header_if_needed(handle, &local.header, message_id, sizeof(message_id));
    return build_and_send(handle, build_error_adapter, &local);
}

esp_err_t usaki_server_call_send_binary(usaki_server_call_handle_t handle,
                                        const uint8_t *data,
                                        size_t len)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(data != NULL || len == 0, ESP_ERR_INVALID_ARG, TAG, "data is null");
    if (!usaki_server_call_is_connected(handle))
    {
        handle->connected = false;
        ESP_LOGW(TAG, "skip send binary: websocket is not connected");
        return ESP_ERR_INVALID_STATE;
    }

    int sent = esp_websocket_client_send_bin(handle->ws,
                                             (const char *)data,
                                             (int)len,
                                             pdMS_TO_TICKS(handle->config.send_timeout_ms));
    if (sent != (int)len)
    {
        handle->connected = false;
        ESP_LOGW(TAG, "send binary failed: sent=%d expected=%u", sent, (unsigned)len);
        return ESP_FAIL;
    }
    return ESP_OK;
}

esp_err_t usaki_server_call_handle_server_text(usaki_server_call_handle_t handle,
                                               const char *text,
                                               size_t len)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(text != NULL, ESP_ERR_INVALID_ARG, TAG, "text is null");

    usaki_protocol_server_message_t *message =
        (usaki_protocol_server_message_t *)calloc(1, sizeof(*message));
    ESP_RETURN_ON_FALSE(message != NULL, ESP_ERR_NO_MEM, TAG, "alloc server message failed");

    esp_err_t err = usaki_protocol_parse_server_message(text, len, message);
    if (err != ESP_OK)
    {
        if (handle->config.callbacks.unhandled_text != NULL)
        {
            handle->config.callbacks.unhandled_text(text, len, handle->config.user_ctx);
        }
        free(message);
        return err;
    }

    if (message->type == USAKI_PROTOCOL_SERVER_MESSAGE_BODY_ACTION ||
        message->type == USAKI_PROTOCOL_SERVER_MESSAGE_MOTION_SERVO_BATCH ||
        message->type == USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_START ||
        message->type == USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_END ||
        message->type == USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_CANCEL)
    {
        ESP_LOGI(TAG,
                 "server message: type=%s seq=%d body_actions=%d motion_servos=%d output_id=%s reason=%s",
                 message->type_name,
                 message->seq,
                 message->body_action_count,
                 message->motion_servo_count,
                 message->output_id,
                 message->reason);
    }

    for (size_t i = 0; i < sizeof(SERVER_MESSAGE_DISPATCH) / sizeof(SERVER_MESSAGE_DISPATCH[0]); ++i)
    {
        if (SERVER_MESSAGE_DISPATCH[i].type == message->type)
        {
            err = SERVER_MESSAGE_DISPATCH[i].dispatch(handle, message);
            free(message);
            return err;
        }
    }

    ESP_LOGI(TAG, "unhandled server message type=%s", message->type_name);
    if (handle->config.callbacks.unhandled_text != NULL)
    {
        handle->config.callbacks.unhandled_text(text, len, handle->config.user_ctx);
    }
    free(message);
    return ESP_OK;
}

esp_err_t usaki_server_call_handle_server_binary(usaki_server_call_handle_t handle,
                                                 const uint8_t *data,
                                                 size_t len)
{
    ESP_RETURN_ON_FALSE(handle != NULL, ESP_ERR_INVALID_ARG, TAG, "handle is null");
    ESP_RETURN_ON_FALSE(data != NULL || len == 0, ESP_ERR_INVALID_ARG, TAG, "data is null");

    if (handle->config.callbacks.binary != NULL)
    {
        handle->config.callbacks.binary(data, len, handle->config.user_ctx);
    }
    return ESP_OK;
}

static esp_err_t dispatch_voice_output_start(usaki_server_call_handle_t handle,
                                             const usaki_protocol_server_message_t *message)
{
    if (handle->config.callbacks.voice_output_start != NULL)
    {
        handle->config.callbacks.voice_output_start(message, handle->config.user_ctx);
    }
    return ESP_OK;
}

static esp_err_t dispatch_voice_output_end(usaki_server_call_handle_t handle,
                                           const usaki_protocol_server_message_t *message)
{
    if (handle->config.callbacks.voice_output_end != NULL)
    {
        handle->config.callbacks.voice_output_end(message, handle->config.user_ctx);
    }
    return ESP_OK;
}

static esp_err_t dispatch_voice_output_cancel(usaki_server_call_handle_t handle,
                                              const usaki_protocol_server_message_t *message)
{
    if (handle->config.callbacks.voice_output_cancel != NULL)
    {
        handle->config.callbacks.voice_output_cancel(message, handle->config.user_ctx);
    }
    return ESP_OK;
}

static esp_err_t dispatch_emotion_update(usaki_server_call_handle_t handle,
                                         const usaki_protocol_server_message_t *message)
{
    if (handle->config.callbacks.emotion_update != NULL)
    {
        handle->config.callbacks.emotion_update(message, handle->config.user_ctx);
    }
    return ESP_OK;
}

static esp_err_t dispatch_eye_animation(usaki_server_call_handle_t handle,
                                        const usaki_protocol_server_message_t *message)
{
    if (handle->config.callbacks.eye_animation != NULL)
    {
        handle->config.callbacks.eye_animation(message, handle->config.user_ctx);
    }
    return ESP_OK;
}

static esp_err_t dispatch_body_action(usaki_server_call_handle_t handle,
                                      const usaki_protocol_server_message_t *message)
{
    if (handle->config.callbacks.body_action != NULL)
    {
        handle->config.callbacks.body_action(message, handle->config.user_ctx);
    }
    return ESP_OK;
}

static esp_err_t dispatch_motion_servo_batch(usaki_server_call_handle_t handle,
                                             const usaki_protocol_server_message_t *message)
{
    if (handle->config.callbacks.motion_servo_batch != NULL)
    {
        handle->config.callbacks.motion_servo_batch(message, handle->config.user_ctx);
    }
    return ESP_OK;
}

static esp_err_t dispatch_notification_push(usaki_server_call_handle_t handle,
                                            const usaki_protocol_server_message_t *message)
{
    if (handle->config.callbacks.notification_push != NULL)
    {
        handle->config.callbacks.notification_push(message, handle->config.user_ctx);
    }
    return ESP_OK;
}

static esp_err_t dispatch_server_error(usaki_server_call_handle_t handle,
                                       const usaki_protocol_server_message_t *message)
{
    ESP_LOGW(TAG, "server error code=%d message=%s", message->code, message->message);
    if (handle->config.callbacks.server_error != NULL)
    {
        handle->config.callbacks.server_error(message, handle->config.user_ctx);
    }
    return ESP_OK;
}
