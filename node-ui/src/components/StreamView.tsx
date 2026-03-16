import React from 'react'
import { Box, Text } from 'ink'

interface StreamViewProps {
  text: string
  /** true 时显示打字机光标 ▋ */
  active: boolean
}

export function StreamView({ text, active }: StreamViewProps) {
  if (!text && !active) return null

  return (
    <Box flexDirection="column" marginBottom={1}>
      <Text bold color="cyan">
        AI{'  '}
        <Text dimColor color="gray">▍</Text>
      </Text>
      <Box paddingLeft={3}>
        <Text color="white">
          {text}
          {active && <Text color="cyan">▋</Text>}
        </Text>
      </Box>
    </Box>
  )
}
