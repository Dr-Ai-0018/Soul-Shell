import tomllib
from .defaults import CONFIG_FILE


def load_channels_raw() -> list[dict]:
    if not CONFIG_FILE.exists():
        return []
    with open(CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)
    return data.get("channels", [])


CONFIG_EXAMPLE = """\
# Soul-Shell 渠道配置示例
# 保存至 ~/.config/soul-shell/channels.toml

[[channels]]
name = "deepseek"
provider = "openai"
base_url = "https://api.deepseek.com"
api_key = "sk-你的key"
models = ["deepseek-chat"]
default_model = "deepseek-chat"

# [[channels]]
# name = "local-ollama"
# provider = "openai"
# base_url = "http://localhost:11434"
# api_key = ""
# models = ["qwen2.5:7b"]
# default_model = "qwen2.5:7b"

# [[channels]]
# name = "claude"
# provider = "anthropic"
# base_url = "https://api.anthropic.com"
# api_key = "sk-ant-你的key"
# models = ["claude-sonnet-4-6"]
# default_model = "claude-sonnet-4-6"

# [[channels]]
# name = "gemini"
# provider = "gemini"
# base_url = "https://generativelanguage.googleapis.com"
# api_key = "AIza你的key"
# models = ["gemini-2.0-flash"]
# default_model = "gemini-2.0-flash"
"""
