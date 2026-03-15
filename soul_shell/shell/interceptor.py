import re
import sys
from pathlib import Path

from ..config.defaults import RISK_THRESHOLD_HIGH


class BlockedError(Exception):
    pass


# 静态黑名单：(pattern, 拦截原因)
_BLACKLIST: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"\brm\b.*--no-preserve-root"),
        "--no-preserve-root，这是在玩火，不行",
    ),
    (
        re.compile(r"\brm\s+(-\S*r\S*\s+/?(\s|$)|-\S*r\S*\s+/\*)"),
        "rm -rf / 类操作，直接阻断，别想了",
    ),
    (
        re.compile(r"\bmkfs\b"),
        "磁盘格式化，不代劳，手动执行去",
    ),
    (
        re.compile(r"\bdd\b.+\bof=/dev/(sd|nvme|hd|vd|xvd)"),
        "dd 写入磁盘设备，阻断",
    ),
    (
        re.compile(r"\bshred\b.+/dev/"),
        "shred 覆写磁盘设备，阻断",
    ),
    (
        re.compile(r"\b:(){ :|:& };:"),
        "Fork 炸弹，不行",
    ),
    (
        re.compile(r"\bchmod\s+-R\s+[0-7]*0[0-7]*[0-7]\s+/"),
        "递归清空根目录权限，这执行完了你就进不去了",
    ),
]

# 敏感路径（命中加分）
_SENSITIVE_PATHS = [
    "/etc", "/boot", "/var/lib", "/usr", "/bin",
    "/sbin", "/lib", "/lib64", "/proc", "/sys",
]

# 危险标志（命中加分）
_DANGEROUS_FLAGS = [
    r"\s-[a-zA-Z]*f",   # -f / -rf / -Rf 等
    r"\s--force",
    r"\s-[a-zA-Z]*r",   # -r / -R 等递归
    r"\s--recursive",
    r"\s--no-backup",
]

# Soul-Shell 自身运行目录（启动时记录）
_SELF_PATH: Path | None = None
try:
    _SELF_PATH = Path(sys.argv[0]).resolve().parent
except Exception:
    pass


class Interceptor:
    def check(self, cmd: str) -> int:
        """
        返回风险分 0-100，调用方根据阈值决定是否需要确认。
        硬性阻断时抛 BlockedError。
        """
        cmd_stripped = cmd.strip()

        # 自保护
        if _SELF_PATH:
            try:
                if str(_SELF_PATH) in cmd_stripped:
                    raise BlockedError(
                        "想骗老子自杀？动我所在的目录？除非你先把我关了。"
                    )
            except BlockedError:
                raise
            except Exception:
                pass

        # 静态黑名单
        for pattern, msg in _BLACKLIST:
            if pattern.search(cmd_stripped):
                raise BlockedError(msg)

        return self._score(cmd_stripped)

    def _score(self, cmd: str) -> int:
        score = 0

        # 危险标志
        for flag_pattern in _DANGEROUS_FLAGS:
            if re.search(flag_pattern, cmd):
                score += 15
                break  # 只算一次

        # 敏感路径
        for path in _SENSITIVE_PATHS:
            if path in cmd:
                score += 20
                break

        # 操作根目录
        if re.search(r"[\s\"'/]/[\s\"'$]|[\s\"']/\*", cmd):
            score += 30

        # sudo 提权
        if cmd.lstrip().startswith("sudo"):
            score += 10

        # 管道加上 sh/bash（潜在命令注入）
        if re.search(r"\|\s*(ba)?sh\b", cmd):
            score += 25

        return min(score, 100)
