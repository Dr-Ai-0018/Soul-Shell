import asyncio
import sys
from ..shell.interceptor import Interceptor, BlockedError
from ..config.defaults import RISK_THRESHOLD_HIGH


class Executor:
    def __init__(self, interceptor: Interceptor):
        self._interceptor = interceptor

    async def run_with_confirm(self, cmd: str) -> None:
        """
        安全校验 -> 打印计划 -> 等待确认 -> 执行
        阻断时打印原因后返回，不抛异常（让对话继续）。
        """
        print()

        try:
            risk_score = self._interceptor.check(cmd)
        except BlockedError as e:
            print(f"[Soul Guard] {e}\n")
            return

        risk_label = (
            "low" if risk_score < 40
            else "medium" if risk_score < RISK_THRESHOLD_HIGH
            else "high"
        )
        risk_icon = {"low": "✓", "medium": "!", "high": "⚠"}[risk_label]

        print(f"[{risk_icon}] 准备执行：{cmd}")
        if risk_score > 0:
            print(f"    风险评级：{risk_label}（{risk_score}/100）")

        if risk_score >= RISK_THRESHOLD_HIGH:
            try:
                confirm = input("    这条命令风险较高，确认执行？[y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n    已取消")
                return
            if confirm != "y":
                print("    已取消")
                return
        else:
            try:
                confirm = input("    确认执行？[Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n    已取消")
                return
            if confirm == "n":
                print("    已取消")
                return

        print()
        await self._execute(cmd)

    async def _execute(self, cmd: str) -> None:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            # 流式读取输出，不等全部完成再打印
            assert proc.stdout is not None
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                sys.stdout.write(chunk.decode(errors="replace"))
                sys.stdout.flush()
            await proc.wait()
        except Exception as e:
            print(f"\n[执行出错] {e}")
