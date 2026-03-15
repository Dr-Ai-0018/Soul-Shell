from enum import Enum, auto
from typing import AsyncIterator

OPEN_TAG = "<cmd>"
CLOSE_TAG = "</cmd>"


class _State(Enum):
    NORMAL = auto()
    MAYBE_OPEN = auto()   # 正在尝试匹配 <cmd>
    IN_CMD = auto()
    MAYBE_CLOSE = auto()  # 正在尝试匹配 </cmd>


class StreamParser:
    """
    消费 AsyncIterator[str] 的 token 流，
    yield (text_chunk, cmd_or_None) 元组：
      - text_chunk: 实时显示给用户的文字
      - cmd:        完整提取的命令（None 表示本次无命令）

    关键特性：<cmd> 标签可被跨 chunk 切分，状态机保证正确处理。
    """

    def __init__(self):
        self._reset()

    def _reset(self):
        self._state = _State.NORMAL
        self._tag_buf = ""   # MAYBE_OPEN / MAYBE_CLOSE 阶段的暂存
        self._cmd_buf = ""   # IN_CMD 阶段的命令内容

    async def feed(
        self, token_stream: AsyncIterator[str]
    ) -> AsyncIterator[tuple[str, str | None]]:
        async for token in token_stream:
            for char in token:
                text, cmd = self._process_char(char)
                if text or cmd is not None:
                    yield text, cmd

        # 流结束，处理残留状态
        if self._state == _State.MAYBE_OPEN:
            # 未完成的 <cmd 前缀，当普通文本输出
            yield self._tag_buf, None
        elif self._state == _State.IN_CMD:
            # 未闭合的命令标签，丢弃并告警
            yield "\n[Soul Guard] 检测到未闭合的 <cmd> 标签，命令已丢弃\n", None
        elif self._state == _State.MAYBE_CLOSE:
            # IN_CMD 中出现了未完成的 </cmd 前缀
            yield "", None  # 静默丢弃，不输出残缺命令

        self._reset()

    def _process_char(self, char: str) -> tuple[str, str | None]:
        if self._state == _State.NORMAL:
            if char == "<":
                self._state = _State.MAYBE_OPEN
                self._tag_buf = "<"
                return "", None
            return char, None

        elif self._state == _State.MAYBE_OPEN:
            self._tag_buf += char
            if OPEN_TAG.startswith(self._tag_buf):
                if self._tag_buf == OPEN_TAG:
                    # 完整匹配到 <cmd>，进入命令收集
                    self._state = _State.IN_CMD
                    self._tag_buf = ""
                    self._cmd_buf = ""
                # 继续等待
                return "", None
            else:
                # 不是 <cmd>，把缓冲当普通文本 flush 出去
                flushed = self._tag_buf
                self._tag_buf = ""
                self._state = _State.NORMAL
                return flushed, None

        elif self._state == _State.IN_CMD:
            if char == "<":
                self._state = _State.MAYBE_CLOSE
                self._tag_buf = "<"
                return "", None
            self._cmd_buf += char
            return "", None

        elif self._state == _State.MAYBE_CLOSE:
            self._tag_buf += char
            if CLOSE_TAG.startswith(self._tag_buf):
                if self._tag_buf == CLOSE_TAG:
                    # 完整匹配到 </cmd>，命令提取完成
                    cmd = self._cmd_buf.strip()
                    self._cmd_buf = ""
                    self._tag_buf = ""
                    self._state = _State.NORMAL
                    return "", cmd if cmd else None
                # 继续等待
                return "", None
            else:
                # 不是 </cmd>，把 tag_buf 追加到 cmd_buf，回到 IN_CMD
                self._cmd_buf += self._tag_buf
                self._tag_buf = ""
                self._state = _State.IN_CMD
                return "", None

        return "", None  # 不可达，保险
