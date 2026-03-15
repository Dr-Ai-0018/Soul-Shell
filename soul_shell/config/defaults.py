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
