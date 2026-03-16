/**
 * index.tsx — Soul-Shell Node UI 入口
 *
 * Phase 2 骨架：启动 Python bridge，渲染基础 Ink 界面。
 * 目前只做 ping/pong 验证通信，后续迭代加输入框和流式渲染。
 */

import React, { useState, useEffect } from "react";
import { render, Text, Box } from "ink";
import { PythonBridge, SoulMessage } from "./bridge.js";

function App() {
  const [status, setStatus] = useState<"connecting" | "ready" | "error">(
    "connecting"
  );
  const [log, setLog] = useState<string[]>([]);

  const append = (line: string) =>
    setLog((prev) => [...prev.slice(-20), line]);

  useEffect(() => {
    const bridge = new PythonBridge();

    bridge.on("ready", () => {
      setStatus("ready");
      append("[bridge] Python core 已就绪");
    });

    bridge.on("message", (msg: SoulMessage) => {
      append(`[${msg.type}] ${JSON.stringify(msg)}`);
    });

    bridge.on("close", (code: number) => {
      setStatus("error");
      append(`[bridge] Python 进程退出，code=${code}`);
    });

    return () => bridge.destroy();
  }, []);

  const statusColor =
    status === "ready" ? "green" : status === "error" ? "red" : "yellow";
  const statusText =
    status === "ready"
      ? "● 已连接"
      : status === "error"
      ? "✗ 连接断开"
      : "○ 连接中…";

  return (
    <Box flexDirection="column" padding={1}>
      <Box marginBottom={1}>
        <Text bold color="cyan">
          Soul-Shell{" "}
        </Text>
        <Text color={statusColor}>{statusText}</Text>
      </Box>

      <Box flexDirection="column">
        {log.map((line, i) => (
          <Text key={i} dimColor>
            {line}
          </Text>
        ))}
      </Box>

      {status === "ready" && (
        <Box marginTop={1}>
          <Text color="gray">（UI 输入框开发中…）</Text>
        </Box>
      )}
    </Box>
  );
}

render(<App />);
