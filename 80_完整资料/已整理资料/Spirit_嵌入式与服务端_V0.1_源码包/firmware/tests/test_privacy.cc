// Host unit test of actual privacy policy. Stubs only emulate NVS error paths;
// they are not hardware drivers and are never included in the firmware build.
#include "app/spirit_privacy.h"
#include "nvs.h"
#include <cassert>
#include <atomic>
#include <chrono>
#include <thread>
#include <cstdio>
static int stored = -1, pending = -1;
static bool fail_open, fail_commit;
esp_err_t nvs_open(const char*, int, nvs_handle_t* h) { *h=1; return fail_open ? ESP_FAIL : ESP_OK; }
esp_err_t nvs_get_u8(nvs_handle_t, const char*, uint8_t* v) { if(stored<0) return ESP_ERR_NVS_NOT_FOUND; *v=stored; return ESP_OK; }
esp_err_t nvs_set_u8(nvs_handle_t, const char*, uint8_t v) { pending=v; return ESP_OK; }
esp_err_t nvs_commit(nvs_handle_t) { if(fail_commit) return ESP_FAIL; stored=pending; return ESP_OK; }
void nvs_close(nvs_handle_t) {}
int main() {
    assert(spirit_privacy_muted());
    assert(spirit_privacy_init()==ESP_OK && spirit_privacy_muted());
    assert(spirit_privacy_set_muted(false)==ESP_OK && !spirit_privacy_muted());
    assert(spirit_privacy_init()==ESP_OK && !spirit_privacy_muted());
    assert(spirit_privacy_set_muted(true)==ESP_OK && spirit_privacy_muted());
    assert(spirit_privacy_init()==ESP_OK && spirit_privacy_muted());
    fail_commit=true;
    assert(spirit_privacy_set_muted(false)!=ESP_OK && spirit_privacy_muted());
    fail_commit=false; fail_open=true;
    assert(spirit_privacy_set_muted(false)!=ESP_OK && spirit_privacy_muted());
    assert(spirit_privacy_init()!=ESP_OK && spirit_privacy_muted());
    fail_open=false;
    assert(spirit_privacy_set_muted(false)==ESP_OK);
    const uint32_t old_epoch = spirit_privacy_epoch();
    std::atomic<bool> entered{false}, release{false}, completed{false}, mute_returned{false};
    std::thread upload([&] {
        std::lock_guard<std::recursive_mutex> l(spirit_privacy_gate());
        entered=true;
        while(!release.load()) std::this_thread::yield();
        completed=true;
    });
    while(!entered.load()) std::this_thread::yield();
    std::thread muter([&] { assert(spirit_privacy_set_muted(true)==ESP_OK); mute_returned=true; });
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while(!spirit_privacy_muted() && std::chrono::steady_clock::now()<deadline) std::this_thread::yield();
    assert(spirit_privacy_muted()); // Intent is visible before a blocking upload ends.
    assert(!mute_returned.load());
    release=true;
    upload.join(); muter.join();
    assert(completed.load() && mute_returned.load() && spirit_privacy_muted());
    assert(spirit_privacy_epoch()!=old_epoch); // Old captured frames are invalidated.
    puts("PASS: privacy default/persistence/fail-closed/in-flight gate (host unit test, not firmware/hardware validation)");
}
