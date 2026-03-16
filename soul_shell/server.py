"""
Soul-Shell Server Mode
======================
以 JSON-lines over stdio 协议运行，供 Node.js UI 层调用。

Node → Python（请求，每行一个 JSON）：
  {"type": "query",  "id": "1", "text": "...", "history": [...]}
  {"type": "shell",  "id": "2", "cmd": "ls -la"}
  {"type": "cancel", "id": "1"}
  {"type": "ping"}

Python → Node（响应，每行一个 JSON）：
  {"type": "pong"}
  {"type": "token",  "id": "1", "text": "..."}
  {"type": "cmd",    "id": "1", "cmd": "ls -la"}
  {"type": "done",   "id": "1"}
  {"type": "risk",   "id": "2", "score": 75, "cmd": "..."}
  {"type": "output", "id": "2", "text": "...", "exit": 0}
  {"type": "react",  "id": "2", "text": "..."}
  {"type": "error",  "id": "1", "msg": "..."}
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from typing import Any


def _emit(obj: dict[str, Any]) -> None:
    """向 stdout 写一行 JSON，立即 flush。"""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class Server:
    """JSON-lines 协议服务端，管理请求分发与取消。"""

    def __init__(self) -> None:
        # id -> asyncio.Task，用于支持 cancel
        self._tasks: dict[str, asyncio.Task] = {}

        # 启动时加载一次配置，避免每次 query 都重复读 toml
        from .models.registry import ModelRegistry
        from .models.channel import Channel
        from .config.loader import load_channels_raw
        from .config.defaults import MAX_HISTORY_TURNS, SYSTEM_PROMPT_FILE
        from .engine.stream_parser import StreamParser
        from .shell.interceptor import Interceptor, BlockedError
        from .config.defaults import RISK_THRESHOLD_HIGH

        channels = [Channel.from_dict(c) for c in load_channels_raw()]
        self._registry = ModelRegistry(channels)
        self._max_history_turns = MAX_HISTORY_TURNS
        self._system_prompt_file = SYSTEM_PROMPT_FILE
        self._interceptor = Interceptor()
        self._risk_threshold = RISK_THRESHOLD_HIGH
        self._StreamParser = StreamParser
        self._BlockedError = BlockedError

        from .config.defaults import SOUL_REACT_PROBABILITY
        self._react_probability = SOUL_REACT_PROBABILITY

    async def run(self) -> None:
        """主循环：从 stdin 逐行读取请求并分发。"""
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                line = await reader.readline()
            except Exception:
                break
            if not line:
                break

            raw = line.decode("utf-8", errors="replace").strip()
            if not raw:
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as e:
                _emit({"type": "error", "msg": f"JSON parse error: {e}"})
                continue

            await self._dispatch(msg)

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        msg_type = msg.get("type")

        if msg_type == "ping":
            _emit({"type": "pong"})

        elif msg_type == "query":
            req_id = str(msg.get("id", ""))
            task = asyncio.create_task(self._handle_query(msg))
            if req_id:
                self._tasks[req_id] = task
            task.add_done_callback(lambda _: self._tasks.pop(req_id, None))

        elif msg_type == "shell":
            req_id = str(msg.get("id", ""))
            task = asyncio.create_task(self._handle_shell(msg))
            if req_id:
                self._tasks[req_id] = task
            task.add_done_callback(lambda _: self._tasks.pop(req_id, None))

        elif msg_type == "cancel":
            req_id = str(msg.get("id", ""))
            task = self._tasks.pop(req_id, None)
            if task and not task.done():
                task.cancel()

        else:
            _emit({"type": "error", "msg": f"unknown message type: {msg_type!r}"})

    async def _handle_query(self, msg: dict[str, Any]) -> None:
        """处理 AI 查询请求，流式输出 token / cmd / done。"""
        req_id = str(msg.get("id", ""))
        text = msg.get("text", "")
        history = msg.get("history", [])

        try:
            adapter = self._registry.get_adapter()

            # 构造消息列表
            messages: list[dict] = list(history[-(self._max_history_turns * 2):])
            messages.append({"role": "user", "content": text})

            system_prompt: str | None = None
            try:
                system_prompt = self._system_prompt_file.read_text(encoding="utf-8")
            except Exception:
                pass

            parser = self._StreamParser()
            token_stream = adapter.chat_stream(messages, system=system_prompt)

            async for chunk_text, cmd in parser.feed(token_stream):
                if chunk_text:
                    _emit({"type": "token", "id": req_id, "text": chunk_text})
                if cmd is not None:
                    _emit({"type": "cmd", "id": req_id, "cmd": cmd})

            _emit({"type": "done", "id": req_id})

        except asyncio.CancelledError:
            _emit({"type": "error", "id": req_id, "msg": "cancelled"})
            raise
        except Exception as e:
            _emit({"type": "error", "id": req_id, "msg": str(e)})

    async def _handle_shell(self, msg: dict[str, Any]) -> None:
        """处理 shell 执行请求，输出 risk / output。"""
        req_id = str(msg.get("id", ""))
        cmd = msg.get("cmd", "")

        try:
            try:
                score = self._interceptor.check(cmd)
            except self._BlockedError as e:
                _emit({"type": "error", "id": req_id, "msg": f"blocked: {e}"})
                return

            _emit({"type": "risk", "id": req_id, "score": score, "cmd": cmd})

            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            assert proc.stdout is not None

            # 收集输出用于 react（同时实时推流给 Node）
            output_chunks: list[str] = []
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                text = chunk.decode(errors="replace")
                output_chunks.append(text)
                _emit({"type": "output", "id": req_id, "text": text, "exit": None})

            await proc.wait()
            exit_code = proc.returncode
            _emit({"type": "output", "id": req_id, "text": "", "exit": exit_code})

            # 失败必 react；成功按概率 react（Soul 在旁边看着）
            should_react = (exit_code != 0) or (random.random() < self._react_probability)
            if should_react:
                full_output = "".join(output_chunks)[:800]
                react_id = f"react_{req_id}"
                task = asyncio.create_task(
                    self._handle_react(react_id, cmd, full_output, exit_code)
                )
                self._tasks[react_id] = task
                task.add_done_callback(lambda _: self._tasks.pop(react_id, None))

        except asyncio.CancelledError:
            _emit({"type": "error", "id": req_id, "msg": "cancelled"})
            raise
        except Exception as e:
            _emit({"type": "error", "id": req_id, "msg": str(e)})


    async def _handle_react(
        self,
        react_id: str,
        cmd: str,
        output: str,
        exit_code: int,
    ) -> None:
        """Soul 看完 shell 输出后的点评，失败必出声，成功按概率。"""
        try:
            adapter = self._registry.get_adapter()

            status = "成功" if exit_code == 0 else f"失败（退出码 {exit_code}）"
            user_msg = f"[Shell 执行{status}]\n$ {cmd}\n{output.strip()}"

            system_prompt: str | None = None
            try:
                system_prompt = self._system_prompt_file.read_text(encoding="utf-8")
            except Exception:
                pass

            full_text = ""
            async for chunk in adapter.chat_stream(
                [{"role": "user", "content": user_msg}],
                system=system_prompt,
            ):
                full_text += chunk

            if full_text.strip():
                _emit({"type": "react", "id": react_id, "text": full_text.strip()})

        except asyncio.CancelledError:
            raise
        except Exception:
            pass  # react 失败静默，不干扰主流程


async def run_server() -> None:
    server = Server()
    await server.run()
