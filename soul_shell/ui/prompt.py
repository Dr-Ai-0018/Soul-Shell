import asyncio
import os
import random
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from ..config.defaults import (
    CONFIG_FILE, SYSTEM_PROMPT_FILE, USER_PROFILE_FILE,
    SHELL_LOG_OUTPUT_MAX_CHARS, CONTEXT_OUTPUT_MAX_CHARS,
)
from ..config.loader import load_channels_raw, load_settings, CONFIG_EXAMPLE
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

# 始终注入 system 的命令协议（让 AI 知道 <cmd> 能被执行并会收到反馈）
_CMD_PROTOCOL = """\

---
【命令执行协议】
- 需要执行 Shell 命令时，用 <cmd>...</cmd> 包裹，每次只给一条
- 命令执行后，输出和退出码会作为系统消息反馈给你，你可以据此继续
- 多步骤任务：逐条给命令，看到反馈再给下一条，全部完成后在回复末尾输出 [Done]
- 单步任务或纯回答：正常回复，不需要输出 [Done]
- 命令被拦截或用户跳过时，你会收到通知，据此调整方案
---"""

# 连续模式追加的额外约束（在 _CMD_PROTOCOL 基础上叠加）
_AUTO_PROTOCOL = """\

---
【连续执行模式】
你现在处于自主任务执行模式，必须持续执行直到完成：
1. 先简短描述整体执行计划
2. 每次只输出一条命令，看到反馈再给下一条，不要一次给多条
3. 遇到报错，分析原因后调整方案，不要重复失败的命令
4. 所有步骤完成后必须输出 [Done]，否则系统会继续等待你的下一条命令
---"""

HELP_TEXT = """\
用法：
  ? <问题>              向 Soul 提问，支持自然语言
  ?? <任务>             连续模式：Soul 自主规划并逐步执行命令直到完成
  /model               列出所有渠道和模型
  /model <渠道/模型>    切换到指定模型（例：/model deepseek/deepseek-chat）
  /model probe <渠道>   自动探测渠道可用模型（仅 OpenAI 兼容渠道）
  /history             查看本次对话历史
  /clear               清空对话历史
  /help                显示此帮助
  /exit                退出

普通输入直接作为 shell 命令执行，经过安全拦截层校验。
"""

# 已知需要独占终端的交互式程序（TUI / REPL）
_INTERACTIVE_COMMANDS = frozenset({
    'htop', 'top', 'atop', 'btop', 'glances',
    'vim', 'vi', 'nvim', 'nano', 'emacs', 'micro', 'joe',
    'less', 'more', 'man',
    'watch',
    'ncdu', 'tig', 'lazygit', 'gitui',
    'mc', 'ranger', 'nnn', 'lf',
    'mutt', 'neomutt', 'cmus', 'ncmpcpp',
    'screen', 'tmux',
    'ssh', 'sftp', 'ftp', 'telnet',
    'mysql', 'psql', 'sqlite3', 'redis-cli', 'mongosh',
    'python', 'python3', 'ipython', 'bpython',
    'node', 'deno', 'irb', 'pry',
    'gdb', 'lldb', 'pdb',
    'zsh', 'bash', 'fish', 'sh', 'dash',
})


def _is_interactive(cmd: str) -> bool:
    """检测命令是否需要独占终端（TUI / REPL）"""
    first = cmd.strip().split()[0].split('/')[-1] if cmd.strip() else ''
    return first in _INTERACTIVE_COMMANDS


