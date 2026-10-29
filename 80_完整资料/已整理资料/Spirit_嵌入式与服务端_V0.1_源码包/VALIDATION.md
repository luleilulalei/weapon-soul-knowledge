# V0.1 验证记录

日期：2026-10-22。这里区分源码/构建/离线协议测试与真实硬件验证。

## 已实际执行

### ESP32-S3 固件

- 官方 ESP-IDF v5.5.1、Xtensa 交叉工具链，执行完整构建及 ELF 链接，不是只过 C/C++ 语法检查。
- 默认无网络凭据配置构建通过。
- 另使用虚构 SSID 与本机地址进行**只编译、不运行**的联网配置构建，避免默认空配置使链接器裁掉语音与网络路径，完整构建通过。
- 最终具体工具链、源文件摘要、镜像大小与构建结论见 `firmware/BUILD_RESULT.md`。本交付以源码为主，不含 SDK/构建缓存，也没有自动执行烧录。
- `cd firmware && bash tests/run_host_tests.sh` 通过。主机端 NVS 替身单元测试覆盖默认静音、持久化、失败关闭、在途上传门控；不等于 ESP32 上的采音测试。
- PN532 实际纯帧解析器的主机测试以 GCC AddressSanitizer/UndefinedBehaviorSanitizer 运行通过，覆盖截断、校验、边界和空输入；没有实卡测试。
- 独立检查并修复了静音上传队列、过期采样、服务端取消、J7 默认门禁、共享升压使用者、退出通知竞争等问题。额外修正了麦克风静音与震动反馈错误耦合，二者保持独立。最终复核还发现并修复了 WebSocket 库内部锁与适配层控制锁的反转：回调现在只深拷贝到有界事件池/零等待队列，工作任务在库锁外处理；源码复审未再发现该阻断，真实压力测试仍未做。

### Python 服务端

在 Python 3.12 离线虚拟环境执行；精确依赖在 `server/requirements-spirit.lock.txt`。

```sh
cd server
python -m pytest -q tests/test_spirit.py tests/test_voice_websocket.py
# 25 passed；3 条第三方/旧 API 弃用警告
USAKI_DEVICE_PROFILE=usaki python -m pytest -q -k 'not test_shota_motion_script_shape'
# 71 passed, 1 deselected
python -m compileall -q usaki_server
# exit 0
```

另做默认 stub provider、FastAPI 启动、health、device-connect 离线烟测。主控与服务端的新遥测/effect JSON 契约已对照检查。服务端最终 focused 测试和固件主机隐私测试还独立重跑了一次，均通过。

**不是全量旧测试绿灯。** 原附件缺少 `tools/motion_lab/dances/shota-waist-twist.json`，旧舞蹈素材形状测试失败，后续兼容回归明确排除了该项；没有造一个文件把失败掩盖掉。Spirit 默认不使用兔子舵机/舞蹈流程。更完整记录见 `server/VALIDATION.md`。

### 交付检查

- 原始附件仅作基线，没有把其中 `.env`、私人记忆、数据库或联网凭据带入源码交付。
- SDK、managed_components、虚拟环境、生成 sdkconfig、构建缓存不纳入。
- 保留固件 `dependencies.lock` 和服务端精确依赖版本。
- ZIP 完整性和文件摘要在打包时检查，包含文件清单 `MANIFEST.json`。

## 没有执行，不能宣称通过

- 真实 PCB 烧录、上电、电源极性/峰值电流、温升、续航、屏幕方向与排线核对。
- 真实麦克风/功放音频质量、声学回声消除、硬件静音；当前只有软件停止采集/上传。
- 实际器灵与服务端无线全链路联调、真实厂商 ASR/LLM/TTS 调用。
- LRA 实物额定参数/校准、BMI270 安装方向/姿态融合、CAP1296 电极调参、电池标定及电量百分比、PN532 实卡与天线。
- 真实剑身从控协议；当前 blade 命令明确不支持，J7 只有默认禁用的安全传输入口。
- OTA 完整工作流、BLE/Unity、生产身份鉴权、防复制卡、低功耗产品策略。

构建成功只是软件交付门槛，不是“可以不检查就上板”或整机功能验收。
