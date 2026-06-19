"""API key filtering tests.

Placeholder keys in .env must not be treated as configured providers. This keeps
/health and the dialog pipeline from calling fake Grok/Gemini/OpenAI keys.
"""

from backend.orchestrator.session import get_api_keys, is_real_api_key


def test_placeholder_keys_are_not_real():
    placeholders = [
        "xai-your-grok-key-here",
        "AIza-your-gemini-key-here",
        "sk-your-openai-key-here",
        "your-key-here",
        "placeholder",
        "changeme",
        "example",
        "sk-...",
        "",
        "   ",
        None,
    ]
    assert all(not is_real_api_key(value) for value in placeholders)


def test_real_looking_keys_are_real():
    assert is_real_api_key("sk-ant-api03-real-looking-token")
    assert is_real_api_key("sk-proj-real-looking-openai-token")
    assert is_real_api_key("xai-real-looking-token")
    assert is_real_api_key("AIzaSyRealLookingGoogleToken")


def test_get_api_keys_ignores_placeholders(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-real-looking-token")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-real-looking-openai-token")
    monkeypatch.setenv("XAI_API_KEY", "xai-your-grok-key-here")
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza-your-gemini-key-here")

    keys = get_api_keys()

    assert list(keys.keys()) == ["claude", "chatgpt"]
    assert "grok" not in keys
    assert "gemini" not in keys


def test_get_api_keys_ignores_empty_values(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    monkeypatch.setenv("XAI_API_KEY", "placeholder")
    monkeypatch.setenv("GOOGLE_API_KEY", "changeme")

    assert get_api_keys() == {}
