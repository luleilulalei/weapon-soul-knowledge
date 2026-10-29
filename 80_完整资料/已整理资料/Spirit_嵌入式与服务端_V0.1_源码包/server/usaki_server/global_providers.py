from __future__ import annotations

import logging

from usaki_server.audio.providers import VoiceProviders

logger = logging.getLogger(__name__)

_voice_providers: VoiceProviders | None = None


def set_voice_providers(providers: VoiceProviders) -> None:
    global _voice_providers
    _voice_providers = providers
    logger.warning(
        "[USAKI DIAG] global voice providers set: stt=%s llm=%s tts=%s",
        type(_voice_providers.stt).__name__,
        type(_voice_providers.llm).__name__,
        type(_voice_providers.tts).__name__,
    )


def get_voice_providers() -> VoiceProviders:
    assert _voice_providers is not None, "voice providers not initialized"
    return _voice_providers