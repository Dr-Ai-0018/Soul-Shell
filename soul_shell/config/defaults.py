from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "soul-shell" 
CONFIG_FILE = CONFIG_DIR / "channels.toml" # 存储用户的渠道配置

ROOT_DIR = Path(__file__).resolve().parents[2] # 获取项目根目录
PROMPTS_DIR = ROOT_DIR / "prompts"
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system.md"
USER_PROFILE_FILE = PROMPTS_DIR / "user_profile.md"

DEFAULT_CONNECT_TIMEOUT = 10.0 # 连接超时时间（秒）
DEFAULT_STREAM_TIMEOUT = 300.0 # 流式响应的默认超时时间（秒），适用于长时间运行的命令
MAX_HISTORY_TURNS = 20 # 与 AI 交互时保留的历史轮数（用户输入 + AI 回复算一轮），超过部分会被丢弃以节省上下文空间
RISK_THRESHOLD_HIGH = 70 # 风险评估的高风险阈值，超过该值的命令会被标记为高风险

# Shell 命令日志
MAX_SHELL_LOG = 200          # 本地环形缓冲区大小（条）
SHELL_CONTEXT_INJECT = 20    # 每次注入 AI context 的条数
SOUL_REACT_PROBABILITY = 0.30  # 命令成功时 Soul 点评的触发概率

# 输出截断限制（None = 不截断）
# 注意：CONTEXT_OUTPUT_MAX_CHARS 影响每次 AI 请求的 prompt 体积，建议保留合理上限
REACT_OUTPUT_MAX_CHARS: "int | None" = None   # react 上下文里 shell 输出的最大字符数
SHELL_LOG_OUTPUT_MAX_CHARS: "int | None" = None  # shell_log 每条 out 字段的最大字符数
CONTEXT_OUTPUT_MAX_CHARS: "int | None" = 150  # 注入 AI context 时每条命令输出的最大字符数

# 连续执行模式（Agentic Loop）
AUTO_MAX_ITERATIONS = 10     # 最大自动执行轮数
