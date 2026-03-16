import React from 'react'
import { Static, Box, Text } from 'ink'
import type { ChatMsg } from '../types.js'

// ─── Markdown 渲染 ────────────────────────────────────────────────────────────

/** 处理行内格式：`code` 和 **bold** */
function InlineMd({ text }: { text: string }) {
  const parts = text.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.length > 2 && part.startsWith('`') && part.endsWith('`')) {
          return <Text key={i} color="cyan">{part.slice(1, -1)}</Text>
        }
        if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) {
          return <Text key={i} bold>{part.slice(2, -2)}</Text>
        }
        return <Text key={i}>{part}</Text>
      })}
    </>
  )
}

/** 将 Markdown 字符串渲染为 Ink 组件树 */
function MarkdownView({ text }: { text: string }) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // ── 围栏代码块 ────────────────────────────────────────────────────────────
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      i++ // 跳过闭合的 ```
      elements.push(
        <Box key={elements.length} flexDirection="column" borderStyle="single" borderColor="gray" paddingX={1} marginTop={0}>
          {lang ? <Text color="gray" dimColor>{lang}</Text> : null}
          {codeLines.map((l, j) => (
            <Text key={j} color="green">{l || ' '}</Text>
          ))}
        </Box>
      )
      continue
    }

    // ── 标题 ──────────────────────────────────────────────────────────────────
    const h3 = line.match(/^### (.+)/)
    const h2 = line.match(/^## (.+)/)
    const h1 = line.match(/^# (.+)/)
    if (h1) { elements.push(<Text key={elements.length} bold color="white" underline>{h1[1]}</Text>); i++; continue }
    if (h2) { elements.push(<Text key={elements.length} bold color="cyan">{h2[1]}</Text>); i++; continue }
    if (h3) { elements.push(<Text key={elements.length} bold>{h3[1]}</Text>); i++; continue }

    // ── 无序列表 ──────────────────────────────────────────────────────────────
    const ulMatch = line.match(/^[-*] (.+)/)
    if (ulMatch) {
      elements.push(
        <Text key={elements.length}>{'  • '}<InlineMd text={ulMatch[1]} /></Text>
      )
      i++; continue
    }

    // ── 有序列表 ──────────────────────────────────────────────────────────────
    const olMatch = line.match(/^(\d+)\. (.+)/)
    if (olMatch) {
      elements.push(
        <Text key={elements.length}>{'  '}{olMatch[1]}. <InlineMd text={olMatch[2]} /></Text>
      )
      i++; continue
    }

    // ── 空行 ──────────────────────────────────────────────────────────────────
    if (!line.trim()) {
      elements.push(<Text key={elements.length}>{' '}</Text>)
      i++; continue
    }

    // ── 普通文本（含行内格式）────────────────────────────────────────────────
    elements.push(
      <Text key={elements.length}><InlineMd text={line} /></Text>
    )
    i++
  }

  return <Box flexDirection="column">{elements}</Box>
}

// ─── 消息条目 ─────────────────────────────────────────────────────────────────

const riskColor = (s: number) => s >= 70 ? 'red' : s >= 40 ? 'yellow' : 'green'
const riskLabel = (s: number) => s >= 70 ? '高危' : s >= 40 ? '中危' : '低危'

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
          <Box paddingLeft={3} flexDirection="column">
            <MarkdownView text={msg.text} />
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

// ─── 导出 ─────────────────────────────────────────────────────────────────────

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
