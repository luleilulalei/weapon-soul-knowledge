# Spirit firmware v0.1 — adapted from supplied Usaki ESP-IDF source

## Scope / safety

This is a source adaptation for ESP32-S3-WROOM-1-N16R8, **not a hardware-qualified release**. No board has been flashed. The supplied voice protocol, Opus codec pipeline, MAX98357A driver, GC9A01 driver and animated-eye UI are reused. Original servo/motion/MPR121/dual-mic sources remain for provenance but are **excluded from the active build**; server `body.action` is explicitly rejected rather than driving nonexistent servos.

The supplied inputs are not modified; this working tree is the adaptation. Credentials and private LAN addresses in the active board defaults have been replaced. Do not share a generated `sdkconfig` after entering credentials.

## Build

Pinned SDK: **ESP-IDF v5.5.1**, target `esp32s3`, 16 MB QIO flash, 8 MB octal PSRAM. Exact direct component versions are in `src/idf_component.yml`; transitive versions are resolved by IDF Component Manager. The existing factory/model/storage partition map is retained; **OTA/rollback is not implemented**.

```sh
. /path/to/esp-idf/export.sh
idf.py set-target esp32s3
idf.py menuconfig   # Spirit v0.1 configuration: SSID/password/device ID/server URLs
idf.py build
# Only on a physically verified board and with user authorization:
# idf.py -p PORT flash monitor
```

Without SSID/server configuration the device boots local UI/peripherals and does not attempt a server connection. URLs are placeholders. HTTP/WS are suitable only for a trusted isolated development LAN; HTTPS/WSS use the ESP certificate bundle. Provisioning, production authentication/identity, key rotation and OTA remain future work. Never put server-provider API keys in device firmware.

## Active pin mapping

| Function | GPIO |
|---|---|
| One GC9A01: DC / CS / MOSI / SCK / RESET / backlight | 9 / 10 / 11 / 12 / 13 / 48 |
| One LMD3526T261-OA5 PDM: DATA / CLK | 4 / 5 (I2S0 RX, 16 kHz PCM mono) |
| MAX98357A: BCLK / LRCLK / DOUT / enable | 7 / 15 / 16 / 17 (I2S1 TX) |
| Main I2C: SCL / SDA | 41 / 42 |
| BMI270 INT / CAP1296 IRQ / TCA9534 IRQ | 18 / 40 / 47 |
| DRV2605L enable / boost enable | 6 / 8 |
| Battery ADC / USB present active-low | 1 / 39 |
| User key / boot | 14 / 0 |
| J7 I2C: SCL / SDA / detect active-low | 21 / 38 / 2 |
| Native USB / UART TX,RX | 19,20 / 43,44 (reserved) |

GPIO38 is **not** IMU interrupt. The LCD right-display branch is disabled; existing one-eye rendering is retained, not a new full Spirit art design. Backlight is on/off, not PWM brightness yet. The PDM microphone L/R is grounded in the supplied netlist; verify PCM sign/amplitude and clock edge on the real PCB.

## Interaction and privacy

- First boot defaults **microphone muted**. Hold KEY14 for 1.5 seconds to toggle persistent software privacy; 30 ms debounce. NVS failures fail closed in the current session and are logged. Do not erase NVS automatically to recover a boot error: this would discard privacy state. If a mute write fails, power-cycle persistence cannot be promised until storage is repaired.
- When unmuted, short-press KEY14 to start a manual input turn; short-press again to send `voice.input.end`. Server playback is half-duplex. Reconnect and playback completion do not automatically open another turn. There is no timeout-based endpoint in default manual mode: explicitly end the turn with the key. During playback a short press interrupts output rather than opening the microphone. The display has an independent MIC MUTED / MIC READY / LISTENING badge; hardware visual validation is still required.
- PDM RX is disabled when not processing/waking; privacy additionally blocks processor/wake activation, serializes against capture reads and binary uploads, and discards queued/in-flight-generation audio. Already transmitted data cannot be recalled. Unmuting does not itself start capture/upload.
- This is **not a physical microphone disconnect**: the microphone remains powered. No mode transition, touch, server response or reconnect can override privacy mute. No GPIO40/47 deep-sleep-wakeup assumptions are used.
- Default build uses the original pass-through processor + Opus, with actual manual `voice.input.start` signaling. Optional ESP-SR AFE/WakeNet sources are retained behind menuconfig, but models, thresholds, acoustic tuning and optional-path lifecycle require separate validation. No claim of far-field/full-duplex/AEC support is made.

