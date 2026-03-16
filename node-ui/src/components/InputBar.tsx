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

  return (
    <Box
      borderStyle="single"
      borderColor={busy ? 'gray' : 'blueBright'}
      paddingX={1}
    >
      {connStatus === 'error' ? (
        <Text color="red">✗ 连接已断开，请重启</Text>
      ) : connStatus !== 'ready' ? (
        <Text color="gray">连接中，请稍候…</Text>
      ) : hasPendingCmd ? (
        <Text color="magenta">等待命令确认  [y / n / q]</Text>
      ) : isQuerying ? (
        <Text color="yellow">⟳  AI 响应中…  [ESC 取消]</Text>
      ) : (
        <>
          <Text bold color="blueBright">›  </Text>
          <Text>{inputText}</Text>
          <Text color="blueBright">▋</Text>
        </>
      )}
    </Box>
  )
}
