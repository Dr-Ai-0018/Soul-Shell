import sys

# pty 是 Unix-only 模块
if sys.platform == "win32":
    raise RuntimeError(
        "Soul-Shell 需要 Linux 或 macOS 环境，Windows 不支持 pty。\n"
        "建议在 WSL2 中运行。"
    )

import os
import select


class PtyHost:
    """
    启动子 bash，通过 pty 伪终端接管其 stdin/stdout。
    MVP 模式：行级命令写入 + 非阻塞批量读取。
    """

    def __init__(self):
        self._master_fd: int | None = None
        self._pid: int | None = None

    def spawn(self, shell: str = "bash") -> None:
        import pty
        self._pid, self._master_fd = pty.fork()
        if self._pid == 0:
            # 子进程：exec shell
            os.execvp(shell, [shell])
            # 不可达
            os._exit(1)
        # 父进程继续

    def write(self, cmd: str) -> None:
        if self._master_fd is None:
            raise RuntimeError("PtyHost 还未启动，请先调用 spawn()")
        os.write(self._master_fd, (cmd + "\n").encode())

    def read_available(self, timeout: float = 0.8) -> str:
        """
        非阻塞读取 bash 的输出，最多等待 timeout 秒。
        同步方法，调用时用 asyncio.to_thread 包装避免阻塞事件循环。
        """
        if self._master_fd is None:
            return ""
        chunks: list[str] = []
        while True:
            r, _, _ = select.select([self._master_fd], [], [], timeout)
            if not r:
                break
            try:
                data = os.read(self._master_fd, 4096)
                if not data:
                    break
                chunks.append(data.decode(errors="replace"))
                # 读到数据后用短超时继续尝试读剩余
                timeout = 0.1
            except OSError:
                break
        return "".join(chunks)

    def close(self) -> None:
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

    def __del__(self):
        self.close()
