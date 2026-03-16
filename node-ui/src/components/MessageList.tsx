import React from 'react'
import { Static, Box, Text } from 'ink'
import type { ChatMsg } from '../types.js'

const riskColor  = (s: number) => s >= 70 ? 'red' : s >= 40 ? 'yellow' : 'green'
const riskLabel  = (s: number) => s >= 70 ? '高危' : s >= 40 ? '中危' : '低危'

function MsgItem({ msg }: { msg: ChatMsg }) {
  switch (msg.role) {
    case 'user':
      return (
        <Box marginBottom={1}>
          <Text bold color="blueBright">You  </Text>
          <Text bold color="white">{msg.text}</Text>
        </Box>
      )

    case 'ai':
      return (
        <Box flexDirection="column" marginBottom={1}>
          <Text bold color="cyan">AI</Text>
          <Box paddingLeft={3}>
            <Text color="white">{msg.text}</Text>
          </Box>
        </Box>
      )

    case 'shell':
      return (
        <Box flexDirection="column" marginBottom={1}>
          <Text bold color="yellow">$ Output</Text>
          <Box paddingLeft={3} borderStyle="single" borderColor="yellow">
            <Text color="yellowBright">{msg.text}</Text>
          </Box>
        </Box>
      )

    case 'risk': {
      const score = msg.riskScore ?? 0
      return (
        <Box marginBottom={1}>
          <Text color={riskColor(score)}>
            ⚡ [{riskLabel(score)} {score}/100]{'  '}
          </Text>
          <Text dimColor color="gray">{msg.text}</Text>
        </Box>
      )
    }

    case 'system':
      return (
        <Box marginBottom={1}>
          <Text color="gray" dimColor>  {msg.text}</Text>
        </Box>
      )

    case 'error':
      return (
        <Box marginBottom={1}>
          <Text color="red">✗ {msg.text}</Text>
        </Box>
      )

    default:
      return null
  }
}

interface MessageListProps {
  messages: ChatMsg[]
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <Static items={messages}>
      {(msg) => <MsgItem key={msg.id} msg={msg} />}
    </Static>
  )
}
