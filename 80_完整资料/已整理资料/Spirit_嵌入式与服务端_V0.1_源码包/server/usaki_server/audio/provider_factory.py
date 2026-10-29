from __future__ import annotations

import logging

from usaki_server.agent.profile import build_agent_system_prompt
from usaki_server.audio.providers import (
    HttpLanguageModelProvider,
    HttpSpeechToTextProvider,
    HttpTextToSpeechProvider,
    SilentTextToSpeechProvider,
    SpeechToTextProvider,
    StubLanguageModelProvider,
    StubSpeechToTextProvider,
    TextToSpeechProvider,
    VoiceProviders,
)
from usaki_server.config import Settings
from usaki_server.llm.providers import (
    LLM_PROVIDER_PRESETS,
    LanguageModelProvider,
    OpenAICompatibleLanguageModelProvider,
)
from usaki_server.memory import MemoryAugmentedLanguageModelProvider, create_agent_memory_store

logger = logging.getLogger(__name__)


def create_voice_providers(settings: Settings) -> VoiceProviders:
    stt = create_speech_to_text_provider(settings)
    llm = create_language_model_provider(settings)
    tts = create_text_to_speech_provider(settings)
    logger.warning(
        "[USAKI DIAG] voice providers: stt=%s llm=%s tts=%s",
        type(stt).__name__,
        type(llm).__name__,
        type(tts).__name__,
    )
    return VoiceProviders(stt=stt, llm=llm, tts=tts)


def create_speech_to_text_provider(settings: Settings) -> SpeechToTextProvider:
    if xfyun_realtime_asr_enabled(settings):
        from usaki_server.audio.xfyun_realtime_asr import (
            XfyunRealtimeAsrConfig,
            XfyunRealtimeSpeechToTextProvider,
        )

        assert settings.xfyun_realtime_asr_app_id is not None
        assert settings.xfyun_realtime_asr_api_key is not None
        assert settings.xfyun_realtime_asr_api_secret is not None
        logger.warning(
            "[USAKI DIAG] using XfyunRealtimeSpeechToTextProvider"
        )
        return XfyunRealtimeSpeechToTextProvider(
            XfyunRealtimeAsrConfig(
                app_id=settings.xfyun_realtime_asr_app_id,
                api_key=settings.xfyun_realtime_asr_api_key,
                api_secret=settings.xfyun_realtime_asr_api_secret,
                host=settings.xfyun_realtime_asr_host,
                path=settings.xfyun_realtime_asr_path,
                language=settings.xfyun_realtime_asr_language,
                domain=settings.xfyun_realtime_asr_domain,
                accent=settings.xfyun_realtime_asr_accent,
                vad_eos_ms=settings.xfyun_realtime_asr_vad_eos_ms,
            )
        )
    if settings.stt_http_url:
        logger.warning("[USAKI DIAG] using HttpSpeechToTextProvider url=%s", settings.stt_http_url)
        return HttpSpeechToTextProvider(settings.stt_http_url, settings.stt_http_api_key)
    logger.warning("[USAKI DIAG] using StubSpeechToTextProvider (no real STT configured)")
    return StubSpeechToTextProvider()


def create_language_model_provider(settings: Settings) -> LanguageModelProvider:
    openai_compatible_llm = create_openai_compatible_language_model_provider(settings)
    if openai_compatible_llm is not None:
        return _with_memory_if_enabled(settings, openai_compatible_llm)
    if settings.llm_http_url:
        logger.warning("[USAKI DIAG] using HttpLanguageModelProvider url=%s", settings.llm_http_url)
        return _with_memory_if_enabled(
            settings,
            HttpLanguageModelProvider(settings.llm_http_url, settings.llm_http_api_key),
        )
    logger.warning("[USAKI DIAG] using StubLanguageModelProvider (no real LLM configured)")
    return _with_memory_if_enabled(settings, StubLanguageModelProvider())


