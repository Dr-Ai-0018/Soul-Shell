import React from 'react'
import { Box, Text } from 'ink'
import type { SessionState } from '../types.js'

type InputBarState = Pick<SessionState, 'connStatus' | 'phase' | 'cmdQueue' | 'inputText'>

interface InputBarProps {
  state: InputBarState
}

export function InputBar({ state }: InputBarProps) {
  const { connStatus, phase, cmdQueue, inputText } = state

  const hasPendingCmd = cmdQueue.length > 0
  const isQuerying = phase === 'querying' && !hasPendingCmd
  const busy = hasPendingCmd || isQuerying || connStatus !== 'ready'

  // 根据输入内容决定前缀样式：? 开头 → AI 模式，否则 → shell 模式
  const isAiMode = /^[?？]/.test(inputText)

  return (
    <Box
      borderStyle="single"
      borderColor={busy ? 'gray' : isAiMode ? 'cyan' : 'blueBright'}
      paddingX={1}
    >
      {connStatus === 'error' ? (
        <Text color="red">✗ 连接已断开，请重启</Text>
      ) : connStatus !== 'ready' ? (
        <Text color="gray">连接中，请稍候…</Text>
      ) : hasPendingCmd ? (
        <Text color="magenta">等待命令确认  [y] 执行  [n] 跳过  [q] 取消</Text>
      ) : isQuerying ? (
        <Text color="yellow">⟳  AI 响应中…  [ESC 取消]</Text>
      ) : (
        <>
          <Text bold color={isAiMode ? 'cyan' : 'blueBright'}>
            {isAiMode ? '?  ' : '$  '}
          </Text>
          <Text>{inputText}</Text>
          <Text color={isAiMode ? 'cyan' : 'blueBright'}>▋</Text>
        </>
      )}
    </Box>
  )
}
