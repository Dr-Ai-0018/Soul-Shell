import asyncio
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from ..config.defaults import CONFIG_FILE, SYSTEM_PROMPT_FILE, USER_PROFILE_FILE
from ..config.loader import load_channels_raw, CONFIG_EXAMPLE
from ..models.channel import Channel
from ..models.registry import ModelRegistry
from ..models.probe import probe_models
from ..adapters.base import AdapterError
from ..engine.stream_parser import StreamParser
from ..engine.executor import Executor
from ..shell.interceptor import Interceptor, BlockedError

_PROMPT_STYLE = Style.from_dict({
    "prompt.bracket": "#888888",
    "prompt.model": "#00aaff bold",
    "prompt.dollar": "#ffffff",
})

HELP_TEXT = """\
用法：
  ? <问题>              向 Soul 提问，支持自然语言
  /model               列出所有渠道和模型
  /model <渠道/模型>    切换到指定模型（例：/model deepseek/deepseek-chat）
  /model probe <渠道>   自动探测渠道可用模型（仅 OpenAI 兼容渠道）
  /history             查看本次对话历史
  /clear               清空对话历史
  /help                显示此帮助
  /exit                退出

普通输入直接作为 shell 命令执行，经过安全拦截层校验。
"""


class SoulShellUI:
    def __init__(self):
        channels_raw = load_channels_raw()
        channels = [Channel.from_dict(c) for c in channels_raw]
        self._registry = ModelRegistry(channels)
        self._interceptor = Interceptor()
        self._executor = Executor(self._interceptor)
        self._history: list[dict] = []
        self._session = PromptSession(
            history=InMemoryHistory(),
            style=_PROMPT_STYLE,
        )
        self._system_prompt = self._load_system_prompt()
        self._pty = None
        self._use_pty = sys.platform != "win32"

    def _load_system_prompt(self) -> str:
        if not SYSTEM_PROMPT_FILE.exists():
            return "你是 Soul，一个毒舌的 Linux 终端助手。"
        system = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
        if USER_PROFILE_FILE.exists():
            profile = USER_PROFILE_FILE.read_text(encoding="utf-8")
            system = system.replace("{{user_profile}}", profile)
        else:
            system = system.replace("{{user_profile}}", "（用户画像未配置）")
        return system

    def _get_prompt_text(self) -> str:
        model_str = (
            self._registry.active.display_name
            if self._registry.active
            else "no-model"
        )
        return f"[{model_str}] $ "

    async def run(self) -> None:
        # 检查配置
        if not self._registry.active:
            self._print_no_config_guide()
            return

        # 启动 pty（仅 Linux/macOS）
        if self._use_pty:
            try:
                from ..shell.pty_host import PtyHost
                self._pty = PtyHost()
                self._pty.spawn()
            except Exception as e:
                print(f"pty 启动失败，降级为直接执行模式：{e}")
                self._pty = None

        print(f"Soul-Shell 启动了，，，你又来折腾我了")
        print(f"当前模型：{self._registry.active.display_name}")
        print("输入 /help 查看用法\n")

        while True:
            try:
                line = await self._session.prompt_async(self._get_prompt_text())
            except EOFError:
                print("\n拜")
                break
            except KeyboardInterrupt:
                print()
                continue

            line = line.strip()
            if not line:
                continue

            if line.startswith("?"):
                await self._handle_ai_query(line[1:].strip())
            elif line.startswith("/"):
                should_exit = await self._handle_slash_command(line)
                if should_exit:
                    break
            else:
                await self._handle_shell_command(line)

        if self._pty:
            self._pty.close()

    async def _handle_ai_query(self, query: str) -> None:
        if not query:
            print("（问点什么？）")
            return

        self._history.append({"role": "user", "content": query})

        try:
            adapter = self._registry.get_adapter()
        except RuntimeError as e:
            print(f"[错误] {e}")
            return

        parser = StreamParser()
        full_response: list[str] = []

        try:
            token_stream = adapter.chat_stream(
                self._history, system=self._system_prompt
            )
            async for text, cmd in parser.feed(token_stream):
                if text:
                    print(text, end="", flush=True)
                    full_response.append(text)
                if cmd is not None:
                    print()
                    await self._executor.run_with_confirm(cmd)
        except AdapterError as e:
            print(f"\n[适配器错误] {e}")
            if e.body:
                print(f"    响应：{e.body[:200]}")
            self._history.pop()  # 失败的请求不计入历史
            return
        except Exception as e:
            print(f"\n[未知错误] {e}")
            self._history.pop()
            return

        print()
        response_text = "".join(full_response)
        if response_text:
            self._history.append({"role": "assistant", "content": response_text})

        # 裁剪历史，避免无限增长
        from ..config.defaults import MAX_HISTORY_TURNS
        if len(self._history) > MAX_HISTORY_TURNS * 2:
            self._history = self._history[-(MAX_HISTORY_TURNS * 2):]

    async def _handle_slash_command(self, line: str) -> bool:
        """返回 True 表示需要退出"""
        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/model":
            if not args:
                print(self._registry.list_all())
            elif args[0] == "probe":
                if len(args) < 2:
                    print("用法：/model probe <渠道名>")
                else:
                    await self._probe_channel(args[1])
            else:
                try:
                    new_model = self._registry.switch(args[0])
                    print(f"切换到：{new_model}")
                except ValueError as e:
                    print(f"切换失败：{e}")

        elif cmd in ("/exit", "/quit", "/q"):
            print("拜")
            return True

        elif cmd == "/help":
            print(HELP_TEXT)

        elif cmd == "/history":
            if not self._history:
                print("（对话历史为空）")
            else:
                for i, msg in enumerate(self._history, 1):
                    role = "你" if msg["role"] == "user" else "Soul"
                    content = msg["content"][:100]
                    suffix = "..." if len(msg["content"]) > 100 else ""
                    print(f"  {i}. [{role}] {content}{suffix}")

        elif cmd == "/clear":
            self._history.clear()
            print("对话历史已清空")

        else:
            print(f"未知命令：{cmd}，输入 /help 查看可用命令")

        return False

    async def _handle_shell_command(self, cmd: str) -> None:
        try:
            risk_score = self._interceptor.check(cmd)
        except BlockedError as e:
            print(f"[Soul Guard] {e}")
            return

        if self._pty:
            # 通过 pty 执行，保留终端特性
            from ..config.defaults import RISK_THRESHOLD_HIGH
            if risk_score >= RISK_THRESHOLD_HIGH:
                try:
                    confirm = input(f"[⚠] 风险命令（{risk_score}/100），确认执行？[y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\n已取消")
                    return
                if confirm != "y":
                    print("已取消")
                    return

            self._pty.write(cmd)
            output = await asyncio.to_thread(self._pty.read_available)
            if output:
                print(output, end="")
        else:
            # 降级：走 executor 直接执行
            await self._executor.run_with_confirm(cmd)

    async def _probe_channel(self, ch_name: str) -> None:
        ch = self._registry.channels.get(ch_name)
        if not ch:
            print(f"渠道 '{ch_name}' 不存在")
            return
        print(f"正在探测 {ch_name}...")
        models = await probe_models(ch)
        if models:
            ch.models = models
            if not ch.default_model or ch.default_model not in models:
                ch.default_model = models[0]
            print(f"探测到 {len(models)} 个模型：{', '.join(models)}")
        else:
            print("探测失败或无结果，可能是 API Key 问题或该渠道不支持 /v1/models")

    def _print_no_config_guide(self) -> None:
        print(f"找不到配置文件：{CONFIG_FILE}")
        print("请创建该文件并添加至少一个渠道，示例：\n")
        print(CONFIG_EXAMPLE)
