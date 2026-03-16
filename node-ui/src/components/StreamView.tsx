/**
 * StreamView.tsx — AI 流式输出的实时展示
 *
 * 关键约束：本组件位于 Ink 的「动态区」（live area），Ink 每次 render 都会通过
 *   ansiEscapes.eraseLines(previousLineCount) + write(newOutput)
 * 来更新终端。若 previousLineCount 过大（如 AI 输出了 200 行代码块），每次
 * token 批次都要擦除并重写 200+ 行，导致严重频闪甚至卡死。
 *
 * 解决方案：
 *   1. 最多展示最近 MAX_VISIBLE_LINES 行（live area 保持矮小）
 *   2. 逐行渲染（而非单个巨型 <Text> block），Ink layout 更快
 *   3. 流结束后全文移入 MessageList（Static），live area 恢复极小
 */

import React, { useState, useEffect, useRef } from 'react'
import { Box, Text } from 'ink'

const FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

/** live area 最多展示的行数，超出时只显示最后 N 行 */
const MAX_VISIBLE_LINES = 20

interface StreamViewProps {
  text: string
  active: boolean
}

export function StreamView({ text, active }: StreamViewProps) {
  const [frame, setFrame] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 仅在「等待首 token」阶段运行 spinner；有文本后立即停止，避免多余 re-render
  useEffect(() => {
    if (active && !text) {
      timerRef.current = setInterval(
        () => setFrame(f => (f + 1) % FRAMES.length),
        80,
      )
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [active, !text]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!active && !text) return null

  // 只取最后 MAX_VISIBLE_LINES 行展示，保持 live area 高度有界
  const allLines = text ? text.split(/\r?\n/) : []
  const clipped = allLines.length > MAX_VISIBLE_LINES
  const displayLines = clipped
    ? allLines.slice(-MAX_VISIBLE_LINES)
    : allLines

  return (
    <Box flexDirection="column" marginBottom={1}>

      {/* 标题行 */}
      <Box>
        <Text bold color="cyan">AI</Text>
        {active && !text && (
          <>
            <Text color="gray">{'  '}</Text>
            <Text color="cyan">{FRAMES[frame]}</Text>
            <Text color="gray" dimColor>  思考中…  </Text>
            <Text color="gray" dimColor>ESC 取消</Text>
          </>
        )}
        {active && text && <Text color="gray" dimColor>  ▍</Text>}
        {clipped && (
          <Text color="gray" dimColor>
            {`  … (已省略前 ${allLines.length - MAX_VISIBLE_LINES} 行)`}
          </Text>
        )}
      </Box>

      {/* 逐行渲染，避免单个巨型 Text block 拖慢 Ink layout 计算 */}
      {displayLines.map((line, i) => {
        const isLast = i === displayLines.length - 1
        return (
          <Box key={i} paddingLeft={3}>
            <Text color="white">
              {line || ' '}
              {active && isLast ? <Text color="cyan">▋</Text> : null}
            </Text>
          </Box>
        )
      })}

    </Box>
  )
}
