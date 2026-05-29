from backend.app.core.config import Settings


def test_deepseek_is_default_provider():
    settings = Settings(_env_file=None, deepseek_api_key="sk-test")
    assert settings.ai_provider == "deepseek"
    assert settings.resolved_ai_api_base == "https://api.deepseek.com"
    assert settings.resolved_ai_model == "deepseek-chat"
    assert settings.resolved_ai_api_key == "sk-test"


def test_generic_ai_key_overrides_provider_key():
    settings = Settings(
        _env_file=None,
        ai_api_key="sk-generic",
        deepseek_api_key="sk-deepseek",
    )
    assert settings.resolved_ai_api_key == "sk-generic"
