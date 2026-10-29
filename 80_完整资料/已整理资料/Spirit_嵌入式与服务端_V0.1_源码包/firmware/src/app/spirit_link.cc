#include "app/spirit_link.h"
#include "app/spirit_privacy.h"
#include "board/usaki_board.h"
#include "spirit_peripherals/spirit_peripherals.h"
#include "cJSON.h"
#include "esp_crt_bundle.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_websocket_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>

namespace {
constexpr size_t kMaxJson = 4096;
struct Incoming { int64_t received_us; uint32_t session; char json[kMaxJson + 1]; };
struct Ack { char id[65]; char status[12]; char reason[161]; };
static esp_websocket_client_handle_t ws;
static QueueHandle_t queue;
static TaskHandle_t worker;
static std::atomic<bool> connected{false}, stopping{false};
static std::atomic<uint32_t> session{0};
static Incoming assembled;
static size_t accumulated, frame_base, frame_received;
static bool assembling;
static Ack cache[8];
static unsigned cache_next, sequence;
static const char *TAG = "spirit_link";
static std::string uri;

static const char *string_field(const cJSON *o, const char *key) {
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(o, key);
    return cJSON_IsString(v) && v->valuestring ? v->valuestring : nullptr;
}
static bool integer_field(const cJSON *o, const char *key, int fallback, int low, int high, int &out) {
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(o, key);
    if (!v) { out = fallback; return true; }
    if (!cJSON_IsNumber(v) || !std::isfinite(v->valuedouble) ||
        v->valuedouble != std::floor(v->valuedouble) || v->valuedouble < low || v->valuedouble > high) return false;
    out = static_cast<int>(v->valuedouble); return true;
}
static void send_data(const char *type, cJSON *data) {
    if (!data) return;
    if (!connected.load()) { cJSON_Delete(data); return; }
    cJSON *root = cJSON_CreateObject();
    if (!root) { cJSON_Delete(data); return; }
    char id[48]; std::snprintf(id, sizeof(id), "spirit_%lld_%u", static_cast<long long>(esp_timer_get_time()), ++sequence);
    cJSON_AddStringToObject(root, "id", id);
    cJSON_AddStringToObject(root, "type", type);
    cJSON_AddStringToObject(root, "device_id", USAKI_DEVICE_ID);
    cJSON_AddNumberToObject(root, "seq", sequence);
    cJSON_AddItemToObject(root, "data", data);
    char *json = cJSON_PrintUnformatted(root);
    if (json) { (void)esp_websocket_client_send_text(ws, json, std::strlen(json), pdMS_TO_TICKS(150)); cJSON_free(json); }
    cJSON_Delete(root);
}
static void send_ack(const Ack &ack) {
    cJSON *data = cJSON_CreateObject();
    if (!data) return;
    cJSON_AddStringToObject(data, "command_id", ack.id);
    cJSON_AddStringToObject(data, "status", ack.status);
    cJSON_AddStringToObject(data, "reason", ack.reason);
    send_data("spirit.ack", data);
}
static void result(const char *id, const char *status, const char *reason) {
    Ack &ack = cache[cache_next++ % 8];
    std::snprintf(ack.id, sizeof(ack.id), "%s", id);
    std::snprintf(ack.status, sizeof(ack.status), "%s", status);
    std::snprintf(ack.reason, sizeof(ack.reason), "%s", reason);
    send_ack(ack);
}
static void command(const Incoming &in) {
    if (!connected.load() || in.session != session.load()) return; // no stale replay after reconnect
    const char *end = nullptr;
    cJSON *root = cJSON_ParseWithLengthOpts(in.json, std::strlen(in.json) + 1, &end, true);
    if (!root) return;
    const char *type = string_field(root, "type"), *device = string_field(root, "device_id");
    if (!type || std::strcmp(type, "spirit.effect") || !device || std::strcmp(device, USAKI_DEVICE_ID)) { cJSON_Delete(root); return; }
    const cJSON *data = cJSON_GetObjectItemCaseSensitive(root, "data");
    const char *id = string_field(data, "command_id"), *effect = string_field(data, "effect");
    if (!id || !*id || std::strlen(id) > 64) { cJSON_Delete(root); return; }
    for (const Ack &ack : cache) if (!std::strcmp(ack.id, id)) { send_ack(ack); cJSON_Delete(root); return; }
    int ttl=1000, duration=100, library=1;
    bool valid = cJSON_IsObject(data) && effect &&
        integer_field(data, "ttl_ms", 1000, 100, 3000, ttl) &&
        integer_field(data, "duration_ms", 100, 1, 1000, duration) &&
        integer_field(data, "library_effect", 1, 1, 123, library);
    // Do not silently reinterpret intensity/unknown raw controls.
    for (const cJSON *v = data ? data->child : nullptr; v; v = v->next) {
        if (!v->string || (std::strcmp(v->string,"command_id") && std::strcmp(v->string,"effect") &&
            std::strcmp(v->string,"ttl_ms") && std::strcmp(v->string,"duration_ms") && std::strcmp(v->string,"library_effect"))) valid = false;
    }
    if (!valid) result(id, "rejected", "invalid_effect_parameters");
    else if (esp_timer_get_time() - in.received_us > static_cast<int64_t>(ttl) * 1000) result(id, "expired", "local_queue_ttl_elapsed");
    else if (!std::strcmp(effect, "blade")) result(id, "rejected", "blade_protocol_unimplemented");
    else if (!std::strcmp(effect, "stop")) {
        esp_err_t err = spirit_haptic_stop();
        result(id, err == ESP_OK ? "applied" : "rejected", err == ESP_OK ? "haptic_stopped" : esp_err_to_name(err));
    } else if (!std::strcmp(effect, "haptic")) {
        esp_err_t err = spirit_haptic_play_for(static_cast<uint8_t>(library), static_cast<uint32_t>(duration));
        result(id, err == ESP_OK ? "applied" : "rejected", err == ESP_OK ? "haptic_started" : "haptic_unconfigured_or_driver_error");
    } else result(id, "rejected", "unsupported_effect");
    cJSON_Delete(root);
}
static void telemetry() {
    spirit_peripherals_status_t s = {};
    bool ready = spirit_peripherals_get_status(&s) == ESP_OK;
    cJSON *d = cJSON_CreateObject(); if (!d) return;
    cJSON_AddStringToObject(d, "protocol", "spirit.v1");
    cJSON_AddBoolToObject(d, "battery_valid", ready && s.battery_calibrated && s.battery_mv >= 0);
    cJSON_AddBoolToObject(d, "haptic_ready", ready && s.haptic_configured);
    cJSON_AddBoolToObject(d, "blade_ready", false);
    cJSON_AddBoolToObject(d, "peripherals_ready", ready);
    cJSON_AddBoolToObject(d, "privacy_muted", spirit_privacy_muted());
    cJSON_AddNumberToObject(d, "uptime_ms", esp_timer_get_time()/1000);
    cJSON_AddBoolToObject(d, "imu_valid", ready && s.imu_valid);
    cJSON_AddBoolToObject(d, "touch_valid", ready && s.touch_valid);
    cJSON_AddBoolToObject(d, "expander_valid", ready && s.expander_valid);
    if (ready) {
        cJSON_AddNumberToObject(d, "sampled_us", s.sampled_us);
        cJSON_AddNumberToObject(d, "imu_sampled_us", s.imu_sampled_us);
        int a[3] = {s.accel_raw[0],s.accel_raw[1],s.accel_raw[2]}, g[3] = {s.gyro_raw[0],s.gyro_raw[1],s.gyro_raw[2]};
        cJSON_AddItemToObject(d,"accel_raw",cJSON_CreateIntArray(a,3));
        cJSON_AddItemToObject(d,"gyro_raw",cJSON_CreateIntArray(g,3));
        cJSON_AddNumberToObject(d,"touch_mask",s.touch_mask);
        cJSON_AddNumberToObject(d,"battery_pin_mv",s.battery_pin_mv);
        cJSON_AddNumberToObject(d,"battery_mv",s.battery_mv);
        cJSON_AddBoolToObject(d,"battery_calibrated",s.battery_calibrated);
        cJSON_AddBoolToObject(d,"docked",s.docked);
        cJSON_AddBoolToObject(d,"charging",s.charging);
        cJSON_AddBoolToObject(d,"power_good",s.power_good);
        cJSON_AddBoolToObject(d,"usb_present",s.usb_present);
        cJSON_AddBoolToObject(d,"accessory_present",s.accessory_present);
        cJSON_AddBoolToObject(d,"accessory_changed",s.accessory_changed);
        cJSON_AddNumberToObject(d,"bus_errors",s.bus_errors);
    }
    send_data("spirit.telemetry",d);
}
static void run(void *) {
    Incoming in;
    int64_t next = 0;
    while (!stopping.load()) {
        if (xQueueReceive(queue, &in, pdMS_TO_TICKS(50)) == pdPASS) command(in);
        if (connected.load() && esp_timer_get_time() >= next) { telemetry(); next=esp_timer_get_time()+1000000; }
    }
    vTaskDelete(nullptr);
}
static void event(void *, esp_event_base_t, int32_t event_id, void *event_data) {
    if (event_id == WEBSOCKET_EVENT_CONNECTED) { ++session; connected.store(true); assembling=false; return; }
    if (event_id == WEBSOCKET_EVENT_DISCONNECTED || event_id == WEBSOCKET_EVENT_ERROR) {
        connected.store(false); ++session; assembling=false; return;
    }
    if (event_id != WEBSOCKET_EVENT_DATA) return;
    const auto *e = static_cast<esp_websocket_event_data_t *>(event_data);
    if (e->op_code != 1 && e->op_code != 0) return; // ignore binary/control frames
    if (e->payload_offset == 0) {
        if (e->op_code == 1) {
            accumulated=0; assembling=true; assembled.received_us=esp_timer_get_time(); assembled.session=session.load();
        } else if (!assembling) return;
        frame_base=accumulated; frame_received=0;
    }
    if (!assembling || e->data_len < 0 || e->payload_len < 0 || e->payload_offset < 0 ||
        static_cast<size_t>(e->payload_offset) != frame_received ||
        frame_base + static_cast<size_t>(e->payload_len) > kMaxJson ||
        e->payload_offset + e->data_len > e->payload_len || (!e->data_ptr && e->data_len)) { assembling=false; return; }
    if (e->data_len) std::memcpy(assembled.json+frame_base+frame_received,e->data_ptr,e->data_len);
    frame_received += e->data_len;
    if (frame_received != static_cast<size_t>(e->payload_len)) return;
    accumulated=frame_base+frame_received;
    if (e->fin) {
        assembled.json[accumulated]='\0';
        if (!std::memchr(assembled.json,'\0',accumulated) && xQueueSend(queue,&assembled,0) != pdPASS)
            ESP_LOGW(TAG,"effect queue full; command dropped (server must time out)");
        assembling=false;
    }
}
static std::string encode_id(const char *id) {
    std::string out;
    for (const unsigned char *p=reinterpret_cast<const unsigned char *>(id); *p; ++p) {
        if ((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='-'||*p=='_'||*p=='.') out.push_back(*p);
        else { char escaped[4]; std::snprintf(escaped,sizeof(escaped),"%%%02X",*p); out+=escaped; }
    }
    return out;
}
}
esp_err_t spirit_link_start(void) {
    if (ws) return ESP_OK;
    if (!CONFIG_SPIRIT_EFFECT_URL[0] || std::string(CONFIG_SPIRIT_EFFECT_URL).find("example.invalid") != std::string::npos) return ESP_OK;
    uri=CONFIG_SPIRIT_EFFECT_URL;
    uri += uri.find('?') == std::string::npos ? "?device_id=" : "&device_id=";
    uri += encode_id(USAKI_DEVICE_ID);
    queue=xQueueCreate(2,sizeof(Incoming)); if (!queue) return ESP_ERR_NO_MEM;
    esp_websocket_client_config_t cfg = {};
    cfg.uri=uri.c_str(); cfg.crt_bundle_attach=esp_crt_bundle_attach;
    cfg.buffer_size=1024; cfg.task_stack=6144; cfg.task_name="spirit_ws";
    cfg.network_timeout_ms=1000; cfg.reconnect_timeout_ms=3000;
    ws=esp_websocket_client_init(&cfg);
    if (!ws) { vQueueDelete(queue); queue=nullptr; return ESP_ERR_NO_MEM; }
    esp_err_t err=esp_websocket_register_events(ws,WEBSOCKET_EVENT_ANY,event,nullptr);
    if (err==ESP_OK) err=esp_websocket_client_start(ws);
    if (err!=ESP_OK) { esp_websocket_client_destroy(ws); ws=nullptr; vQueueDelete(queue); queue=nullptr; return err; }
    if (xTaskCreate(run,"spirit_link",8192,nullptr,3,&worker)!=pdPASS) {
        esp_websocket_client_stop(ws); esp_websocket_client_destroy(ws); ws=nullptr;
        vQueueDelete(queue); queue=nullptr; return ESP_ERR_NO_MEM;
    }
    ESP_LOGI(TAG,"Spirit telemetry/effect development link started");
    return ESP_OK;
}
