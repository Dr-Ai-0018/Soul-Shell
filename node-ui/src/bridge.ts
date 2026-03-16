/**
 * bridge.ts — Node ↔ Python JSON-lines IPC
 *
 * 启动 Python 子进程（soul-shell --server），
 * 提供 send() 发送请求、onMessage() 注册响应回调。
 */

import { spawn, spawnSync, ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import { EventEmitter } from "node:events";
import type { NodeMsg, PyMsg } from "./types.js";

/**
 * 探测启动方式（优先级）：
 *  1. uv run — 自动激活 .venv，跨平台，依赖隔离最优
 *  2. .venv/bin/python — 直接用项目虚拟环境
 *  3. python3 / python — 系统 Python（可能缺依赖，兜底）
 */
function detectLauncher(): { cmd: string; args: string[] } {
  const projectRoot = new URL("../../", import.meta.url).pathname;

  // 1. 尝试 uv run
  const uvCheck = spawnSync("uv", ["--version"], { stdio: "ignore" });
  if (uvCheck.status === 0) {
    return { cmd: "uv", args: ["run", "python", "-m", "soul_shell", "--server"] };
  }

  // 2. 尝试 .venv/bin/python（Unix）
  const venvPython = `${projectRoot}.venv/bin/python`;
  const venvCheck = spawnSync(venvPython, ["--version"], { stdio: "ignore" });
  if (venvCheck.status === 0) {
    return { cmd: venvPython, args: ["-m", "soul_shell", "--server"] };
  }

  // 3. 兜底：系统 Python
  for (const cmd of ["python3", "python"]) {
    const r = spawnSync(cmd, ["--version"], { stdio: "ignore" });
    if (r.status === 0) return { cmd, args: ["-m", "soul_shell", "--server"] };
  }

  throw new Error("未找到可用的 Python 环境，请确认已安装 uv 或 Python 3");
}

/** 兼容旧代码（内部使用），外部代码应改用 PyMsg */
export type SoulMessage = Record<string, unknown> & { type: string };

export class PythonBridge extends EventEmitter {
  private proc: ChildProcessWithoutNullStreams;
  private ready = false;

  constructor() {
    super();
    const { cmd, args } = detectLauncher();
    this.proc = spawn(cmd, args, {
      stdio: ["pipe", "pipe", "pipe"],
      cwd: new URL("../../", import.meta.url).pathname,
    });

    const rl = createInterface({ input: this.proc.stdout });
    rl.on("line", (line) => {
      if (!line.trim()) return;
      try {
        const msg = JSON.parse(line) as PyMsg;
        this.emit("message", msg);
        this.emit(msg.type, msg);
      } catch {
        // 忽略非 JSON 行（Python 启动日志等）
      }
    });

    // 把 Python stderr 转发到 Node stderr（Ink 不占用 stderr）
    this.proc.stderr.pipe(process.stderr);

    this.proc.on("close", (code) => {
      this.emit("close", code);
    });

    // 等待第一个 pong 确认进程就绪
    this.once("pong", () => {
      this.ready = true;
      this.emit("ready");
    });
    this.ping();
  }

  ping(): void {
    this.send({ type: "ping" });
  }

  send(msg: NodeMsg): void {
    const line = JSON.stringify(msg) + "\n";
    this.proc.stdin.write(line);
  }

  query(id: string, text: string, history: import("./types.js").HistoryEntry[] = []): void {
    this.send({ type: "query", id, text, history });
  }

  shell(id: string, cmd: string): void {
    this.send({ type: "shell", id, cmd });
  }

  cancel(id: string): void {
    this.send({ type: "cancel", id });
  }

  destroy(): void {
    this.proc.kill();
  }

  isReady(): boolean {
    return this.ready;
  }
}
