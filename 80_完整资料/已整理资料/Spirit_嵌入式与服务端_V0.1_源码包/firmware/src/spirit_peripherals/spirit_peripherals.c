#include "spirit_peripherals.h"
#include "pn532_frame.h"
#include "vendor/bmi270/bmi270.h"
#include <string.h>
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
static const char *TAG = "spirit_peripherals";
static i2c_master_bus_handle_t main_bus, j7_bus;
static i2c_master_dev_handle_t imu, cap, tca, drv;
static SemaphoreHandle_t io_lock, state_lock, j7_lock;
static adc_oneshot_unit_handle_t adc;
static adc_cali_handle_t cali;
static struct bmi2_dev bmi;
static spirit_peripherals_status_t status;
static bool initialized, running, haptic_configured, haptic_profile_valid;
static spirit_haptic_config_t haptic_profile;
static int64_t haptic_stop_us;
static esp_timer_handle_t haptic_timer;
static void haptic_timeout(void *arg) { (void)arg; gpio_set_level(GPIO_NUM_6, 0); }
// V072 S020 netlist: R124=100k top, R125=100k bottom, Q102 enabled by +3V3/Q103.
static unsigned divider_ratio = 2000, boost_owners;
static bool j7_transport_enabled;
static void boost_locked(unsigned owner, bool enable) {
    if (enable) boost_owners |= owner; else boost_owners &= ~owner;
    gpio_set_level(GPIO_NUM_8, boost_owners ? 1 : 0);
}
static esp_err_t rd(i2c_master_dev_handle_t dev, uint8_t reg, uint8_t *data, size_t len) {
    return dev ? i2c_master_transmit_receive(dev, &reg, 1, data, len, 30) : ESP_ERR_INVALID_STATE;
}
static esp_err_t wr(i2c_master_dev_handle_t dev, uint8_t reg, uint8_t value) {
    uint8_t data[] = {reg, value};
    return dev ? i2c_master_transmit(dev, data, sizeof(data), 30) : ESP_ERR_INVALID_STATE;
}
static esp_err_t add(i2c_master_bus_handle_t bus, uint8_t addr, i2c_master_dev_handle_t *out) {
    i2c_device_config_t cfg = {.dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = addr, .scl_speed_hz = 100000};
    return i2c_master_bus_add_device(bus, &cfg, out);
}
static BMI2_INTF_RETURN_TYPE bmi_read(uint8_t reg, uint8_t *data, uint32_t len, void *ctx) {
    (void)ctx; return rd(imu, reg, data, len) == ESP_OK ? 0 : -1;
}
static BMI2_INTF_RETURN_TYPE bmi_write(uint8_t reg, const uint8_t *data, uint32_t len, void *ctx) {
    (void)ctx; if (len > 32) return -1;
    uint8_t buf[33]; buf[0] = reg; memcpy(buf + 1, data, len);
    return i2c_master_transmit(imu, buf, len + 1, 30) == ESP_OK ? 0 : -1;
}
static void bmi_delay(uint32_t us, void *ctx) {
    (void)ctx;
    if (us >= 2000) vTaskDelay(pdMS_TO_TICKS((us + 999) / 1000)); else esp_rom_delay_us(us);
}
static bool init_imu(void) {
    bmi.intf = BMI2_I2C_INTF; bmi.read = bmi_read; bmi.write = bmi_write;
    bmi.delay_us = bmi_delay; bmi.read_write_len = 32; bmi.intf_ptr = &imu;
    int8_t r = bmi270_init(&bmi); // Includes Bosch's required 8192-byte feature configuration.
    if (r != BMI2_OK) { ESP_LOGW(TAG, "BMI270 init failed: %d", r); return false; }
    struct bmi2_sens_config cfg[2] = {0};
    cfg[0].type = BMI2_ACCEL; cfg[1].type = BMI2_GYRO;
    r = bmi2_get_sensor_config(cfg, 2, &bmi);
    if (r != BMI2_OK) return false;
    cfg[0].cfg.acc.odr = BMI2_ACC_ODR_100HZ; cfg[0].cfg.acc.range = BMI2_ACC_RANGE_8G;
    cfg[0].cfg.acc.bwp = BMI2_ACC_NORMAL_AVG4; cfg[0].cfg.acc.filter_perf = BMI2_PERF_OPT_MODE;
    cfg[1].cfg.gyr.odr = BMI2_GYR_ODR_100HZ; cfg[1].cfg.gyr.range = BMI2_GYR_RANGE_2000;
    cfg[1].cfg.gyr.bwp = BMI2_GYR_NORMAL_MODE; cfg[1].cfg.gyr.noise_perf = BMI2_POWER_OPT_MODE;
    cfg[1].cfg.gyr.filter_perf = BMI2_PERF_OPT_MODE;
    if (bmi2_set_sensor_config(cfg, 2, &bmi) != BMI2_OK) return false;
    uint8_t sensors[] = {BMI2_ACCEL, BMI2_GYRO};
    return bmi2_sensor_enable(sensors, 2, &bmi) == BMI2_OK;
}
static bool init_cap(void) {
    uint8_t id = 0, vendor = 0;
    if (rd(cap, 0xFD, &id, 1) != ESP_OK || rd(cap, 0xFE, &vendor, 1) != ESP_OK || id != 0x69 || vendor != 0x5D) return false;
    // Default sensitivity/thresholds retained for first board tuning. Enable all six channels,
    // disable repeat IRQs and multi-touch blocking; clear INT without changing gain bits.
    if (wr(cap, 0x21, 0x3F) != ESP_OK || wr(cap, 0x27, 0x3F) != ESP_OK ||
        wr(cap, 0x28, 0) != ESP_OK || wr(cap, 0x2A, 0) != ESP_OK) return false;
    uint8_t ctrl;
    return rd(cap, 0, &ctrl, 1) == ESP_OK && wr(cap, 0, ctrl & ~1u) == ESP_OK;
}
static void poll_once(void) {
    xSemaphoreTake(io_lock, portMAX_DELAY);
    spirit_peripherals_status_t s;
    xSemaphoreTake(state_lock, portMAX_DELAY); s = status; xSemaphoreGive(state_lock);
    s.sampled_us = esp_timer_get_time();
    s.imu_valid = s.touch_valid = s.expander_valid = false;
    if (s.imu_ready) {
        struct bmi2_sens_data d = {0};
        int8_t r = bmi2_get_sensor_data(&d, &bmi);
        if (r == BMI2_OK && (d.status & BMI2_DRDY_ACC) && (d.status & BMI2_DRDY_GYR)) {
            s.accel_raw[0] = d.acc.x; s.accel_raw[1] = d.acc.y; s.accel_raw[2] = d.acc.z;
            s.gyro_raw[0] = d.gyr.x; s.gyro_raw[1] = d.gyr.y; s.gyro_raw[2] = d.gyr.z;
            s.imu_valid = true; s.imu_sampled_us = s.sampled_us;
        } else if (r != BMI2_OK) ++s.bus_errors;
    }
    if (s.touch_ready) {
        uint8_t touch, ctrl;
        if (rd(cap, 3, &touch, 1) == ESP_OK && rd(cap, 0, &ctrl, 1) == ESP_OK && wr(cap, 0, ctrl & ~1u) == ESP_OK) {
            s.touch_mask = touch & 0x3F; s.touch_valid = true;
        } else ++s.bus_errors;
    }
    if (s.expander_ready) {
        uint8_t pins;
        if (rd(tca, 0, &pins, 1) == ESP_OK) {
            s.docked = !(pins & 1); s.charging = !(pins & 2); s.power_good = !(pins & 4);
            s.aux_key_down = !(pins & 0x40); s.expander_valid = true;
        } else ++s.bus_errors;
    }
    s.usb_present = !gpio_get_level(GPIO_NUM_39);
    // DET is observational, not hotplug protection. A transition disables future J7 transfers.
    s.accessory_present = !gpio_get_level(GPIO_NUM_2);
    if (s.accessory_present != s.accessory_present_at_boot) s.accessory_changed = true;
    s.battery_adc_raw = s.battery_pin_mv = s.battery_mv = -1;
    s.battery_calibrated = false;
    if (adc && adc_oneshot_read(adc, ADC_CHANNEL_0, &s.battery_adc_raw) == ESP_OK && cali &&
        adc_cali_raw_to_voltage(cali, s.battery_adc_raw, &s.battery_pin_mv) == ESP_OK) {
        s.battery_calibrated = true;
        if (divider_ratio) s.battery_mv = (int)((int64_t)s.battery_pin_mv * divider_ratio / 1000);
    }
    if (haptic_stop_us && s.sampled_us >= haptic_stop_us) {
        (void)wr(drv, 0x0C, 0); gpio_set_level(GPIO_NUM_6, 0); haptic_stop_us = 0;
        boost_locked(SPIRIT_BOOST_HAPTIC, false);
        haptic_configured = false; // Reapply RAM profile on the next explicit play.
    }
    s.haptic_configured = haptic_profile_valid; s.haptic_active = haptic_stop_us != 0; s.boost_owners = (uint8_t)boost_owners;
    xSemaphoreTake(state_lock, portMAX_DELAY); status = s; xSemaphoreGive(state_lock);
    xSemaphoreGive(io_lock);
}
static void task(void *arg) {
    (void)arg; TickType_t last = xTaskGetTickCount();
    while (true) { poll_once(); vTaskDelayUntil(&last, pdMS_TO_TICKS(20)); }
}
esp_err_t spirit_peripherals_init(void) {
    if (initialized) return ESP_OK;
    esp_err_t err = ESP_OK;
    memset(&status, 0, sizeof(status));
    io_lock = xSemaphoreCreateMutex(); state_lock = xSemaphoreCreateMutex(); j7_lock = xSemaphoreCreateMutex();
    if (!io_lock || !state_lock || !j7_lock) { err = ESP_ERR_NO_MEM; goto fail; }
    gpio_config_t out = {.pin_bit_mask = (1ULL << 6) | (1ULL << 8), .mode = GPIO_MODE_OUTPUT};
    err = gpio_config(&out); if (err != ESP_OK) goto fail;
    gpio_set_level(GPIO_NUM_6, 0); gpio_set_level(GPIO_NUM_8, 0);
    gpio_config_t in = {.pin_bit_mask = (1ULL << 18) | (1ULL << 40) | (1ULL << 47) | (1ULL << 39) | (1ULL << 2),
        .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE};
    err = gpio_config(&in); if (err != ESP_OK) goto fail;
    status.accessory_present_at_boot = !gpio_get_level(GPIO_NUM_2);
    status.accessory_present = status.accessory_present_at_boot;
    i2c_master_bus_config_t bus = {.i2c_port = I2C_NUM_0, .sda_io_num = GPIO_NUM_42, .scl_io_num = GPIO_NUM_41,
        .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7, .flags.enable_internal_pullup = true};
    err = i2c_new_master_bus(&bus, &main_bus); if (err != ESP_OK) goto fail;
    bus.i2c_port = I2C_NUM_1; bus.sda_io_num = GPIO_NUM_38; bus.scl_io_num = GPIO_NUM_21;
    err = i2c_new_master_bus(&bus, &j7_bus); if (err != ESP_OK) ESP_LOGW(TAG, "J7 bus unavailable: %s", esp_err_to_name(err));
    if (add(main_bus, 0x69, &imu) == ESP_OK) status.imu_ready = init_imu();
    if (add(main_bus, 0x28, &cap) == ESP_OK) status.touch_ready = init_cap();
    if (add(main_bus, 0x20, &tca) == ESP_OK) status.expander_ready = wr(tca, 3, 0xFF) == ESP_OK && wr(tca, 2, 0) == ESP_OK;
    (void)add(main_bus, 0x5A, &drv); // EN stays LOW; no motor probing/calibration at boot.
    adc_oneshot_unit_init_cfg_t ac = {.unit_id = ADC_UNIT_1};
    if (adc_oneshot_new_unit(&ac, &adc) == ESP_OK) {
        adc_oneshot_chan_cfg_t ch = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
        if (adc_oneshot_config_channel(adc, ADC_CHANNEL_0, &ch) != ESP_OK) { adc_oneshot_del_unit(adc); adc = NULL; }
        adc_cali_curve_fitting_config_t cc = {.unit_id = ADC_UNIT_1, .chan = ADC_CHANNEL_0,
            .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
        if (adc) (void)adc_cali_create_scheme_curve_fitting(&cc, &cali);
    }
    esp_timer_create_args_t timer_args = {.callback = haptic_timeout, .name = "haptic_stop"};
    if (esp_timer_create(&timer_args, &haptic_timer) != ESP_OK) ESP_LOGW(TAG, "Haptic timer unavailable; effects disabled");
    initialized = true; poll_once();
    ESP_LOGI(TAG, "BMI270=%d CAP1296=%d TCA9534=%d; haptic/boost OFF; J7 power-off insertion only",
        status.imu_ready, status.touch_ready, status.expander_ready);
    return ESP_OK; // Optional failed devices remain explicitly unavailable, not fatal.
fail:
    // Critical startup failures release acquired resources; optional-device failures
    // above are degraded status, so callers may safely retry a failed init.
    if (j7_bus) { i2c_del_master_bus(j7_bus); j7_bus = NULL; }
    if (main_bus) { i2c_del_master_bus(main_bus); main_bus = NULL; }
    if (io_lock) { vSemaphoreDelete(io_lock); io_lock = NULL; }
    if (state_lock) { vSemaphoreDelete(state_lock); state_lock = NULL; }
    if (j7_lock) { vSemaphoreDelete(j7_lock); j7_lock = NULL; }
    return err;
}
esp_err_t spirit_peripherals_start(void) {
    if (!initialized) return ESP_ERR_INVALID_STATE;
    if (running) return ESP_OK;
    if (xTaskCreate(task, "spirit_sensors", 6144, NULL, 4, NULL) != pdPASS) return ESP_ERR_NO_MEM;
    running = true; return ESP_OK;
}
esp_err_t spirit_peripherals_get_status(spirit_peripherals_status_t *out) {
    if (!initialized || !out) return ESP_ERR_INVALID_STATE;
    xSemaphoreTake(state_lock, portMAX_DELAY); *out = status; xSemaphoreGive(state_lock); return ESP_OK;
}
esp_err_t spirit_battery_set_divider_ratio(unsigned ratio) {
    if (!initialized || ratio < 1000 || ratio > 10000) return ESP_ERR_INVALID_ARG;
    xSemaphoreTake(io_lock, portMAX_DELAY); divider_ratio = ratio; xSemaphoreGive(io_lock); return ESP_OK;
}
esp_err_t spirit_boost_request(spirit_boost_owner_t owner, bool enabled) {
    if (!initialized) return ESP_ERR_INVALID_STATE;
    if (owner != SPIRIT_BOOST_AUDIO && owner != SPIRIT_BOOST_HAPTIC && owner != SPIRIT_BOOST_MANUAL) return ESP_ERR_INVALID_ARG;
    xSemaphoreTake(io_lock, portMAX_DELAY); boost_locked(owner, enabled); xSemaphoreGive(io_lock);
    return ESP_OK;
}
esp_err_t spirit_boost_set_enabled(bool enabled) { return spirit_boost_request(SPIRIT_BOOST_MANUAL, enabled); }
esp_err_t spirit_haptic_stop(void) {
    if (!initialized) return ESP_ERR_INVALID_STATE;
    xSemaphoreTake(io_lock, portMAX_DELAY);
    if (haptic_timer) (void)esp_timer_stop(haptic_timer);
    if (haptic_configured) (void)wr(drv, 0x0C, 0);
    gpio_set_level(GPIO_NUM_6, 0); haptic_configured = false; haptic_stop_us = 0;
    boost_locked(SPIRIT_BOOST_HAPTIC, false);
    xSemaphoreGive(io_lock); return ESP_OK;
}
static esp_err_t haptic_apply_locked(const spirit_haptic_config_t *c) {
    if (haptic_timer) (void)esp_timer_stop(haptic_timer);
    gpio_set_level(GPIO_NUM_6, 0);
    haptic_configured = false; haptic_stop_us = 0;
    boost_locked(SPIRIT_BOOST_HAPTIC, true);
    vTaskDelay(pdMS_TO_TICKS(5));
    gpio_set_level(GPIO_NUM_6, 1); vTaskDelay(pdMS_TO_TICKS(2));
    uint8_t id = 0;
    esp_err_t err = rd(drv, 0, &id, 1);
    if (err == ESP_OK && (id & 0xE0) != 0xE0) err = ESP_ERR_NOT_SUPPORTED;
    const uint8_t regs[][2] = {{0x01,0},{0x0C,0},{0x03,6},{0x16,c->rated_voltage},{0x17,c->overdrive_clamp},
        {0x1A,c->feedback},{0x1B,c->control1},{0x1C,c->control2},{0x1D,c->control3},
        {0x18,c->autocal_comp},{0x19,c->autocal_bemf}};
    for (unsigned i = 0; err == ESP_OK && i < sizeof(regs)/sizeof(regs[0]); ++i) err = wr(drv, regs[i][0], regs[i][1]);
    if (err == ESP_OK) haptic_configured = true; else { gpio_set_level(GPIO_NUM_6, 0); boost_locked(SPIRIT_BOOST_HAPTIC, false); }
    return err;
}
esp_err_t spirit_haptic_configure(const spirit_haptic_config_t *c) {
    if (!initialized || !c || !c->rated_voltage || !c->overdrive_clamp || !(c->feedback & 0x80) || (c->control3 & 1)) return ESP_ERR_INVALID_ARG;
    xSemaphoreTake(io_lock, portMAX_DELAY);
    esp_err_t err = haptic_apply_locked(c);
    haptic_profile_valid = err == ESP_OK;
    if (haptic_profile_valid) haptic_profile = *c;
    // Configuring never starts GO and need not keep the motor rail energized.
    gpio_set_level(GPIO_NUM_6, 0); haptic_configured = false;
    boost_locked(SPIRIT_BOOST_HAPTIC, false);
    xSemaphoreGive(io_lock); return err;
}
esp_err_t spirit_haptic_play_for(uint8_t effect, uint32_t duration_ms) {
    if (!initialized || !running || !haptic_timer || duration_ms < 1 || duration_ms > 1000 || effect < 1 || effect > 123) return ESP_ERR_INVALID_ARG;
    xSemaphoreTake(io_lock, portMAX_DELAY);
    if (haptic_stop_us && esp_timer_get_time() < haptic_stop_us) { xSemaphoreGive(io_lock); return ESP_ERR_INVALID_STATE; }
    if (haptic_stop_us && esp_timer_get_time() >= haptic_stop_us) haptic_configured = false;
    esp_err_t err = haptic_profile_valid ? ESP_OK : ESP_ERR_INVALID_STATE;
    if (err == ESP_OK && !haptic_configured) err = haptic_apply_locked(&haptic_profile);
    if (err == ESP_OK) err = wr(drv, 4, effect);
    if (err == ESP_OK) err = wr(drv, 5, 0);
    if (err == ESP_OK) {
        (void)esp_timer_stop(haptic_timer);
        haptic_stop_us = esp_timer_get_time() + (int64_t)duration_ms * 1000;
        err = esp_timer_start_once(haptic_timer, (uint64_t)duration_ms * 1000);
    }
    if (err == ESP_OK) err = wr(drv, 0x0C, 1);
    if (err != ESP_OK) { gpio_set_level(GPIO_NUM_6, 0); haptic_profile_valid = false; haptic_configured = false; haptic_stop_us = 0; boost_locked(SPIRIT_BOOST_HAPTIC, false); }
    xSemaphoreGive(io_lock); return err;
}
esp_err_t spirit_haptic_play(uint8_t effect) { return spirit_haptic_play_for(effect, 1000); }
esp_err_t spirit_j7_enable_transport(bool enabled) {
    if (!initialized) return ESP_ERR_INVALID_STATE;
    xSemaphoreTake(j7_lock, portMAX_DELAY); j7_transport_enabled = enabled; xSemaphoreGive(j7_lock);
    return ESP_OK;
}
esp_err_t spirit_j7_transfer(uint8_t addr, const uint8_t *tx, size_t nt, uint8_t *rx, size_t nr) {
    if (!initialized || !j7_bus || addr < 8 || addr > 0x77 || nt > 64 || nr > 64 || (!nt && !nr) || (nt && !tx) || (nr && !rx)) return ESP_ERR_INVALID_ARG;
    spirit_peripherals_status_t s; spirit_peripherals_get_status(&s);
    if (!s.accessory_present_at_boot || !s.accessory_present || s.accessory_changed || gpio_get_level(GPIO_NUM_2)) return ESP_ERR_INVALID_STATE;
    xSemaphoreTake(j7_lock, portMAX_DELAY);
    if (!j7_transport_enabled) { xSemaphoreGive(j7_lock); return ESP_ERR_INVALID_STATE; }
    i2c_master_dev_handle_t dev = NULL; esp_err_t err = add(j7_bus, addr, &dev);
    if (err == ESP_OK) {
        if (nt && nr) err = i2c_master_transmit_receive(dev, tx, nt, rx, nr, 30);
        else if (nt) err = i2c_master_transmit(dev, tx, nt, 30);
        else err = i2c_master_receive(dev, rx, nr, 30);
        i2c_master_bus_rm_device(dev);
    }
    xSemaphoreGive(j7_lock); return err;
}

// Optional PN532 normal frames, per NXP UM0701-02. No reset/IRQ pins are assumed.
static i2c_master_dev_handle_t nfc;
static SemaphoreHandle_t nfc_lock;
static bool nfc_ready;
static esp_err_t pn_wait(int64_t deadline) {
    while (esp_timer_get_time() < deadline) {
        uint8_t ready = 0;
        esp_err_t err = i2c_master_receive(nfc, &ready, 1, 30);
        if (err != ESP_OK) return err;
        if (ready & 1) return ESP_OK;
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    return ESP_ERR_TIMEOUT;
}
static esp_err_t pn_command(uint8_t command, const uint8_t *params, size_t count, uint8_t *response, size_t *response_len) {
    if (count > 16) return ESP_ERR_INVALID_ARG;
    uint8_t frame[25] = {0,0,0xFF};
    frame[3] = (uint8_t)(count + 2); frame[4] = (uint8_t)-frame[3];
    frame[5] = 0xD4; frame[6] = command;
    if (count) memcpy(frame + 7, params, count);
    uint8_t sum = 0;
    for (size_t i = 5; i < count + 7; ++i) sum += frame[i];
    frame[count + 7] = (uint8_t)-sum; frame[count + 8] = 0;
    esp_err_t err = i2c_master_transmit(nfc, frame, count + 9, 30);
    int64_t deadline = esp_timer_get_time() + 700000;
    if (err == ESP_OK) err = pn_wait(deadline);
    uint8_t ack[7]; const uint8_t expected[6] = {0,0,0xFF,0,0xFF,0};
    if (err == ESP_OK) err = i2c_master_receive(nfc, ack, sizeof(ack), 30);
    if (err == ESP_OK && (!(ack[0]&1) || memcmp(ack + 1, expected, 6))) err = ESP_ERR_INVALID_RESPONSE;
    if (err == ESP_OK) err = pn_wait(deadline);
    uint8_t data[80] = {0};
    if (err == ESP_OK) err = i2c_master_receive(nfc, data, sizeof(data), 30);
    if (err != ESP_OK) {
        // Host ACK aborts a pending command; subsequent calls never consume a stale reply.
        (void)i2c_master_transmit(nfc, expected, sizeof(expected), 30);
        return err;
    }
    return spirit_pn532_parse_normal(data, sizeof(data), command, response, response_len)
        ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}
esp_err_t spirit_nfc_init(void) {
    if (!initialized) return ESP_ERR_INVALID_STATE;
    // Initialize once from the application task before concurrent NFC reads.
    if (!nfc_lock) nfc_lock = xSemaphoreCreateMutex();
    if (!nfc_lock) return ESP_ERR_NO_MEM;
    xSemaphoreTake(nfc_lock, portMAX_DELAY);
    esp_err_t err = nfc ? ESP_OK : add(main_bus, 0x24, &nfc);
    nfc_ready = false;
    uint8_t response[64]; size_t len = sizeof(response);
    if (err == ESP_OK) err = pn_command(0x02, NULL, 0, response, &len);
    if (err == ESP_OK && (len != 4 || response[0] != 0x32)) err = ESP_ERR_NOT_SUPPORTED;
    const uint8_t sam[] = {1,0x14,0}; len = sizeof(response);
    if (err == ESP_OK) err = pn_command(0x14, sam, sizeof(sam), response, &len);
    // Bound passive activation retries, avoiding an indefinitely pending scan.
    const uint8_t retry[] = {5,0xFF,1,1}; len = sizeof(response);
    if (err == ESP_OK) err = pn_command(0x32, retry, sizeof(retry), response, &len);
    nfc_ready = err == ESP_OK; xSemaphoreGive(nfc_lock); return err;
}
esp_err_t spirit_nfc_read_uid(uint8_t uid[10], size_t *uid_len) {
    if (!nfc_lock || !uid || !uid_len) return ESP_ERR_INVALID_ARG;
    *uid_len = 0;
    xSemaphoreTake(nfc_lock, portMAX_DELAY);
    if (!nfc_ready) { xSemaphoreGive(nfc_lock); return ESP_ERR_INVALID_STATE; }
    const uint8_t params[] = {1,0}; uint8_t response[64]; size_t len = sizeof(response);
    esp_err_t err = pn_command(0x4A, params, sizeof(params), response, &len);
    if (err == ESP_OK) {
        if (len == 1 && response[0] == 0) err = ESP_ERR_NOT_FOUND;
        else if (len < 6 || response[0] != 1 || response[5] > 10 || response[5] < 4 || len < (size_t)6 + response[5]) err = ESP_ERR_INVALID_RESPONSE;
        else { *uid_len = response[5]; memcpy(uid, response + 6, *uid_len); }
    }
    xSemaphoreGive(nfc_lock); return err;
}
