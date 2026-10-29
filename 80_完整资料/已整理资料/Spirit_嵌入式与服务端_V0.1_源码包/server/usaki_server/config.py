from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    server_name: str = "spirit-server"
    device_profile: str = "spirit"
    env: str = "dev"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"

    db_path: str = "data/usaki_server.sqlite3"

    agent_id: str = "spirit"
    agent_root: str = "usaki_server/agent/spirit"
    memory_enabled: bool = False
    memory_db_path: str = "usaki_server/agent/spirit/runtime/memory.sqlite3"
    memory_recent_window_minutes: int = 10
    memory_max_context_items: int = 8
    memory_query_pool_size: int = 100
    memory_share_with_llm: bool = False

    audio_sample_rate_hz: int = 16000
    audio_vad_provider: str = "rms"
    audio_vad_model_path: Optional[str] = None
    audio_vad_threshold: float = 0.5
    audio_vad_threshold_low: float = 0.3
    audio_vad_min_silence_duration_ms: int = 200
    audio_vad_frame_window_threshold: int = 3
    audio_server_vad_auto_end: bool = False
    audio_server_vad_auto_end_min_input_ms: int = 1200
    audio_silence_rms_threshold: int = 350
    audio_silence_timeout_ms: int = 900
    audio_max_utterance_ms: int = 12000

    stt_provider: str = "auto"
    stt_http_url: Optional[str] = None
    stt_http_api_key: Optional[str] = None
    xfyun_realtime_asr_app_id: Optional[str] = None
    xfyun_realtime_asr_api_key: Optional[str] = None
    xfyun_realtime_asr_api_secret: Optional[str] = None
    xfyun_realtime_asr_host: str = "iat.cn-huabei-1.xf-yun.com"
    xfyun_realtime_asr_path: str = "/v1"
    xfyun_realtime_asr_language: str = "zh_cn"
    xfyun_realtime_asr_domain: str = "slm"
    xfyun_realtime_asr_accent: str = "mandarin"
    xfyun_realtime_asr_vad_eos_ms: int = 3000

    # Backward-compatible generic HTTP LLM adapter.
    llm_http_url: Optional[str] = None
    llm_http_api_key: Optional[str] = None
    # OpenAI-compatible LLM adapter. Supported presets include:
    # qwen/dashscope/aliyun, doubao/volcengine, deepseek, kimi/moonshot,
    # zhipu/glm, hunyuan/tencent, minimax, stepfun/step.
    llm_provider: str = "stub"
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: float = 0.7
    llm_max_tokens: int = 512
    llm_timeout_seconds: float = 30
    llm_thinking_type: Optional[str] = None
    llm_reasoning_effort: Optional[str] = None
    llm_system_prompt: str = (
        "你是 Spirit，寄宿在单屏单麦光剑道具中的器灵伙伴。你没有兔耳、手臂、底座或舵机。光剑仅为灯光道具，不是真实武器。不要声称已经执行硬件动作或认证 NFC。"
        "你温暖、外向、敏锐、会照顾人的情绪，也会主动把事情讲清楚、陪用户一起完成小目标。"
        "请用自然、简短、积极、适合语音播放的中文回答，像可靠又有亲和力的陪伴者，而不是冷冰冰的工具。"
        "先给一句不超过12个汉字的自然短回应，并以标点结束，再补充必要内容。"
        "不要输出暴力、成人、危险操作、隐私诱导，或医疗/法律/金融定论。"
        "如果用户表达危险、受伤或强烈负面情绪，请温柔建议马上找可信任的人帮助。"
    )

    tts_provider: str = "auto"
    tts_http_url: Optional[str] = None
    tts_http_api_key: Optional[str] = None
    xfyun_tts_app_id: Optional[str] = None
    xfyun_tts_api_key: Optional[str] = None
    xfyun_tts_api_secret: Optional[str] = None
    xfyun_tts_host: str = "tts-api.xfyun.cn"
    xfyun_tts_voice_name: str = "x4_yezi"
    xfyun_tts_speed: int = 48
    xfyun_tts_volume: int = 50
    xfyun_tts_pitch: int = 60
    xfyun_tts_background_sound: int = 0
    xfyun_tts_timeout_seconds: float = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="USAKI_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
