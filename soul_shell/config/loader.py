import tomllib
from .defaults import (
    CONFIG_FILE,
    MAX_SHELL_LOG, SHELL_CONTEXT_INJECT, SOUL_REACT_PROBABILITY,
    MAX_HISTORY_TURNS, RISK_THRESHOLD_HIGH, AUTO_MAX_ITERATIONS,
    CMD_OUTPUT_MAX_CHARS,
)


def _load_toml() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def load_channels_raw() -> list[dict]:
    return _load_toml().get("channels", [])


def load_settings() -> dict:
    """
    读取 channels.toml 中的 [settings] 表，缺失项回落到 defaults.py 的默认值。

    可配置项示例（channels.toml）：
        [settings]
        shell_log_size       = 500    # 本地缓冲区大小
        shell_context_inject = 30     # 注入 AI 的条数
        react_probability    = 0.20   # 成功命令触发点评概率 (0.0~1.0)
        max_history_turns    = 30     # 对话历史轮数
        risk_threshold       = 60     # 高风险命令阈值 (0~100)
        cmd_output_max_chars = 2000   # AI 执行命令后反馈给它的输出最大字符数
    """
    raw = _load_toml().get("settings", {})
    return {
        "shell_log_size":      int(raw.get("shell_log_size",      MAX_SHELL_LOG)),
        "shell_context_inject": int(raw.get("shell_context_inject", SHELL_CONTEXT_INJECT)),
        "react_probability":   float(raw.get("react_probability",  SOUL_REACT_PROBABILITY)),
        "max_history_turns":   int(raw.get("max_history_turns",   MAX_HISTORY_TURNS)),
        "risk_threshold":      int(raw.get("risk_threshold",      RISK_THRESHOLD_HIGH)),
        "auto_max_iterations": int(raw.get("auto_max_iterations", AUTO_MAX_ITERATIONS)),
        "cmd_output_max_chars": raw.get("cmd_output_max_chars", CMD_OUTPUT_MAX_CHARS),
    }


CONFIG_EXAMPLE = """\
# Soul-Shell 配置文件
# 保存至 ~/.config/soul-shell/channels.toml

# ── 行为设置（可选，不写则用默认值）──────────────────────────────────
# [settings]
# shell_log_size       = 200    # 本地命令日志缓冲区大小（条）
# shell_context_inject = 20     # 每次注入 AI 上下文的命令条数
# react_probability    = 0.30   # 命令成功时 Soul 点评概率 (0.0 ~ 1.0)
# max_history_turns    = 20     # 对话历史最大轮数
# risk_threshold       = 70     # 高风险命令确认阈值 (0 ~ 100)
# auto_max_iterations  = 10     # 连续模式最大自动执行轮数
# cmd_output_max_chars = 1500   # AI 执行命令后反馈的输出最大字符数（None 则不截断）

# ── 渠道配置（至少填一个）───────────────────────────────────────────

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