class SoulShellUI:
    def __init__(self):
        channels_raw = load_channels_raw()
        channels = [Channel.from_dict(c) for c in channels_raw]
        self._registry = ModelRegistry(channels)
        self._interceptor = Interceptor()
        self._executor = Executor(self._interceptor)
        self._cfg = load_settings()
        self._history: list[dict] = []
        self._shell_log: list[dict] = []   # {"cmd", "exit", "out", "cwd"}
        self._cwd = os.getcwd()
        self._session = PromptSession(
            history=InMemoryHistory(),
            style=_PROMPT_STYLE,
        )
        self._system_prompt = self._load_system_prompt()

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

    def _build_system_with_context(self, extra: str = "") -> str:
        """
        拼接最终 system prompt：
          基础人设 + 命令执行协议 + shell 历史上下文（可选）+ 额外模式附加（可选）
        """
        result = self._system_prompt + _CMD_PROTOCOL
        if self._shell_log:
            lines = []
            for entry in self._shell_log[-self._cfg["shell_context_inject"]:]:
                status = "✓" if entry["exit"] == 0 else f"✗(exit {entry['exit']})"
                _o = entry['out'] if CONTEXT_OUTPUT_MAX_CHARS is None else entry['out'][:CONTEXT_OUTPUT_MAX_CHARS]
                out = f"\n    输出：{_o}" if _o else ""
                lines.append(f"  {status} [{entry['cwd']}] {entry['cmd']}{out}")
            result += (
                "\n\n---\n【当前会话终端记录（最近执行的命令，供你参考上下文）】\n"
                + "\n".join(lines)
                + f"\n当前目录：{self._cwd}\n---"
            )
        if extra:
            result += extra
        return result

    def _get_prompt_text(self) -> str:
        model_str = (
            self._registry.active.display_name
            if self._registry.active
            else "no-model"
        )
        cwd_display = os.path.basename(self._cwd) or self._cwd
        return f"[{model_str}] {cwd_display} $ "

    async def run(self) -> None:
        if not self._registry.active:
            self._print_no_config_guide()
            return

        print("Soul-Shell 启动了，，，你又来折腾我了")
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

            if line.startswith("??") or line.startswith("？？"):
                await self._handle_auto_mode(line[2:].strip())
            elif line.startswith("?") or line.startswith("？"):
                await self._handle_ai_query(line[1:].strip())
            elif line.startswith("/"):
                should_exit = await self._handle_slash_command(line)
                if should_exit:
                    break
            else:
                await self._handle_shell_command(line)

    async def _run_confirmed(self, cmd: str) -> tuple[str, int] | None:
        """
        安全检查 → 用户确认 → 执行并返回 (output, exit_code)。
        用户拒绝或命令被拦截时返回 None。
        """
        try:
            risk_score = self._interceptor.check(cmd)
        except BlockedError as e:
            print(f"\n[Soul Guard] {e}")
            return ("命令被安全层拦截", -1)

        risk_tag = f"  ⚠ 风险 {risk_score}/100" if risk_score >= 40 else ""
        print(f"\n[准备执行] {cmd}{risk_tag}")

        high_risk = risk_score >= self._cfg["risk_threshold"]
        prompt = "高风险，确认执行？[y/N] " if high_risk else "确认执行？[Y/n] "
        try:
            confirm = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return None

        if high_risk and confirm != "y":
            return None
        if not high_risk and confirm == "n":
            return None

        output, exit_code = await self._run_for_auto(cmd)
        return output, exit_code

    async def _handle_ai_query(self, query: str) -> None:
        if not query:
            print("（问点什么？）")
            return

        self._history.append({"role": "user", "content": query})
        max_rounds = self._cfg["auto_max_iterations"]

        for _round in range(max_rounds):
            try:
                adapter = self._registry.get_adapter()
            except RuntimeError as e:
                print(f"[错误] {e}")
                self._history.pop()
                return

            parser = StreamParser()
            full_response: list[str] = []
            cmd_results: list[str] = []

            try:
                async for text, cmd in parser.feed(
                    adapter.chat_stream(
                        self._history, system=self._build_system_with_context()
                    )
                ):
                    if text:
                        print(text, end="", flush=True)
                        full_response.append(text)
                    if cmd is not None:
                        print()
                        result = await self._run_confirmed(cmd)
                        if result is not None:
                            output, exit_code = result
                            status = "成功" if exit_code == 0 else f"失败(exit {exit_code})"
                            cmd_results.append(
                                f"`{cmd}` → {status}\n{output[:800] or '（无输出）'}"
                            )
            except AdapterError as e:
                print(f"\n[适配器错误] {e}")
                if e.body:
                    print(f"    响应：{e.body[:200]}")
                self._history.pop()
                return
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\n已中断")
                return
            except Exception as e:
                print(f"\n[未知错误] {e}")
                self._history.pop()
                return

            print()
            response_text = "".join(full_response)
            if response_text:
                self._history.append({"role": "assistant", "content": response_text})

            max_turns = self._cfg["max_history_turns"]
            if len(self._history) > max_turns * 2:
                self._history = self._history[-(max_turns * 2):]

            # 没有执行任何命令，或 AI 明确说完了 → 退出循环
            if not cmd_results or "[Done]" in response_text or "[DONE]" in response_text:
                break

            # 有命令执行结果 → 反馈给 AI，继续下一轮
            feedback = "\n\n---\n".join(cmd_results) + "\n\n请继续，完成后输出 [Done]。"
            self._history.append({"role": "user", "content": feedback})

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

        if risk_score >= self._cfg["risk_threshold"]:
            try:
                confirm = input(
                    f"[⚠] 风险命令（{risk_score}/100），确认执行？[y/N] "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n已取消")
                return
            if confirm != "y":
                print("已取消")
                return

        # cd 特殊处理：子进程无法影响父进程工作目录
        stripped = cmd.strip()
        if stripped == "cd" or stripped.startswith("cd ") or stripped.startswith("cd\t"):
            path = stripped[2:].strip() or os.path.expanduser("~")
            path = os.path.expandvars(os.path.expanduser(path))
            try:
                os.chdir(path)
                self._cwd = os.getcwd()
            except FileNotFoundError:
                print(f"cd: {path}: No such file or directory")
            except PermissionError:
                print(f"cd: {path}: Permission denied")
            except Exception as e:
                print(f"cd: {e}")
            return

        if _is_interactive(cmd):
            await self._run_interactive(cmd)
        else:
            await self._run_captured(cmd)

    async def _run_interactive(self, cmd: str) -> None:
        """运行 TUI/REPL 程序，直接继承终端，退出后恢复终端状态。"""
        proc = await asyncio.create_subprocess_shell(cmd, cwd=self._cwd)
        try:
            await proc.wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    proc.kill()
        finally:
            os.system("stty sane 2>/dev/null")

        self._log_shell(cmd, proc.returncode or 0, "")

    async def _run_captured(self, cmd: str) -> None:
        """运行普通命令，捕获输出，事后让 Soul 点评。"""
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self._cwd,
            )
            output_bytes, _ = await proc.communicate()
        except (asyncio.CancelledError, KeyboardInterrupt):
            return
        except Exception as e:
            print(f"[执行出错] {e}")
            return

        output = output_bytes.decode(errors="replace") if output_bytes else ""
        if output:
            print(output, end="")

        exit_code = proc.returncode if proc.returncode is not None else 0
        self._log_shell(cmd, exit_code, output)
        await self._soul_react(cmd, exit_code, output)

    def _log_shell(self, cmd: str, exit_code: int, output: str) -> None:
        """记录命令执行结果到 shell_log，供 Soul 参考上下文。"""
        self._shell_log.append({
            "cmd": cmd,
            "exit": exit_code,
            "out": output.strip() if SHELL_LOG_OUTPUT_MAX_CHARS is None else output.strip()[:SHELL_LOG_OUTPUT_MAX_CHARS],
            "cwd": os.path.basename(self._cwd) or self._cwd,
        })
        limit = self._cfg["shell_log_size"]
        if len(self._shell_log) > limit:
            self._shell_log = self._shell_log[-limit:]

    async def _soul_react(self, cmd: str, exit_code: int, output: str) -> None:
        """Soul 对命令执行结果的旁观者点评（出错必评，成功 30% 概率触发）。"""
        if not self._registry.active:
            return

        failed = exit_code != 0
        if not failed and random.random() >= self._cfg["react_probability"]:
            return

        status = f"失败（exit {exit_code}）" if failed else "成功（exit 0）"
        _out = output.strip()
        output_preview = (_out if SHELL_LOG_OUTPUT_MAX_CHARS is None else _out[:SHELL_LOG_OUTPUT_MAX_CHARS]) if _out else "无输出"

        react_msg = (
            f"用户刚执行了 shell 命令：`{cmd}`\n"
            f"结果：{status}\n"
            f"命令输出（节选）：{output_preview}\n\n"
            "用你的风格给一句简短点评，不超过两行，不要重复命令本身。"
        )

        try:
            adapter = self._registry.get_adapter()
            print("\nSoul > ", end="", flush=True)
            async for text, _ in StreamParser().feed(
                adapter.chat_stream(
                    [{"role": "user", "content": react_msg}],
                    system=self._build_system_with_context(),
                )
            ):
                if text:
                    print(text, end="", flush=True)
            print()
        except Exception:
            pass  # 点评失败不影响主流程

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

    async def _run_for_auto(self, cmd: str) -> tuple[str, int]:
        """执行命令，实时打印输出，同时返回完整输出和退出码供 AI 参考。"""
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self._cwd,
            )
            chunks: list[str] = []
            assert proc.stdout is not None
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                text = chunk.decode(errors="replace")
                sys.stdout.write(text)
                sys.stdout.flush()
                chunks.append(text)
            await proc.wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            return "", -1
        except Exception as e:
            print(f"[执行出错] {e}")
            return str(e), -1

        output = "".join(chunks)
        exit_code = proc.returncode if proc.returncode is not None else 0
        self._log_shell(cmd, exit_code, output)
        return output, exit_code

    async def _handle_auto_mode(self, task: str) -> None:
        """
        连续执行模式：AI 自主规划并逐条执行命令，直到输出 [Done] 或达到最大轮数。
        触发：?? <任务描述>
        """
        if not task:
            print("用法：?? <任务描述>，例：?? 安装并启动 nginx")
            return

        try:
            adapter = self._registry.get_adapter()
        except RuntimeError as e:
            print(f"[错误] {e}")
            return

        max_iter = self._cfg["auto_max_iterations"]
        # 独立历史，不污染主对话
        auto_history: list[dict] = [
            {"role": "user", "content": f"任务：{task}"}
        ]
        system = self._build_system_with_context(extra=_AUTO_PROTOCOL)

        print(f"\n[连续模式] 任务：{task}  (最多 {max_iter} 轮，Ctrl+C 随时中断)\n")

        for iteration in range(1, max_iter + 1):
            print(f"── 第 {iteration} 轮 " + "─" * 40)

            parser = StreamParser()
            full_response: list[str] = []
            pending_cmd: str | None = None

            try:
                async for text, cmd in parser.feed(
                    adapter.chat_stream(auto_history, system=system)
                ):
                    if text:
                        print(text, end="", flush=True)
                        full_response.append(text)
                    if cmd is not None:
                        pending_cmd = cmd
            except AdapterError as e:
                print(f"\n[适配器错误] {e}")
                break
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\n[连续模式] 已中断")
                return

            print()
            response_text = "".join(full_response)
            auto_history.append({"role": "assistant", "content": response_text})

            # 检测任务完成信号
            if "[Done]" in response_text or "[DONE]" in response_text:
                print("\n[连续模式] ✓ 任务完成")
                return

            # 没有命令也没有 [Done]：可能 AI 在问用户
            if pending_cmd is None:
                print("\n[连续模式] AI 未给出命令（如需补充信息请输入，输入 q 退出）")
                try:
                    extra = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if extra.lower() == "q":
                    break
                auto_history.append({"role": "user", "content": extra})
                continue

            # 安全检查
            try:
                risk_score = self._interceptor.check(pending_cmd)
            except BlockedError as e:
                print(f"\n[Soul Guard] {e}")
                auto_history.append({
                    "role": "user",
                    "content": f"命令被安全层拦截，无法执行：{e}\n请调整方案或输出 [Done] 结束。",
                })
                continue

            # 用户确认
            risk_tag = f"  ⚠ 风险 {risk_score}/100" if risk_score >= 40 else ""
            print(f"\n[连续模式] 准备执行：{pending_cmd}{risk_tag}")
            try:
                confirm = input("执行？[Y/n/q(退出)] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n[连续模式] 已中断")
                return

            if confirm == "q":
                print("[连续模式] 已退出")
                return
            if confirm == "n":
                auto_history.append({
                    "role": "user",
                    "content": "用户跳过了该命令，请调整方案或输出 [Done] 结束。",
                })
                continue

            # 执行并把结果反馈给 AI
            output, exit_code = await self._run_for_auto(pending_cmd)
            status = "成功" if exit_code == 0 else f"失败（exit {exit_code}）"
            feedback = (
                f"命令执行{status}。\n"
                f"输出：\n{output[:1500] if output.strip() else '（无输出）'}\n\n"
                "请继续执行下一步，或在任务完成后输出 [Done]。"
            )
            auto_history.append({"role": "user", "content": feedback})
            # 同步更新 shell 上下文（让后续 AI 查询也能感知）
            system = self._build_system_with_context(extra=_AUTO_PROTOCOL)

        else:
            print(f"\n[连续模式] 已达最大轮数（{max_iter}），自动退出")

    def _print_no_config_guide(self) -> None:
        print(f"找不到配置文件：{CONFIG_FILE}")
        print("请创建该文件并添加至少一个渠道，示例：\n")
        print(CONFIG_EXAMPLE)
