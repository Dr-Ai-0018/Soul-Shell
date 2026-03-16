import argparse
import asyncio
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Soul-Shell：带有赛博灵魂的毒舌 Linux 终端代理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n  soul-shell\n  soul-shell --model deepseek/deepseek-chat\n  soul-shell --server",
    )
    parser.add_argument(
        "--model",
        metavar="渠道/模型",
        help="启动时指定模型（例：deepseek/deepseek-chat）",
    )
    parser.add_argument(
        "--mode",
        choices=["standard", "managed", "chaos"],
        default="standard",
        help="运行模式（默认：standard）",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="以 JSON-lines 服务模式运行，供 Node.js UI 层调用",
    )
    args = parser.parse_args()

    if args.server:
        try:
            from .server import run_server
            asyncio.run(run_server())
        except KeyboardInterrupt:
            pass
        return

    try:
        from .ui.prompt import SoulShellUI
        ui = SoulShellUI()

        if args.model:
            try:
                ui._registry.switch(args.model)
            except ValueError as e:
                print(f"[启动参数] --model 无效：{e}")
                sys.exit(1)

        asyncio.run(ui.run())

    except RuntimeError as e:
        # 比如 Windows 下 pty 不支持
        print(f"[错误] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n拜")


if __name__ == "__main__":
    main()
