/**
 * index.tsx — Soul-Shell Node UI 入口
 *
 * 架构：
 *   useReducer（store.ts）   → 纯函数状态机，防不可能状态
 *   useBridge（hooks/）      → bridge 事件 → dispatch（含 token 批量合并）
 *   useKeys（hooks/）        → 键盘分层路由 → dispatch + bridge
 *   useAutoLoop（hooks/）    → ?? 自动模式反馈循环
 *   组件（components/）      → 纯展示，无副作用
 *
 * 输入模式：
 *   裸文本  → 直接 shell 执行
 *   ?  前缀 → 单轮 AI 查询
 *   ?? 前缀 → 自动模式（AI 提命令 → 用户确认 → 结果反馈 → 循环至多 10 轮）
 */

import React, { useReducer, useRef } from 'react'
import { render, Box, useApp } from 'ink'
import { PythonBridge } from './bridge.js'
import { reducer, initialState } from './store.js'
import { useBridge } from './hooks/useBridge.js'
import { useKeys } from './hooks/useKeys.js'
import { useAutoLoop } from './hooks/useAutoLoop.js'
import { Header } from './components/Header.js'
import { MessageList } from './components/MessageList.js'
import { StreamView } from './components/StreamView.js'
import { CmdQueue } from './components/CmdQueue.js'
import { InputBar } from './components/InputBar.js'

function App() {
  const { exit } = useApp()
  const [state, dispatch] = useReducer(reducer, initialState)
  const bridgeRef = useRef<PythonBridge | null>(null)

  useBridge(bridgeRef, dispatch)
  useKeys(state, dispatch, bridgeRef, exit)
  useAutoLoop(state, dispatch, bridgeRef)

  return (
    <Box flexDirection="column" paddingX={1}>
      <Header connStatus={state.connStatus} />
      <MessageList messages={state.messages} />
      <StreamView text={state.streamText} active={state.phase === 'querying'} />
      <CmdQueue queue={state.cmdQueue} />
      <InputBar state={state} />
    </Box>
  )
}

render(<App />)
