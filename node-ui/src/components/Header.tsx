import React from 'react'
import { Box, Text } from 'ink'
import type { ConnStatus } from '../types.js'

interface HeaderProps {
  connStatus: ConnStatus
}

const STATUS = {
  ready:      { dot: '●', label: '已连接',  color: 'green'  },
  connecting: { dot: '○', label: '连接中…', color: 'yellow' },
  error:      { dot: '✗', label: '已断开',  color: 'red'    },
} as const

export function Header({ connStatus }: HeaderProps) {
  const { dot, label, color } = STATUS[connStatus]
  const borderColor = connStatus === 'ready' ? 'cyan' : connStatus === 'error' ? 'red' : 'yellow'

  return (
    <Box borderStyle="round" borderColor={borderColor} paddingX={1} marginBottom={1}>
      <Text bold color="cyanBright">Soul-Shell</Text>
      <Text>  </Text>
      <Text color={color}>{dot} {label}</Text>
      <Text dimColor color="gray">    ESC 取消  Ctrl+C 退出</Text>
    </Box>
  )
}
