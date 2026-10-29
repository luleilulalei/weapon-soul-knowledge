import pytest

from usaki_server.config import Settings
from usaki_server.llm.providers import (
    LLM_PROVIDER_PRESETS,
    OpenAICompatibleLanguageModelProvider,
)
from usaki_server.audio.provider_factory import create_openai_compatible_language_model_provider


@pytest.mark.parametrize(
    "provider_name",
    ["qwen", "doubao", "deepseek", "kimi", "zhipu", "hunyuan", "minimax", "stepfun"],
)
def test_llm_provider_presets_cover_main_vendors(provider_name: str) -> None:
    preset = LLM_PROVIDER_PRESETS[provider_name]
    assert preset.base_url.startswith("https://")
    assert preset.model


def test_create_openai_compatible_language_model_provider_uses_provider_preset() -> None:
    settings = Settings(_env_file=None, llm_provider="qwen", llm_api_key="test-key")

    provider = create_openai_compatible_language_model_provider(settings)

    assert isinstance(provider, OpenAICompatibleLanguageModelProvider)


def test_create_openai_compatible_language_model_provider_allows_custom_vendor() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="custom",
        llm_base_url="https://llm.example.com/v1",
        llm_api_key="test-key",
        llm_model="custom-chat",
    )

    provider = create_openai_compatible_language_model_provider(settings)

    assert isinstance(provider, OpenAICompatibleLanguageModelProvider)


def test_create_openai_compatible_language_model_provider_returns_none_for_stub() -> None:
    settings = Settings(_env_file=None, llm_provider="stub")

    assert create_openai_compatible_language_model_provider(settings) is None


def test_create_openai_compatible_language_model_provider_fails_fast_when_key_missing() -> None:
    settings = Settings(_env_file=None, llm_provider="deepseek")

    with pytest.raises(ValueError, match="USAKI_LLM_API_KEY"):
        create_openai_compatible_language_model_provider(settings)
