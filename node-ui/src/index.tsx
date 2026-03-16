/**
 * index.tsx — Soul-Shell Node UI 入口
 *
 * 架构：
 *   useReducer（store.ts）   → 纯函数状态机，防不可能状态
 *   useBridge（hooks/）      → bridge 事件 → dispatch
 *   useKeys（hooks/）        → 键盘分层路由 → dispatch + bridge
 *   组件（components/）      → 纯展示，无副作用
 *
 * ID 隔离：queryId (q1, q2…) 与 shellId (s1, s2…) 前缀不同，
 *          Python _tasks dict 永不冲突。
 */

import React, { useReducer, useRef } from 'react'
import { render, Box, useApp } from 'ink'
import { PythonBridge } from './bridge.js'
import { reducer, initialState } from './store.js'
import { useBridge } from './hooks/useBridge.js'
import { useKeys } from './hooks/useKeys.js'
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
