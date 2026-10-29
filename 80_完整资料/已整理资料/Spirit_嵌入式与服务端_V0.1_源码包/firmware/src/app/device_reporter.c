#include "app/device_reporter.h"

#include <stdio.h>
#include <string.h>

#include "board/usaki_board.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_http_client.h"
#include "esp_log.h"

static const char *TAG = "device_reporter";

typedef struct {
    char *buffer;
    int capacity;
    int length;
} http_response_buffer_t;

static esp_err_t http_event_handler(esp_http_client_event_t *event)
{
    if (event->event_id != HTTP_EVENT_ON_DATA || event->user_data == NULL) {
        return ESP_OK;
    }

    http_response_buffer_t *response = (http_response_buffer_t *)event->user_data;
    if (response->length >= response->capacity - 1) {
        return ESP_OK;
    }

    int copy_len = event->data_len;
    int remaining = response->capacity - response->length - 1;
    if (copy_len > remaining) {
        copy_len = remaining;
    }

    memcpy(response->buffer + response->length, event->data, copy_len);
    response->length += copy_len;
    response->buffer[response->length] = '\0';
    return ESP_OK;
}

static esp_err_t post_device_report_payload(const char *payload)
{
    ESP_RETURN_ON_FALSE(payload != NULL, ESP_ERR_INVALID_ARG, TAG, "payload is null");
    ESP_LOGI(TAG, "posting device report to: %s", USAKI_SERVER_DEVICE_REPORT_URL);
#if USAKI_DEVICE_REPORT_VERBOSE_LOG
    ESP_LOGI(TAG, "device report payload: %s", payload);
#endif

    char response_body[256] = {0};
    http_response_buffer_t response = {
        .buffer = response_body,
        .capacity = sizeof(response_body),
        .length = 0,
    };

    esp_http_client_config_t config = {
        .url = USAKI_SERVER_DEVICE_REPORT_URL,
        .method = HTTP_METHOD_POST,
        .timeout_ms = USAKI_DEVICE_REPORT_TIMEOUT_MS,
        .event_handler = http_event_handler,
        .user_data = &response,
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    ESP_RETURN_ON_FALSE(client != NULL, ESP_FAIL, TAG, "http client init failed");

    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, payload, strlen(payload));

    esp_err_t err = esp_http_client_perform(client);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "device report response status=%d", esp_http_client_get_status_code(client));
#if USAKI_DEVICE_REPORT_VERBOSE_LOG
        ESP_LOGI(TAG,
                 "device report response body: %s",
                 response.length > 0 ? response.buffer : "<empty>");
#endif
    } else {
        ESP_LOGW(TAG, "device report failed: %s", esp_err_to_name(err));
    }

    esp_http_client_cleanup(client);
    return err;
}

esp_err_t device_reporter_post_status(const device_reporter_status_t *status)
{
    ESP_RETURN_ON_FALSE(status != NULL, ESP_ERR_INVALID_ARG, TAG, "status is null");
    ESP_RETURN_ON_FALSE(status->state != NULL, ESP_ERR_INVALID_ARG, TAG, "state is null");

    char payload[512] = {0};
    int written = snprintf(payload,
                           sizeof(payload),
                           "{"
                           "\"device_id\":\"%s\","
                           "\"state\":\"%s\","
                           "\"firmware_version\":\"%s\","
                           "\"capabilities\":[\"mic\",\"speaker\",\"display\",\"servo\"],"
                           "\"metrics\":{"
                           "\"reset_reason\":%d,"
                           "\"free_heap_bytes\":%d"
                           "}"
                           "}",
                           USAKI_DEVICE_ID,
                           status->state,
                           USAKI_FIRMWARE_VERSION,
                           status->reset_reason,
                           status->free_heap_bytes);
    ESP_RETURN_ON_FALSE(written > 0 && written < (int)sizeof(payload),
                        ESP_ERR_INVALID_SIZE,
                        TAG,
                        "device report payload overflow");

    return post_device_report_payload(payload);
}

esp_err_t device_reporter_post_wakeup(const char *wake_word)
{
    ESP_RETURN_ON_FALSE(wake_word != NULL, ESP_ERR_INVALID_ARG, TAG, "wake_word is null");

    char payload[512] = {0};
    int written = snprintf(payload,
                           sizeof(payload),
                           "{"
                           "\"device_id\":\"%s\","
                           "\"state\":\"listening\","
                           "\"firmware_version\":\"%s\","
                           "\"capabilities\":[\"mic\",\"speaker\",\"display\",\"servo\"],"
                           "\"metrics\":{"
                           "\"event\":\"wake_word_detected\","
                           "\"wake_word\":\"%s\","
                           "\"free_heap_bytes\":%d"
                           "}"
                           "}",
                           USAKI_DEVICE_ID,
                           USAKI_FIRMWARE_VERSION,
                           wake_word,
                           (int)heap_caps_get_free_size(MALLOC_CAP_DEFAULT));
    ESP_RETURN_ON_FALSE(written > 0 && written < (int)sizeof(payload),
                        ESP_ERR_INVALID_SIZE,
                        TAG,
                        "device wakeup payload overflow");

    return post_device_report_payload(payload);
}
