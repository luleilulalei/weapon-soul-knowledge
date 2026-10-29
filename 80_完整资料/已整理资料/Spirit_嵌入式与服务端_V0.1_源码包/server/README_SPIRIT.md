# Spirit v0.1 服务端（Usaki 增量适配）

这是可在本机启动、以离线替身验证协议的第一版，不是已完成整机联调的产品固件。
保留 `usaki_server` 包名、原 FastAPI/WebSocket、ASR→LLM→TTS 管线和 Opus 语音传输。
默认人格已改为单屏单麦灯光道具中的器灵；不是兔子，也不声称有手臂、耳朵或可驱动的真实武器。

## 启动（实测 Python 3.12，Linux；3.11+为声明支持但未逐版本验证）

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-spirit.lock.txt
cp .env.example .env
python -m uvicorn usaki_server.main:app --host 127.0.0.1 --port 8000
```

Opus 编解码还需要系统 `libopus`（例如 Debian 的 `libopus0`）。默认 RMS VAD 无需下载模型；Silero 和原厂商适配器源码保留，但未做联网验证。
`GET /health` 返回 profile/protocol。默认 STT/LLM/TTS 为本地 stub，**不是真实识别、智能回复或有声合成**。要真实对话，须自行配置原 Usaki provider 和凭据；空白样例不含可用密钥。没有调用任何真实云服务做测试。

### 开发安全边界

默认仅监听本机。整机调试如需 `--host 0.0.0.0`，仅在隔离、可信、无公网转发的开发局域网使用。**v0.1 没有生产认证、授权、TLS、持久设备绑定、防重放会话认证或全局限流**。原 `/device/connect` token 是兼容占位符，不是有效鉴权。不得对公网开放。上线前必须补齐设备身份、TLS、权限和审计。

## 保留的语音接口

`WS /api/v1/voice/voice?device_id=spirit-device-001`，保持原 `voice.input.start/end/cancel`、`voice.output.*` 和二进制 Opus；16 kHz、16 bit、**单声道**、60 ms 帧。
表情事件保留，由单屏固件渲染。Spirit 默认不再输出 `body.action`，也不执行兔子舞蹈脚本。
旧舵机模块可以继续 import，但默认不挂载 `/api/v1/motion`；回归旧设备可显式设置 `USAKI_DEVICE_PROFILE=usaki`。这不是 Spirit 的硬件驱动。

`voice.input.cancel` 的 `reason=privacy_mute/privacy_muted/privacy` 会取消当前服务端处理任务并清空未发送输出；普通带 request_id 的取消不会丢弃其他输入。`voice.interrupt` 也停止任务和排队输出。已经发送的云数据或在途音频无法追回；固件本地麦克风隐私开关才是采集/上传的主闸。隐私麦克风静音不等于必然停止扬声器播放。

## 新设备协议

`WS /api/v1/spirit/device?device_id=spirit-device-001`
所有消息使用 `{id,type,device_id,seq,data}`；seq 为每次连接递增非负 int32。
没有 timestamp 字段；未知字段、错误设备ID、非递增序号、非法字段类型会关闭连接。最多32个在线连接、每帧4096字节。同ID并发连接拒绝。

设备每秒上报 `spirit.telemetry`，字段以 `usaki_server/devices/spirit.py` 为可执行规范：

```json
{"id":"t1","type":"spirit.telemetry","device_id":"spirit-device-001","seq":1,"data":{"protocol":"spirit.v1","uptime_ms":1000,"privacy_muted":false,"imu_valid":false,"battery_valid":false,"battery_pin_mv":-1,"battery_mv":-1,"haptic_ready":false,"blade_ready":false}}
```

可选字段包括 accel_raw/gyro_raw（三个 int16 原始值）、touch_mask、charging/power_good、accessory_present、peripherals_ready/touch_valid/expander_valid、sampled_us/imu_sampled_us、battery_calibrated、docked/usb_present/accessory_changed/bus_errors。有效标志为 false 时，不应把零值/缓存值理解为真实读数。原始 IMU 尚未作姿态融合；电压不是电量百分比。
可选 nfc_uid 仅为4/7/10字节UID十六进制读取，**不是认证、防伪或安全配对**；不写入日志、记忆或 operator state 响应。服务器不把任何遥测送入 LLM。

### 受限效果命令

开发者 HTTP `POST /api/v1/spirit/{device_id}/effects`，示例：

```json
{"command_id":"test-1","effect":"haptic","library_effect":1,"duration_ms":100,"ttl_ms":1000}
```

- effect 只允许 `stop/haptic/blade`；不是任意I2C/GPIO控制。
- library_effect 1..123；duration_ms 1..1000；ttl_ms 100..3000（固件接收开始计时，不依赖时钟同步）。
- haptic 需要3秒内新遥测、haptic_ready=true。默认驱动尚未完成电机额定参数/校准，因此拒绝，而非假装已震动。
- blade 在 v0.1 **始终拒绝**，等待实际从控协议/驱动契约确认。
- 麦克风隐私只控制音频采集/上传，不禁止游戏、震动或灯光；它不是 effects_enabled 开关。
- stop 即使静音/遥测过期仍可发送；它是软件请求，不替代断电急停。
- 每设备单个待确认命令；stop 可以抢占。每会话记住最多1024个命令ID防重复，超过要求重连；固件另有有界去重缓存。不是跨断电安全认证。
- HTTP 202 只表示已发送，不表示硬件执行成功；设备必须回 `spirit.ack`：`{command_id,status:applied|rejected|expired,reason}`。
- `GET /api/v1/spirit/{id}/state` 查看遥测年龄、待确认ID、最后ACK；断开即清除内存状态，不持久化UID。
- LLM 不可发效果；没有语音自动点亮/挥舞/震动映射。

## 已验证（本地无凭据）

在 Python 3.12 临时 venv `/tmp/spirit-server-venv` 中安装 requirements-spirit.txt 对应依赖：

```sh
python -m pytest -q tests/test_spirit.py tests/test_voice_websocket.py
# 25 passed：遥测边界、身份伪造拒绝、校准/过期门禁、麦克风静音不禁用效果、ACK往返、重复命令、
# 单待确认限制、NFC状态脱敏、Spirit不发舵机、处理任务取消、原Opus语音WS。
USAKI_DEVICE_PROFILE=usaki python -m pytest -q -k 'not test_shota_motion_script_shape'
# 71 passed, 1 deselected：兼容模式回归（含新增Spirit测试）。
python -m compileall -q usaki_server
```

完整旧版兼容测试运行曾为 `68 passed, 1 failed`（新增最后3项测试前）。唯一失败是原仓库缺失 `../tools/motion_lab/dances/shota-waist-twist.json` 舞蹈素材，不是补造成功；故后续明确排除该旧素材形状测试。直接以默认Spirit配置运行旧兔子动作/舵机测试不适用，应用上述兼容模式。FastAPI旧 startup 写法及 TestClient 产生 deprecation warnings，未升级架构以降低改动。

尚未验证：真实ESP32与服务端无线往返、真实麦克风/显示/扬声器、电机额定参数校准、blade通信、IMU轴向与标定、电池分压比/SOC、NFC实卡、防伪、断线断电硬件安全、厂商在线ASR/TTS/LLM。不得把本地测试写成硬件验收。

## 清理与沿用

源压缩包由父目录 inputs 保留；交付树删除了真实 `.env` 和原个人 memory/runtime，新增 `.env.example` 只有占位配置，默认不存记忆/不外传。另已通过实际应用 startup、stub providers、`/health`、`/api/v1/device/connect` 离线烟测。

原 README 是历史说明，以本文为Spirit入口。保留原 provider、storage、memory 和旧动作源码供溯源/回退，不代表在Spirit中启用。测试时产生的缓存/数据库不得打入交付。