def create_openai_compatible_language_model_provider(
    settings: Settings,
) -> LanguageModelProvider | None:
    provider_name = settings.llm_provider.strip().lower()
    if provider_name in {"", "stub", "none", "http"}:
        return None

    preset = LLM_PROVIDER_PRESETS.get(provider_name)
    base_url = settings.llm_base_url or (preset.base_url if preset else None)
    model = settings.llm_model or (preset.model if preset else None)
    api_key = settings.llm_api_key or settings.llm_http_api_key

    if not base_url or not model or not api_key:
        missing = []
        if not base_url:
            missing.append("USAKI_LLM_BASE_URL")
        if not model:
            missing.append("USAKI_LLM_MODEL")
        if not api_key:
            missing.append("USAKI_LLM_API_KEY")
        raise ValueError(
            f"LLM provider '{settings.llm_provider}' is enabled but missing: {', '.join(missing)}"
        )

    logger.warning(
        "[USAKI DIAG] using OpenAICompatibleLanguageModelProvider provider=%s base_url=%s model=%s",
        provider_name, base_url, model,
    )
    system_prompt = build_agent_system_prompt(settings.llm_system_prompt, settings.agent_root)
    logger.warning(
        "[USAKI DIAG] llm system prompt built chars=%d base_prompt_chars=%d",
        len(system_prompt),
        len(settings.llm_system_prompt),
    )
    return OpenAICompatibleLanguageModelProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        system_prompt=system_prompt,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
        thinking_type=settings.llm_thinking_type,
        reasoning_effort=settings.llm_reasoning_effort,
    )


def _with_memory_if_enabled(
    settings: Settings,
    provider: LanguageModelProvider,
) -> LanguageModelProvider:
    if not settings.memory_enabled:
        return provider

    logger.warning(
        "[USAKI DIAG] memory enabled agent_id=%s share_with_llm=%s",
        settings.agent_id,
        settings.memory_share_with_llm,
    )
    return MemoryAugmentedLanguageModelProvider(
        provider,
        create_agent_memory_store(settings),
        share_context_with_llm=settings.memory_share_with_llm,
    )


def create_text_to_speech_provider(settings: Settings) -> TextToSpeechProvider:
    if xfyun_tts_enabled(settings):
        from usaki_server.audio.xfyun_tts import XfyunTextToSpeechProvider, XfyunTtsConfig

        assert settings.xfyun_tts_app_id is not None
        assert settings.xfyun_tts_api_key is not None
        assert settings.xfyun_tts_api_secret is not None
        logger.warning("[USAKI DIAG] using XfyunTextToSpeechProvider")
        return XfyunTextToSpeechProvider(
            XfyunTtsConfig(
                app_id=settings.xfyun_tts_app_id,
                api_key=settings.xfyun_tts_api_key,
                api_secret=settings.xfyun_tts_api_secret,
                host=settings.xfyun_tts_host,
                voice_name=settings.xfyun_tts_voice_name,
                speed=settings.xfyun_tts_speed,
                volume=settings.xfyun_tts_volume,
                pitch=settings.xfyun_tts_pitch,
                background_sound=settings.xfyun_tts_background_sound,
                timeout_seconds=settings.xfyun_tts_timeout_seconds,
            )
        )
    if settings.tts_http_url:
        logger.warning("[USAKI DIAG] using HttpTextToSpeechProvider url=%s", settings.tts_http_url)
        return HttpTextToSpeechProvider(settings.tts_http_url, settings.tts_http_api_key)
    logger.warning("[USAKI DIAG] using SilentTextToSpeechProvider (no real TTS configured)")
    return SilentTextToSpeechProvider()


def tts_provider_mode(settings: Settings) -> str:
    return "xfyun_tts" if xfyun_tts_enabled(settings) else "silent_or_http"


def xfyun_realtime_asr_enabled(settings: Settings) -> bool:
    if settings.stt_provider.lower() not in {"auto", "xfyun", "xfyun_realtime_asr", "xfyun_iat"}:
        logger.warning(
            "[USAKI DIAG] xfyun_realtime_asr_enabled: stt_provider=%s does not match xfyun patterns",
            settings.stt_provider,
        )
        return False
    result = bool(
        settings.xfyun_realtime_asr_app_id
        and settings.xfyun_realtime_asr_api_key
        and settings.xfyun_realtime_asr_api_secret
    )
    logger.warning("[USAKI DIAG] xfyun_realtime_asr_enabled=%s", result)
    return result


def xfyun_tts_enabled(settings: Settings) -> bool:
    if settings.tts_provider.lower() not in {"auto", "xfyun", "xfyun_tts"}:
        return False
    return bool(
        settings.xfyun_tts_app_id
        and settings.xfyun_tts_api_key
        and settings.xfyun_tts_api_secret
    )
