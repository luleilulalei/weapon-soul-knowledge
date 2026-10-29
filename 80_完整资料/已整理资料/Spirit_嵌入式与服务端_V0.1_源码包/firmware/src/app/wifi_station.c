#include "app/wifi_station.h"

#include <string.h>

#include "board/usaki_board.h"
#include "esp_check.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "nvs_flash.h"

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT BIT1

static const char *TAG = "wifi_station";
static EventGroupHandle_t s_wifi_event_group;
static int s_retry_count;

static const char *wifi_disconnect_reason_name(uint8_t reason)
{
    switch (reason) {
    case WIFI_REASON_AUTH_EXPIRE:
        return "auth_expire";
    case WIFI_REASON_AUTH_FAIL:
        return "auth_fail";
    case WIFI_REASON_NO_AP_FOUND:
        return "no_ap_found";
    case WIFI_REASON_HANDSHAKE_TIMEOUT:
        return "handshake_timeout";
    case WIFI_REASON_ASSOC_FAIL:
        return "assoc_fail";
    case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:
        return "4way_handshake_timeout";
    default:
        return "unknown";
    }
}

static void wifi_event_handler(void *arg,
                               esp_event_base_t event_base,
                               int32_t event_id,
                               void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
        return;
    }

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        wifi_event_sta_disconnected_t *disconnected = (wifi_event_sta_disconnected_t *)event_data;
        uint8_t reason = disconnected != NULL ? disconnected->reason : 0;

        if (s_retry_count < USAKI_WIFI_MAX_RETRY) {
            esp_wifi_connect();
            ++s_retry_count;
            ESP_LOGW(TAG,
                     "retry wifi connection: %d, reason=%u(%s)",
                     s_retry_count,
                     reason,
                     wifi_disconnect_reason_name(reason));
        } else {
            xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
        }
        return;
    }

    if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
#if USAKI_WIFI_VERBOSE_LOG
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "got ip: " IPSTR, IP2STR(&event->ip_info.ip));
#endif
        s_retry_count = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

esp_err_t wifi_station_connect(void)
{
    /* NVS is initialized by Spirit startup. Never erase persisted privacy. */
    if (USAKI_WIFI_SSID[0] == '\0') return ESP_ERR_INVALID_STATE;
    ESP_RETURN_ON_ERROR(esp_netif_init(), TAG, "netif init failed");
    ESP_RETURN_ON_ERROR(esp_event_loop_create_default(), TAG, "event loop init failed");
#if USAKI_WIFI_VERBOSE_LOG
    ESP_LOGI(TAG, "connecting to wifi ssid: %s", USAKI_WIFI_SSID);
#endif

    s_wifi_event_group = xEventGroupCreate();
    ESP_RETURN_ON_FALSE(s_wifi_event_group != NULL, ESP_ERR_NO_MEM, TAG, "event group failed");

    esp_netif_create_default_wifi_sta();

    wifi_init_config_t init_config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&init_config), TAG, "wifi init failed");

    ESP_RETURN_ON_ERROR(
        esp_event_handler_instance_register(WIFI_EVENT,
                                            ESP_EVENT_ANY_ID,
                                            &wifi_event_handler,
                                            NULL,
                                            NULL),
        TAG,
        "register wifi event failed");

    ESP_RETURN_ON_ERROR(
        esp_event_handler_instance_register(IP_EVENT,
                                            IP_EVENT_STA_GOT_IP,
                                            &wifi_event_handler,
                                            NULL,
                                            NULL),
        TAG,
        "register ip event failed");

    wifi_config_t wifi_config = {0};
    strncpy((char *)wifi_config.sta.ssid, USAKI_WIFI_SSID, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password,
            USAKI_WIFI_PASSWORD,
            sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA_PSK;

    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG, "set wifi mode failed");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &wifi_config), TAG, "set wifi config failed");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), TAG, "wifi start failed");

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group,
                                           WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
                                           pdFALSE,
                                           pdFALSE,
                                           pdMS_TO_TICKS(USAKI_WIFI_CONNECT_TIMEOUT_MS));

    if (bits & WIFI_CONNECTED_BIT) {
#if USAKI_WIFI_VERBOSE_LOG
        ESP_LOGI(TAG, "connected to wifi: %s", USAKI_WIFI_SSID);
#endif
        return ESP_OK;
    }

    ESP_LOGE(TAG, "wifi connection failed: %s", USAKI_WIFI_SSID);
    return ESP_FAIL;
}
