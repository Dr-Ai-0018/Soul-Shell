import React from 'react'
import { Box, Text } from 'ink'
import type { SessionState } from '../types.js'

// ─── 语法高亮 Token ───────────────────────────────────────────────────────────

type Segment = { text: string; color: string; bold?: boolean }

/**
 * 将输入文本解析为带颜色的片段（赛博朋克风）：
 *  - ? 前缀 → AI 模式，整体青色
 *  - 命令名  → 霓虹绿
 *  - 参数标志 (-x / --flag) → 霓虹粉
 *  - 引号字符串 → 霓虹黄
 *  - 路径       → 蓝紫
 *  - 数字       → 青色
 *  - 其余参数   → 白色
 */
function tokenize(text: string): Segment[] {
  if (!text) return []

  // AI 模式
  if (/^[?？]/.test(text)) {
    return [
      { text: text[0], color: 'cyanBright', bold: true },
      { text: text.slice(1), color: 'cyan' },
    ]
  }

  const segs: Segment[] = []
  let pos = 0
  let commandFound = false

  while (pos < text.length) {
    // 空白
    const spaceMatch = text.slice(pos).match(/^(\s+)/)
    if (spaceMatch) {
      segs.push({ text: spaceMatch[1], color: 'white' })
      pos += spaceMatch[1].length
      continue
    }

    // 带闭合的引号字符串
    const quotedMatch = text.slice(pos).match(/^(['"'])((?:\\.|[^\\])*?)\1/)
    if (quotedMatch) {
      segs.push({ text: quotedMatch[0], color: 'yellowBright' })
      pos += quotedMatch[0].length
      continue
    }

    // 未闭合的引号字符串（光标还在里面）
    const openQuote = text.slice(pos).match(/^(['"])(.*)$/)
    if (openQuote) {
      segs.push({ text: text.slice(pos), color: 'yellowBright' })
      break
    }

    // 普通 token（到下一个空白或引号为止）
    const wordMatch = text.slice(pos).match(/^[^\s'"]+/)
    if (wordMatch) {
      const word = wordMatch[0]
      let color: string
      let bold: boolean | undefined

      if (!commandFound) {
        color = 'greenBright'; bold = true; commandFound = true
      } else if (word.startsWith('--') || (word.startsWith('-') && word.length > 1)) {
        color = 'magentaBright'
      } else if (/^\d+(\.\d+)?$/.test(word)) {
        color = 'cyanBright'
      } else if (word.startsWith('/') || word.startsWith('~/') || word.includes('/')) {
        color = 'blueBright'
      } else {
        color = 'white'
      }

      segs.push({ text: word, color, bold })
      pos += word.length
      continue
    }

    // 兜底：逐字符
    segs.push({ text: text[pos], color: 'white' })
    pos++
  }

  return segs
}

/**
 * 将 segments 在 cursorPos 处分割，插入块状光标字符。
 * 光标字符用 inverse（反色）实现赛博朋克感。
 */
function renderWithCursor(segs: Segment[], cursorPos: number): React.ReactNode[] {
  const nodes: React.ReactNode[] = []
  let charIdx = 0
  let cursorPlaced = false

  for (const seg of segs) {
    if (cursorPlaced || cursorPos > charIdx + seg.text.length - 1) {
      nodes.push(
        <Text key={charIdx} color={seg.color} bold={seg.bold}>{seg.text}</Text>
      )
      charIdx += seg.text.length
      continue
    }

    // 光标在此 segment 内
    const rel = cursorPos - charIdx
    const before = seg.text.slice(0, rel)
    const cursorCh = seg.text[rel] ?? ' '
    const after = seg.text.slice(rel + 1)

    if (before)
      nodes.push(<Text key={`${charIdx}b`} color={seg.color} bold={seg.bold}>{before}</Text>)
    nodes.push(<Text key={`${charIdx}c`} inverse>{cursorCh}</Text>)
    if (after)
      nodes.push(<Text key={`${charIdx}a`} color={seg.color} bold={seg.bold}>{after}</Text>)

    charIdx += seg.text.length
    cursorPlaced = true
  }

  // 光标在最末（空文本也要显示）
  if (!cursorPlaced) {
    nodes.push(<Text key="end" inverse>{' '}</Text>)
  }

  return nodes
}

// ─── InputBar ────────────────────────────────────────────────────────────────

type InputBarState = Pick<SessionState, 'connStatus' | 'phase' | 'cmdQueue' | 'inputText' | 'cursorPos'>

interface InputBarProps {
  state: InputBarState
}

export function InputBar({ state }: InputBarProps) {
  const { connStatus, phase, cmdQueue, inputText, cursorPos } = state

  const hasPendingCmd = cmdQueue.length > 0
  const isQuerying = phase === 'querying' && !hasPendingCmd
  const isAiMode = /^[?？]/.test(inputText)

  // 边框颜色：连接异常 → 灰；等待确认 → 品红；AI 响应中 → 黄；AI 模式输入 → 青；正常 → 绿
  const borderColor =
    connStatus !== 'ready' ? 'gray'
    : hasPendingCmd ? 'magentaBright'
    : isQuerying ? 'yellow'
    : isAiMode ? 'cyanBright'
    : 'greenBright'

  return (
    <Box
      borderStyle="single"
      borderColor={borderColor}
      paddingX={1}
    >
      {connStatus === 'error' ? (
        <Text color="red">✗ 连接已断开，请重启</Text>
      ) : connStatus !== 'ready' ? (
        <Text color="gray">连接中，请稍候…</Text>
      ) : hasPendingCmd ? (
        <Text color="magentaBright">等待确认  [y] 执行  [n] 跳过  [q] 取消</Text>
      ) : (
        // idle 和 querying 均显示可编辑输入框
        <>
          {/* querying 时显示 AI 响应指示器 */}
          {isQuerying && (
            <Text color="yellow">⟳ </Text>
          )}
          <Text bold color={isAiMode ? 'cyanBright' : isQuerying ? 'yellow' : 'greenBright'}>
            {isAiMode ? '?  ' : '$  '}
          </Text>
          {renderWithCursor(tokenize(inputText), cursorPos)}
          {isQuerying && (
            <Text color="gray" dimColor>  ESC取消</Text>
          )}
        </>
      )}
    </Box>
  )
}
