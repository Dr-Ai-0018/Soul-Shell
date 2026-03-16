import React, { useState, useEffect } from 'react'
import { Box, Text } from 'ink'

// braille 点阵动画，80ms/帧，优雅且轻量
const FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

interface StreamViewProps {
  text: string
  /** true = AI 正在响应中（可能是等待首 token 或正在流式输出） */
  active: boolean
}

export function StreamView({ text, active }: StreamViewProps) {
  const [frame, setFrame] = useState(0)

  // 只有在"等待首 token"阶段才需要动画；有文本后停止计时器以避免无意义重绘
  useEffect(() => {
    if (!active || text) return
    const timer = setInterval(() => setFrame(f => (f + 1) % FRAMES.length), 80)
    return () => clearInterval(timer)
  }, [active, !!text])

  if (!active && !text) return null

  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* 标题行 */}
      <Box>
        <Text bold color="cyan">AI</Text>
        <Text color="gray">{'  '}</Text>
        {active && !text && (
          <>
            <Text color="cyan">{FRAMES[frame]}</Text>
            <Text color="gray" dimColor>  思考中…  </Text>
            <Text color="gray" dimColor italic>ESC 取消</Text>
          </>
        )}
        {active && text && (
          <Text color="gray" dimColor>▍</Text>
        )}
      </Box>

      {/* 正文：有文本时显示，streaming 末尾加闪烁光标 */}
      {text && (
        <Box paddingLeft={3}>
          <Text color="white">
            {text}
            {active && <Text color="cyan">▋</Text>}
          </Text>
        </Box>
      )}
    </Box>
  )
}
