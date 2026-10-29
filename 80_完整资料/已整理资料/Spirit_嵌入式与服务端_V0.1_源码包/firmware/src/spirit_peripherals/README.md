# Spirit peripheral support v0.1

## Implemented (hardware not yet tested)
- Shared main I2C0: SDA42/SCL41 at 100 kHz. Separate accessory I2C1: SDA38/SCL21 at 100 kHz. Bounded 30 ms transactions; no legacy I2C driver.
- BMI270 0x69: genuine Bosch SensorAPI **v2.86.1**, including required feature-config blob; accel ±8g and gyro ±2000 deg/s configured at 100 Hz, latest data sampled by a ~50 Hz task. Raw signed 16-bit data, timestamps and current validity. INT18 reserved/input; no fabricated quaternion, gesture recognition, FIFO or position estimate.
- CAP1296 0x28: validates device/vendor ID, enables six channels, reads touch bitmask and clears interrupt. Leaves default sensitivity/thresholds for board-specific tuning. IRQ40 is input; polling—not deep sleep wake.
- TCA9534 0x20: all ports input, no polarity inversion. P0 dock, P1 charge, P2 power-good, P6 auxiliary key, all active low. IRQ47 input; polling—not deep sleep wake.
- GPIO39 active-low USB-present. Battery GPIO1/ADC1_CH0 with eFuse curve-fitting calibration when available; reports raw and ADC-pin mV. Nominal battery mV uses 2:1 divider confirmed from V072 S020 netlist R124=100kΩ / R125=100kΩ, Q102 gated by +3V3 through Q103. `spirit_battery_set_divider_ratio()` permits measured ratio override. This is voltage estimation, not a validated battery SOC. No invented percentage, SOC, temperature or charge-current reading.
- DRV2605L 0x5A: safe default EN6 low; explicit `spirit_haptic_configure()` requires motor-specific rated/clamp voltage and previously obtained calibration/control register bytes. Checks chip ID and LRA closed-loop selection; library effects 1..123; 1..1000ms software EN-low timer independent of sensor I2C polling; sensor task subsequently clears GO and releases boost demand. No automatic guessed calibration, no motor driven at boot. Verified profile retained only in RAM after local configure; each explicit play reapplies it after stop/shutdown without auto-starting. Normal stop/timeout does not erase the profile. Hardware/configuration errors invalidate it; local configure is the recovery path. Reboot always clears the profile. `haptic_configured` status means a locally supplied profile is available, not that EN is high. Software watchdog is not a hardware safety cutoff.
- BOOST_EN8 explicitly controlled by API; default OFF. This is a **shared** 5V boost, not entire-device power or independently switched J7 power. `spirit_boost_request(SPIRIT_BOOST_AUDIO, ...)` and HAPTIC/MANUAL bitmask ownership prevent one consumer from shutting off another. Haptic config acquires its demand and stop/error releases it. Core audio owns AUDIO; `spirit_boost_set_enabled` affects only MANUAL demand.
- J7 DET2 boot-state observation; bounded raw I2C transport is disabled by default and requires explicit `spirit_j7_enable_transport(true)`, and only works if accessory was present at boot and no observed DET transition. No sword command protocol was supplied, so none invented. Any observed transition disables transfers until reboot. **Power off before inserting/removing; DET polling is not hotplug protection or independent power isolation.** Very short transitions can be missed.
- Optional PN532 0x24 main bus: explicit opt-in API (not started at boot); checks firmware IC identity, SAM normal mode, bounded passive ISO14443A scan, UID extraction, ACK/checksum/response validation. Polls I2C status—no IRQ/reset assumed. NFC module is still unconfirmed. UID is NOT authentication or safe redemption. Tested only at compile/static-review level, no card test.

## Integration

Sources: `spirit_peripherals.c`, `vendor/bmi270/bmi2.c`, `vendor/bmi270/bmi270.c`.
Dependencies: `esp_driver_i2c`, `esp_driver_gpio`, `esp_adc`, `esp_timer`, `esp_rom`, FreeRTOS.
Call `spirit_peripherals_init()` then `spirit_peripherals_start()`. Init returns success if core buses are usable even when optional sensor probes fail; check individual `*_ready` flags. Read snapshots with `spirit_peripherals_get_status()`, and respect `*_valid` and timestamps. No sensor data is mocked.
Call init sequentially at startup (successful repeats are idempotent; critical failures release acquired resources before returning). Add/remove-device operations and optional NFC init should happen during setup rather than concurrently.

CAP touch values can drive local UI; no fixed body-part meaning is assigned to the six electrodes. Do not call blocking NFC read from the sensor task or time-critical UI/audio callback.

## Still missing / needs board bench

Motor is LD0825BC-0169F (verified 1.2Vrms/240Hz); per-unit calibration still required (see `MOTOR_LD0825BC_0169F.md`); battery measured-divider/curve/loaded-voltage calibration; touch electrode tuning; IMU orientation/mount calibration, fusion and gesture thresholds; actual J7 accessory/light-sword command protocol; NFC module confirmation and antenna test. No BLE/Unity GATT, authorization/card security, FIFO/interrupt pipeline, power-saving wake or OTA here. Pullups and bus electrical integrity need bench verification. No flashing or live services used.

## Sources / licensing

- Bosch files downloaded unchanged from https://github.com/boschsensortec/BMI270_SensorAPI/tree/v2.86.1 ; BSD-3-Clause license retained in `vendor/bmi270/LICENSE`. Hash manifest in same directory.
- CAP1296 register basis: https://ww1.microchip.com/downloads/en/DeviceDoc/00001569B.pdf
- DRV2605L register basis: https://www.ti.com/lit/ds/symlink/drv2605l.pdf
- PN532 framing / commands: https://www.nxp.com/docs/en/user-guide/141520.pdf
- ESP-IDF target API: v5.5.1, ESP32-S3. Build result is reported by core README/build log, not inferred from this documentation.

## Host checks

`tests/test_pn532_frame.c` tests the exact pure parser used by embedded PN532 code:
valid firmware response, every truncation, insufficient output space, wrong command,
bad checksum, busy byte, oversized length and null input. Compiled with GCC
`-std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined` and passed with
`ASAN_OPTIONS=detect_leaks=0` (LeakSanitizer unavailable under the executor's ptrace).
This is parser validation, **not an ESP-IDF firmware build or NFC hardware test**.
