import pytest
from soul_shell.models.channel import Channel
from soul_shell.models.registry import ModelRegistry


def make_registry() -> ModelRegistry:
    channels = [
        Channel(
            name="deepseek",
            provider="openai",
            base_url="https://api.deepseek.com",
            api_key="sk-x",
            models=["deepseek-chat", "deepseek-reasoner"],
            default_model="deepseek-chat",
        ),
        Channel(
            name="claude",
            provider="anthropic",
            base_url="https://api.anthropic.com",
            api_key="sk-ant",
            models=["claude-sonnet-4-6", "claude-opus-4-6"],
            default_model="claude-sonnet-4-6",
        ),
    ]
    return ModelRegistry(channels)


def test_default_active():
    reg = make_registry()
    assert reg.active is not None
    assert reg.active.channel.name == "deepseek"
    assert reg.active.model_id == "deepseek-chat"


def test_display_name():
    reg = make_registry()
    assert reg.active.display_name == "deepseek/deepseek-chat"


def test_switch_channel():
    reg = make_registry()
    result = reg.switch("claude")
    assert result == "claude/claude-sonnet-4-6"
    assert reg.active.channel.name == "claude"


def test_switch_specific_model():
    reg = make_registry()
    result = reg.switch("deepseek/deepseek-reasoner")
    assert result == "deepseek/deepseek-reasoner"
    assert reg.active.model_id == "deepseek-reasoner"


def test_switch_invalid_channel():
    reg = make_registry()
    with pytest.raises(ValueError, match="不存在"):
        reg.switch("nonexistent")


def test_switch_invalid_model():
    reg = make_registry()
    with pytest.raises(ValueError, match="不在渠道"):
        reg.switch("deepseek/gpt-4o")


def test_list_all_contains_current_marker():
    reg = make_registry()
    listing = reg.list_all()
    assert "← 当前" in listing
    assert "deepseek/deepseek-chat" in listing


def test_empty_registry():
    reg = ModelRegistry([])
    assert reg.active is None
    with pytest.raises(RuntimeError):
        reg.get_adapter()


def test_get_adapter_returns_openai_for_openai_provider():
    reg = make_registry()
    from soul_shell.adapters.openai_compat import OpenAICompatAdapter
    adapter = reg.get_adapter()
    assert isinstance(adapter, OpenAICompatAdapter)


def test_get_adapter_returns_anthropic_after_switch():
    reg = make_registry()
    reg.switch("claude")
    from soul_shell.adapters.anthropic import AnthropicAdapter
    adapter = reg.get_adapter()
    assert isinstance(adapter, AnthropicAdapter)
