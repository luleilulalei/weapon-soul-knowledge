#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#ifdef __cplusplus
extern "C" {
#endif
#define SPIRIT_TOUCH_CHANNELS 6
// Validity flags describe the latest poll, not just startup detection.
typedef struct {
    int64_t sampled_us, imu_sampled_us;
    bool imu_ready, imu_valid, touch_ready, touch_valid, expander_ready, expander_valid;
    int16_t accel_raw[3], gyro_raw[3]; // +/-8g and +/-2000 deg/s, signed 16-bit
    uint8_t touch_mask;
    bool docked, charging, power_good, aux_key_down, usb_present;
    bool accessory_present_at_boot, accessory_present, accessory_changed;
    int battery_adc_raw, battery_pin_mv, battery_mv; // -1 = unavailable; no fabricated percent
    bool battery_calibrated;
    bool haptic_configured, haptic_active;
    uint8_t boost_owners;
    uint32_t bus_errors;
} spirit_peripherals_status_t;
esp_err_t spirit_peripherals_init(void);
esp_err_t spirit_peripherals_start(void);
esp_err_t spirit_peripherals_get_status(spirit_peripherals_status_t *status);
// Actual divider ratio must be measured/confirmed; ratio_x1000=(Rtop+Rbottom)/Rbottom*1000.
esp_err_t spirit_battery_set_divider_ratio(unsigned ratio_x1000);
// GPIO8 controls shared boost, NOT total device power or independent accessory power.
typedef enum { SPIRIT_BOOST_AUDIO = 1, SPIRIT_BOOST_HAPTIC = 2, SPIRIT_BOOST_MANUAL = 4 } spirit_boost_owner_t;
esp_err_t spirit_boost_request(spirit_boost_owner_t owner, bool enabled);
esp_err_t spirit_boost_set_enabled(bool enabled); // compatibility manual owner, does not override other demands
// DRV2605L LRA calibrated register set from this exact motor/fixture. No guessed defaults.
typedef struct { uint8_t rated_voltage, overdrive_clamp, feedback, control1, control2, control3,
    autocal_comp, autocal_bemf; } spirit_haptic_config_t;
esp_err_t spirit_haptic_configure(const spirit_haptic_config_t *config);
esp_err_t spirit_haptic_play_for(uint8_t library_effect, uint32_t duration_ms);
esp_err_t spirit_haptic_play(uint8_t library_effect); // 1..123, bounded by 1s safety stop
esp_err_t spirit_haptic_stop(void);
// J7 reserved raw transport: no accessory/light-sword packet protocol was supplied.
// Only devices attached before power-on are allowed. Any DET transition latches disabled until reboot.
esp_err_t spirit_j7_enable_transport(bool enabled); // explicit opt-in; disabled at boot
esp_err_t spirit_j7_transfer(uint8_t address, const uint8_t *tx, size_t tx_len, uint8_t *rx, size_t rx_len);
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
extern "C" {
#endif
// Optional PN532 at main-bus address 0x24, I2C mode, 3.3V. Never enabled at boot.
// UID is an identifier, NOT proof of authenticity / entitlement.
esp_err_t spirit_nfc_init(void);
esp_err_t spirit_nfc_read_uid(uint8_t uid[10], size_t *uid_len);
#ifdef __cplusplus
}
#endif
