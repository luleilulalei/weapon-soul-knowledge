#include "app/spirit_privacy.h"
#include <atomic>
#include "nvs.h"
static std::atomic<bool> muted{true};
static std::atomic<uint32_t> epoch{0};
static std::recursive_mutex gate;
std::recursive_mutex &spirit_privacy_gate() { return gate; }
bool spirit_privacy_muted(void) { return muted.load(); }
uint32_t spirit_privacy_epoch(void) { return epoch.load(); }
esp_err_t spirit_privacy_init(void) {
    std::lock_guard<std::recursive_mutex> lock(gate);
    muted.store(true);
    nvs_handle_t h;
    esp_err_t err = nvs_open("spirit", NVS_READWRITE, &h);
    if (err != ESP_OK) return err;
    uint8_t value = 1;
    err = nvs_get_u8(h, "mic_muted", &value);
    if (err == ESP_ERR_NVS_NOT_FOUND) err = ESP_OK;
    if (err == ESP_OK) muted.store(value != 0);
    nvs_close(h);
    return err;
}
esp_err_t spirit_privacy_set_muted(bool value) {
    // Publish intent before waiting for one in-flight read/upload to complete.
    muted.store(true);
    epoch.fetch_add(1);
    // Serialize with all capture reads and binary uploads. On return, no prior
    // upload/read is in flight; already-transmitted bytes cannot be recalled.
    std::lock_guard<std::recursive_mutex> lock(gate);
    muted.store(true);
    nvs_handle_t h;
    esp_err_t err = nvs_open("spirit", NVS_READWRITE, &h);
    if (err != ESP_OK) return err;
    err = nvs_set_u8(h, "mic_muted", value ? 1 : 0);
    if (err == ESP_OK) err = nvs_commit(h);
    nvs_close(h);
    if (err == ESP_OK) muted.store(value);
    return err;
}
