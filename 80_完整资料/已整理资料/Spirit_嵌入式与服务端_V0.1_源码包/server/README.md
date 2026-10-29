# Usaki Server

Python service layer for Usaki soft-hardware coordination.

## Setup

The conda environment is stored inside this project:

```powershell
conda activate D:\code\usaki\usaki_server\.conda
```

Copy the sample environment file if you want local overrides:

```powershell
Copy-Item .env.example .env
```

## Run

```powershell
python -m uvicorn usaki_server.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## SQLite

The server persists device reports to a local SQLite database. Runtime files are intentionally
ignored by git.

Default setting:

```text
USAKI_DB_PATH=data/usaki_server.sqlite3
```

The database and tables are created automatically on service startup.

## Agent Memory

Usaki's static self-description lives under:

```text
usaki_server/agent/usaki
```

The directory contains stable profile YAML files, long-term memory category placeholders,
short-term JSONL conversation storage, episodic logs, policies, and a runtime SQLite database.

Important settings:

```text
USAKI_MEMORY_ENABLED=true
USAKI_MEMORY_DB_PATH=usaki_server/agent/usaki/runtime/memory.sqlite3
USAKI_MEMORY_SHARE_WITH_LLM=false
```

By default the server records and indexes durable memories, but does not send retrieved private
memories to external LLM endpoints. Set `USAKI_MEMORY_SHARE_WITH_LLM=true` only when you
explicitly want the configured LLM provider to receive relevant retrieved memories during chat.

## Device Report

HTTP endpoint:

```text
POST /devices/report
```

Example:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/devices/report `
  -ContentType "application/json" `
  -Body '{"device_id":"usaki-esp32s3-dev-001","state":"booted","firmware_version":"0.1.0","capabilities":["mic","speaker","display","servo"],"metrics":{"free_heap_bytes":123456}}'
```

## Voice WebSocket

Device endpoint:

```text
WS /api/v1/voice/voice
```

The device sends JSON control messages and binary Opus audio frames. Opus is the only
WebSocket voice transport codec. Xfyun realtime ASR large model receives the original
Opus packets directly.

```json
{"id":"msg_1","type":"voice.input.start","device_id":"usaki-esp32s3-dev-001","seq":1,"data":{"codec":"opus","sample_rate":16000,"channels":1,"sample_bits":16,"frame_duration_ms":60}}
```

The server decodes a side-copy of input Opus only for local VAD/RMS checks. STT receives
Opus packets, and TTS audio is encoded back to Opus frames for the device speaker.

- JSON events: `voice.output.start`, `voice.output.end`, and `error`.
- Binary TTS audio: Opus packets at 16 kHz mono, 60 ms per frame.

Provider endpoints are configured with `USAKI_XFYUN_REALTIME_ASR_*`,
`USAKI_LLM_HTTP_URL`, and `USAKI_TTS_HTTP_URL`. When they are unset, the server uses local
stub providers so the transport can be tested before plugging in a vendor.


## LLM Provider

Usaki now supports two LLM integration modes:

1. `USAKI_LLM_HTTP_URL`: the old generic HTTP adapter. The endpoint receives `{"device_id":"...","text":"..."}` and returns `{"text":"..."}`.
2. `USAKI_LLM_PROVIDER`: the recommended OpenAI-compatible adapter. It calls `{base_url}/chat/completions` directly.

Recommended first-stage setup:

```text
USAKI_LLM_PROVIDER=qwen
USAKI_LLM_API_KEY=your-api-key
# Optional overrides. When omitted, provider presets are used.
USAKI_LLM_BASE_URL=
USAKI_LLM_MODEL=
```

Supported provider presets:

| Provider value | Default endpoint | Default model |
| --- | --- | --- |
| `qwen`, `dashscope`, `aliyun` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| `doubao`, `volcengine` | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-seed-1-6-flash-250615` |
| `deepseek` | `https://api.deepseek.com/v1` | `deepseek-chat` |
| `kimi`, `moonshot` | `https://api.moonshot.cn/v1` | `kimi-k2-0711-preview` |
| `zhipu`, `glm` | `https://open.bigmodel.cn/api/paas/v4` | `glm-4.5-flash` |
| `hunyuan`, `tencent` | `https://api.hunyuan.cloud.tencent.com/v1` | `hunyuan-turbos-latest` |
| `minimax` | `https://api.minimax.io/v1` | `MiniMax-M1` |
| `stepfun`, `step` | `https://api.stepfun.com/v1` | `step-2-mini` |

For other OpenAI-compatible vendors, use:

```text
USAKI_LLM_PROVIDER=custom
USAKI_LLM_BASE_URL=https://vendor.example.com/v1
USAKI_LLM_API_KEY=your-api-key
USAKI_LLM_MODEL=vendor-model-name
```

`USAKI_LLM_SYSTEM_PROMPT` contains the default child-friendly Usaki personality prompt and can be overridden in `.env`.

## Initial Scope

- FastAPI HTTP API.
- WebSocket device gateway.
- Device session registry.
- SQLite-backed device report persistence.
- Static Usaki agent profile and SQLite-backed long-term memory.
- Product-level action protocol.
- Later integration points for ASR, TTS, LLM, vision, VAD, AEC, memory, and logs.
