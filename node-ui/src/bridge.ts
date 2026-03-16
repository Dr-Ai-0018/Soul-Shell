/**
 * bridge.ts — Node ↔ Python JSON-lines IPC
 *
 * 启动 Python 子进程（soul-shell --server），
 * 提供 send() 发送请求、onMessage() 注册响应回调。
 */

import { spawn, ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import { EventEmitter } from "node:events";

export type SoulMessage = Record<string, unknown> & { type: string };

export class PythonBridge extends EventEmitter {
  private proc: ChildProcessWithoutNullStreams;
  private ready = false;

  constructor(pythonCmd = "python", args = ["-m", "soul_shell", "--server"]) {
    super();
    this.proc = spawn(pythonCmd, args, {
      stdio: ["pipe", "pipe", "inherit"],
      cwd: new URL("../../", import.meta.url).pathname,
    });

    const rl = createInterface({ input: this.proc.stdout });
    rl.on("line", (line) => {
      if (!line.trim()) return;
      try {
        const msg: SoulMessage = JSON.parse(line);
        this.emit("message", msg);
        this.emit(msg.type, msg);
      } catch {
        // 忽略非 JSON 行（Python 启动日志等）
      }
    });

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

  send(msg: Record<string, unknown>): void {
    const line = JSON.stringify(msg) + "\n";
    this.proc.stdin.write(line);
  }

  query(id: string, text: string, history: unknown[] = []): void {
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
