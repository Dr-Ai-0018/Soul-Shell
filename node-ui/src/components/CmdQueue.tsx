import React from 'react'
import { Box, Text } from 'ink'
import type { PendingCmd } from '../types.js'

interface CmdQueueProps {
  queue: PendingCmd[]
}

export function CmdQueue({ queue }: CmdQueueProps) {
  if (queue.length === 0) return null

  const head = queue[0]
  const remaining = queue.length - 1

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor="magenta"
      paddingX={2}
      marginBottom={1}
    >
      <Text bold color="magenta"> ⚙ 命令确认</Text>
      <Text>
        {'  '}<Text bold color="yellow">$ {head.cmd}</Text>
      </Text>
      {remaining > 0 && (
        <Text color="gray">{'  '}还有 {remaining} 个命令待确认</Text>
      )}
      <Text color="gray">
        {'  '}[<Text color="green">y</Text>] 执行{'  '}
        [<Text color="yellow">n</Text>] 跳过{'  '}
        [<Text color="red">q</Text>] 取消全部
      </Text>
    </Box>
  )
}
