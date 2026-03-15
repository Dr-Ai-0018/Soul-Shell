from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "soul-shell"
CONFIG_FILE = CONFIG_DIR / "channels.toml"

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system.md"
USER_PROFILE_FILE = PROMPTS_DIR / "user_profile.md"

DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_STREAM_TIMEOUT = 300.0
MAX_HISTORY_TURNS = 20
RISK_THRESHOLD_HIGH = 70

# Shell 命令日志
MAX_SHELL_LOG = 200          # 本地环形缓冲区大小（条）
SHELL_CONTEXT_INJECT = 20    # 每次注入 AI context 的条数
SOUL_REACT_PROBABILITY = 0.30  # 命令成功时 Soul 点评的触发概率

# 连续执行模式（Agentic Loop）
AUTO_MAX_ITERATIONS = 10     # 最大自动执行轮数
