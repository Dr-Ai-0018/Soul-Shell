/**
 * useBridge.ts — bridge 事件 → dispatch
 *
 * 职责：
 *  - 创建 PythonBridge，挂到 bridgeRef
 *  - 订阅 bridge 事件，翻译为 Action 并 dispatch
 *  - 生成 shellId（新命名空间，不复用 queryId）
 *  - 不直接调用 bridge.shell()，执行决策留给 useKeys
 */

import { useEffect } from 'react'
import type { MutableRefObject, Dispatch } from 'react'
import { PythonBridge } from '../bridge.js'
import { newShellId } from '../ids.js'
import type { Action, PyMsg } from '../types.js'

export function useBridge(
  bridgeRef: MutableRefObject<PythonBridge | null>,
  dispatch: Dispatch<Action>,
): void {
  useEffect(() => {
    const bridge = new PythonBridge()
    bridgeRef.current = bridge

    bridge.on('ready', () => dispatch({ type: 'CONN_READY' }))

    bridge.on('close', (code: number | null) =>
      dispatch({ type: 'CONN_ERROR', code: code ?? 1 }),
    )

    bridge.on('message', (msg: PyMsg) => {
      switch (msg.type) {
        case 'token':
          dispatch({ type: 'TOKEN_RECEIVED', id: msg.id, text: msg.text })
          break

        case 'cmd':
          // shellId 在这里生成并绑定到 PendingCmd，不会和 queryId 冲突
          dispatch({
            type: 'CMD_RECEIVED',
            id: msg.id,
            cmd: msg.cmd,
            shellId: newShellId(),
          })
          break

        case 'done':
          dispatch({ type: 'QUERY_DONE', id: msg.id })
          break

        case 'risk':
          dispatch({
            type: 'RISK_RECEIVED',
            id: msg.id,
            score: msg.score,
            cmd: msg.cmd,
          })
          break

        case 'output':
          dispatch({
            type: 'OUTPUT_RECEIVED',
            id: msg.id,
            text: msg.text,
            exit: msg.exit,
          })
          break

        case 'error':
          dispatch({ type: 'ERROR_RECEIVED', id: msg.id, msg: msg.msg })
          break

        case 'react':
          dispatch({ type: 'REACT_RECEIVED', text: msg.text })
          break

        // pong：bridge 内部处理
      }
    })

    return () => bridge.destroy()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}
