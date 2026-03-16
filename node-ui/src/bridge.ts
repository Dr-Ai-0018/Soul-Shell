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

/** 自动探测可用的 Python 命令（python3 优先，兼容 Windows python） */
function detectPython(): string {
  for (const cmd of ["python3", "python"]) {
    const r = spawnSync(cmd, ["--version"], { stdio: "ignore" });
    if (r.status === 0) return cmd;
  }
  throw new Error("未找到可用的 Python 命令，请确认已安装 Python 3");
}

/** 兼容旧代码（内部使用），外部代码应改用 PyMsg */
export type SoulMessage = Record<string, unknown> & { type: string };

export class PythonBridge extends EventEmitter {
  private proc: ChildProcessWithoutNullStreams;
  private ready = false;

  constructor(pythonCmd = detectPython(), args = ["-m", "soul_shell", "--server"]) {
    super();
    this.proc = spawn(pythonCmd, args, {
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
