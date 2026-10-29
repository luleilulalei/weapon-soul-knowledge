# 源码变更清单

以用户提供的两个原始 ZIP 为基线，比较文件字节摘要。不包含构建缓存、运行数据或凭据内容。

## firmware
新增 32，修改 24，原始文件未纳入交付 0。

### 新增
- `BUILD_RESULT.md`
- `README_SPIRIT.md`
- `dependencies.lock`
- `src/app/spirit_link.cc`
- `src/app/spirit_link.h`
- `src/app/spirit_privacy.cc`
- `src/app/spirit_privacy.h`
- `src/drivers/spirit_pdm.c`
- `src/drivers/spirit_pdm.h`
- `src/spirit_peripherals/MOTOR_LD0825BC_0169F.md`
- `src/spirit_peripherals/README.md`
- `src/spirit_peripherals/pn532_frame.h`
- `src/spirit_peripherals/spirit_peripherals.c`
- `src/spirit_peripherals/spirit_peripherals.h`
- `src/spirit_peripherals/tests/test_pn532_frame.c`
- `src/spirit_peripherals/vendor/bmi270/LICENSE`
- `src/spirit_peripherals/vendor/bmi270/SHA256SUMS`
- `src/spirit_peripherals/vendor/bmi270/bmi2.c`
- `src/spirit_peripherals/vendor/bmi270/bmi2.h`
- `src/spirit_peripherals/vendor/bmi270/bmi270.c`
- `src/spirit_peripherals/vendor/bmi270/bmi270.h`
- `src/spirit_peripherals/vendor/bmi270/bmi2_defs.h`
- `tests/privacy_stubs/esp_err.h`
- `tests/privacy_stubs/nvs.h`
- `tests/run_host_tests.sh`
- `tests/test_privacy.cc`
- `validation/default-artifact-sha256.txt`
- `validation/idf-submodules.txt`
- `validation/network-artifact-sha256.txt`
- `validation/python-build-requirements.lock.txt`
- `validation/validated-source-sha256.txt`
- `开始使用_Spirit_v0.1.md`

### 修改
- `CMakeLists.txt`
- `sdkconfig.defaults`
- `src/CMakeLists.txt`
- `src/Kconfig`
- `src/app/protocol.c`
- `src/app/robot.cpp`
- `src/app/server_call.c`
- `src/app/voice_protocol_adapter.cc`
- `src/app/voice_protocol_adapter.h`
- `src/app/voice_runtime.cc`
- `src/app/voice_runtime.h`
- `src/app/wifi_station.c`
- `src/audio/audio_codec.cc`
- `src/audio/audio_service.cc`
- `src/audio/audio_service.h`
- `src/audio/codecs/usaki_audio_codec.cc`
- `src/audio/codecs/usaki_audio_codec.h`
- `src/audio/processors/no_audio_processor.cc`
- `src/audio/processors/no_audio_processor.h`
- `src/board/usaki_board.h`
- `src/drivers/max98357a.c`
- `src/idf_component.yml`
- `src/main.cpp`
- `src/ui/usaki_eyes.c`

### 未纳入（删除或交付过滤）

## server
新增 8，修改 9，原始文件未纳入交付 11。

### 新增
- `README_SPIRIT.md`
- `VALIDATION.md`
- `requirements-spirit.lock.txt`
- `requirements-spirit.txt`
- `tests/test_spirit.py`
- `usaki_server/agent/spirit/profile/identity.yaml`
- `usaki_server/api/spirit.py`
- `usaki_server/devices/spirit.py`

### 修改
- `.env.example`
- `.gitignore`
- `usaki_server/agent/profile.py`
- `usaki_server/api/device.py`
- `usaki_server/api/model.py`
- `usaki_server/api/voice_input.py`
- `usaki_server/audio/voice_interaction.py`
- `usaki_server/config.py`
- `usaki_server/main.py`

### 未纳入（删除或交付过滤）
- `.env`
- `usaki_server/agent/usaki/memory/episodic/conversations/.gitkeep`
- `usaki_server/agent/usaki/memory/episodic/summaries/.gitkeep`
- `usaki_server/agent/usaki/memory/long_term/corrections.yaml`
- `usaki_server/agent/usaki/memory/long_term/events.yaml`
- `usaki_server/agent/usaki/memory/long_term/people.yaml`
- `usaki_server/agent/usaki/memory/long_term/preferences.yaml`
- `usaki_server/agent/usaki/memory/long_term/self_growth.yaml`
- `usaki_server/agent/usaki/memory/long_term/tasks.yaml`
- `usaki_server/agent/usaki/memory/short_term/.gitkeep`
- `usaki_server/agent/usaki/runtime/.gitkeep`