## Peripherals / remaining work

See `src/spirit_peripherals/README.md` for implemented register transactions, Bosch BMI270 integration, calibration and missing capabilities. Sensor absence is a local degradation, not permission to fabricate readings. J7 shares the system rails: **power off before insertion/removal**; detection is not independent power protection. NFC hardware and card security are unconfirmed. Read UID is not authentication. Battery millivolts use the confirmed nominal divider ratio from the netlist; this is not an accurate state-of-charge gauge without board calibration. Do not energize a motor before its rated voltage and clamp parameters are confirmed.

Not implemented: Unity/BLE GATT, OTA, provisioning portal, production credentials, calibrated battery percentage, real-time temperature, absolute motion tracking, complete sword/lighting accessory protocol, secure NFC redemption, production sleep/wake power policy. Core ignores Usaki servo `body.action`; new peripheral actions must use explicitly defined bounded commands.

## Verification

- `tests/run_host_tests.sh`: actual privacy-policy C++ compiled with host-only NVS test doubles. Checks default mute, persisted mute/unmute, NVS failures, and waiting for in-flight upload gate. **Pass**. This is not an ESP32 build or hardware test.
- Full SDK build: default and configured-network variants passed; see the delivery’s `build-validation/` and final validation status below.
- Hardware tests: **not run** (no board). Required before flashing/release: rail polarity/voltage, LCD orientation, mono PDM edge/amplitude, amp shutdown/pop behavior, sensor IDs, battery divider/calibration, interrupt polarity, microphone mute during output/reconnect/mode changes/reboot and NVS failure, J7 power-off handling, real server round trip, heap/stack and Wi-Fi/audio load.

### Residual engineering limits
Raw voice WebSocket callbacks now deep-copy bounded events (including fragment metadata) into an eight-item pool/queue without waiting for adapter locks. A dedicated worker processes them outside the WebSocket client lock. Session generations discard stale queued events; overflow cancels local turn state and reconnects from the worker. Producer stop, worker join and pool release are ordered. This resolves the lock-order inversion found by the final static review; target overflow/reconnect stress remains untested.

The voice adapter now serializes turn-control state across key/runtime, sender and WebSocket callbacks with one recursive control/send mutex; an atomic initialization barrier protects runtime startup. Privacy has a separate immediate-intent/epoch/gated boundary. Rapid start/stop/disconnect and queue-pressure stress tests are still required before production. Optional AFE paths are retained, not qualified. Sensor polling and UI rates are starting values, not latency/power guarantees.

### Spirit telemetry/effect channel
Configure `SPIRIT_EFFECT_URL` separately from voice. `spirit_link` sends actual 1 Hz status snapshots with validity flags over `/api/v1/spirit/device`, and accepts bounded `spirit.effect` commands with acknowledgments, arrival-relative TTL and an eight-entry recent-command cache. `stop` is implemented; `haptic` requires locally supplied calibrated motor configuration and a 1..1000 ms independent safety timer; `blade` returns rejected because no sword packet/electrical contract was supplied. No arbitrary I2C/GPIO or remote unmute is exposed. Cache is not persistent across reboot. This development channel is not a production-authenticated control plane.

### Current build evidence (2026-10-22)
Both **full ESP-IDF v5.5.1 cross-builds and links passed**:

| Build | BIN bytes | Scope |
|---|---:|---|
| Default/offline | 608,720 | Empty credentials/placeholders; local boot defaults |
| Configured-network compile-only | 1,573,040 | Dummy SSID + localhost URLs retain and link voice/network/effect paths |

Final exact commands, ELF/BIN SHA256, dependency lock, size reports and source hash manifest are in the delivery's `build-validation/` directory. The 100-entry compiled source manifest was rechecked successfully at 08:31:06 UTC. The configured build was **not executed or connected**. Both images fit the retained 4 MiB factory partition. Static RAM figures do not prove runtime heap/stack sufficiency.

Host privacy-policy tests and the exact PN532 frame parser's GCC ASan/UBSan checks were independently rerun successfully on 2026-10-22. No firmware has been flashed, no real Wi-Fi/server session opened, and no motor energized by this work. Optional AFE/WakeNet configurations and hardware remain untested.
