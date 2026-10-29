# Spirit firmware build validation

## Environment
- Official ESP-IDF tag: `v5.5.1`
- IDF commit: `fcae32885b0296b32044cb99ecbdc50d98dddb83`
- Recursive submodules checked out at the SDK's recorded revisions (see `validation/idf-submodules.txt`).
- Compiler: `xtensa-esp-elf-gcc (crosstool-NG esp-14.2.0_20241119) 14.2.0`
- CMake 3.30.2; Ninja 1.12.1; Python 3.12.
- Target: `esp32s3`, flash 16 MB, octal PSRAM.
- Direct/transitive component versions recorded in firmware `dependencies.lock`.
- Python package environment recorded in `validation/python-build-requirements.lock.txt`.

## Reproduce the default build
Install the official ESP-IDF `v5.5.1` SDK and its ESP32-S3 toolchain, then export that SDK environment. From this firmware directory:
```sh
idf.py -D IDF_TARGET=esp32s3 build
idf.py size
```
Use a writable `XDG_CACHE_HOME` / `IDF_TOOLS_PATH` if the host's default cache/tool directories are read-only. No global SDK installation is required.

## Status
**PASS — both final integrated configurations compiled and linked, 2026-10-22 UTC.**

| Configuration | App BIN size | 4 MiB app partition remaining | BIN SHA-256 |
|---|---:|---:|---|
| Shipping defaults (offline placeholders) | 608,720 bytes (`0x949d0`) | 85% | `c252f2a11cc21b9f3dbc419e22d66af8b153c770f1f6946912d4414803b4ae2a` |
| Compile-only dummy network configuration | 1,573,040 bytes (`0x1800b0`) | 62% | `5f3ab06cffe0085fed5f8dccabfb700d87e8430dfaf8171a12bdca27fbf02018` |

The default empty SSID enables linker elimination of unreachable networking code. The second build uses a dummy SSID and `127.0.0.1:8000` URLs solely to force full voice/effect code linkage. It was never executed, flashed, or connected to a service. Do not distribute its BIN or sdkconfig as a production configuration.

Both builds include the final `spirit_link`, recursive voice adapter guards, privacy UI, PDM audio, and latest repeated-haptic profile fix. Peripheral source SHA-256: `f323895cc9c09d64896600692858db62c3c9fa48956c6822497bfd8535547fb1`. The final WebSocket raw-event worker removes the library-lock/adapter-lock inversion. `src/app/server_call.c` SHA-256: `80489611ed4c75ed65d5a72c7b5e81fd1e5036d27db07fc90db815b7bcc10981`. All 100 entries in `validation/validated-source-sha256.txt` were regenerated and rechecked successfully at 08:31:06 UTC after both final builds.

Default static DIRAM usage: 114,695 / 341,760 bytes (33.56%). Configured-network static DIRAM: 173,387 / 341,760 bytes (50.73%). These are link-time figures, not runtime heap measurements.

Initial recoverable errors (FreeRTOS include ordering and GCC14 constant-expression pointer warnings) were fixed and rebuilt. No final compile/link errors remain.

To reproduce the second test, copy the default generated sdkconfig to a separate test file, set a dummy nonempty SSID and loopback URLs, then run (same exported SDK environment):
```sh
idf.py -B build-network-test -D SDKCONFIG=sdkconfig.network-test \
  -D IDF_TARGET=esp32s3 build
```
Do not flash this compile-only test configuration.

Full logs and generated binaries are retained in the validation workspace, not shipped in this source archive. Artifact SHA-256 lists in validation/ are for traceability; binaries are not bundled. The generated SDK configs are validation-local only; distribute the source `sdkconfig.defaults` and dependency lock instead.

## Scope / exclusions
- Compilation and linking are not hardware validation.
- No flashing, deployment, push, Wi-Fi connection, or live service call was performed.
- No microphone, screen, battery, haptic, IMU, touch, NFC, or accessory was physically tested.
- Optional AFE/wake-word configurations are not included in the default-build claim.
- Do not distribute SDK, `managed_components/`, build objects, or caches as source deliverables.
