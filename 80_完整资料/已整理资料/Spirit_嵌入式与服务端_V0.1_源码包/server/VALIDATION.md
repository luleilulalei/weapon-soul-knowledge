# Spirit server 本地验证记录

工作目录：`source/usaki_server-master`（相对交付根目录）。
实际 Python：3.12；项目声明支持3.11+，其他版本未测试；临时 venv 位于 `/tmp/spirit-server-venv`，不随包分发。
无真实 `.env`；未读取/使用原密钥。未进行远程推送、部署或真实云 provider 请求。

## 复现

```sh
cd source/usaki_server-master
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-spirit.lock.txt
# 系统需已有 libopus；Linux发行版可用 libopus0。
# 干净shell，勿注入任何真实provider的USAKI_*凭据/URL；不要复制原.env。
python -m pytest -q tests/test_spirit.py tests/test_voice_websocket.py
USAKI_DEVICE_PROFILE=usaki python -m pytest -q -k 'not test_shota_motion_script_shape'
python -m compileall -q usaki_server
```

`requirements-spirit.txt` 是范围约束；`requirements-spirit.lock.txt` 是本次实际 venv 的精确 pip freeze（含测试及传递依赖，非带hash供应链锁）。原 `requirements.txt` 是上游UTF-16文件，Spirit安装入口用新增文件。

## 结果

- 最终 focused（Spirit默认 + 原语音WS）：**25 passed**。
- 最终旧设备兼容模式回归：**71 passed, 1 deselected**。
- `compileall -q usaki_server`：exit 0。
- 应用真实 startup + local stub provider + `/health` + `/api/v1/device/connect` TestClient 烟测：通过。
- 前一检查点为24 focused/70 legacy通过；随后增加 stop 抢占后的迟到ACK回归，避免旧ACK断开连接或清除新stop待确认状态，故各增一项。
- 测试有3条 deprecation warnings（FastAPI startup、TestClient），不是忽略测试失败。

**不是全量绿灯**：完整旧兼容测试最初为68 passed/1 failed（当时尚未增加最后3项测试）；唯一失败 `tests/test_performance_routines.py::test_shota_motion_script_shape` 读取缺失的上游 `../tools/motion_lab/dances/shota-waist-twist.json`。未补造素材，最终命令明确 deselect 此项。默认Spirit不执行旧兔子动作，故旧舵机/兔子断言在兼容模式运行。

最终回归已覆盖麦克风privacy_muted=true时，只要haptic_ready=true且遥测新鲜仍可发送haptic；隐私与效果模式独立。

## 默认配置保证与边界

`Settings()` 默认 llm_provider=stub，所有STT/TTS HTTP URL和Xfyun凭据为空，memory_enabled=false。已启动验证具体 provider 为 StubSpeechToTextProvider、StubLanguageModelProvider、SilentTextToSpeechProvider；不是云端真实对话验证。语音包名和接口保留usaki以兼容原固件。

未验真实板端网络/音频、传感器、电机校准、刀光从控协议、真实NFC、在线ASR/LLM/TTS。协议仅限可信开发网络，没有生产鉴权/TLS。硬件测试和服务器离线测试不能相互替代。
