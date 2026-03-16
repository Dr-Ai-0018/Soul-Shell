/**
 * useBridge.ts — bridge 事件 → dispatch
 *
 * 职责：
 *  - 创建 PythonBridge，挂到 bridgeRef
 *  - 订阅 bridge 事件，翻译为 Action 并 dispatch
 *  - token 批量合并（50ms 窗口）：防止逐 token re-render → Ink 擦写 N 行频闪
 *  - shell 输出批量合并（80ms 窗口）：防止大量 output 事件冲击 Static
 *  - done 到来前立即 flush token/output buffer，避免丢失最后几个 token
 */

import { useEffect } from 'react'
import type { MutableRefObject, Dispatch } from 'react'
import { PythonBridge } from '../bridge.js'
import { newShellId } from '../ids.js'
import type { Action, PyMsg } from '../types.js'

// ─── Token 批量合并 ──────────────────────────────────────────────────────────

function makeTokenBatcher(dispatch: Dispatch<Action>) {
  let buf = ''
  let lastId = ''
  let timer: ReturnType<typeof setTimeout> | null = null

  function flush() {
    if (timer) { clearTimeout(timer); timer = null }
    if (buf && lastId) {
      dispatch({ type: 'TOKEN_RECEIVED', id: lastId, text: buf })
      buf = ''
    }
  }

  function push(id: string, text: string) {
    if (lastId && lastId !== id) {
      flush()  // 切换 query 时立即 flush 旧的
    }
    lastId = id
    buf += text
    if (!timer) {
      timer = setTimeout(flush, 50)  // 50ms 窗口 ≈ 20fps 上限
    }
  }

  return { push, flush }
}

// ─── Shell 输出批量合并 ──────────────────────────────────────────────────────

function makeOutputBatcher(dispatch: Dispatch<Action>) {
  const bufs: Record<string, string> = {}
  let timer: ReturnType<typeof setTimeout> | null = null

  function flush() {
    if (timer) { clearTimeout(timer); timer = null }
    for (const [id, text] of Object.entries(bufs)) {
      if (text) dispatch({ type: 'OUTPUT_RECEIVED', id, text, exit: null })
      delete bufs[id]
    }
  }

  function pushText(id: string, text: string) {
    bufs[id] = (bufs[id] ?? '') + text
    if (!timer) {
      timer = setTimeout(flush, 80)  // 80ms 窗口，shell 输出比 token 少，稍宽松
    }
  }

  function pushExit(id: string, exit: number) {
    // 先 flush 该 id 的待发文本，再立即发 exit
    if (bufs[id]) {
      dispatch({ type: 'OUTPUT_RECEIVED', id, text: bufs[id], exit: null })
      delete bufs[id]
    }
    dispatch({ type: 'OUTPUT_RECEIVED', id, text: '', exit })
  }

  return { pushText, pushExit }
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useBridge(
  bridgeRef: MutableRefObject<PythonBridge | null>,
  dispatch: Dispatch<Action>,
): void {
  useEffect(() => {
    const bridge = new PythonBridge()
    bridgeRef.current = bridge

    const token = makeTokenBatcher(dispatch)
    const output = makeOutputBatcher(dispatch)

    bridge.on('ready', () => dispatch({ type: 'CONN_READY' }))

    bridge.on('close', (code: number | null) =>
      dispatch({ type: 'CONN_ERROR', code: code ?? 1 }),
    )

    bridge.on('message', (msg: PyMsg) => {
      switch (msg.type) {

        case 'token':
          token.push(msg.id, msg.text)
          break

        case 'cmd':
          // cmd 到来前先 flush 该 query 的 token，保持文本顺序一致
          token.flush()
          dispatch({
            type: 'CMD_RECEIVED',
            id: msg.id,
            cmd: msg.cmd,
            shellId: newShellId(),
          })
          break

        case 'done':
          // ⚠️ 必须先 flush token，再派发 QUERY_DONE
          // 否则剩余 token 在 timer 里等待时，activeQueryId 已被清空，会被静默丢弃
          token.flush()
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
          if (msg.exit !== null) {
            output.pushExit(msg.id, msg.exit)
          } else if (msg.text) {
            output.pushText(msg.id, msg.text)
          }
          break

        case 'error':
          token.flush()
          dispatch({ type: 'ERROR_RECEIVED', id: msg.id, msg: msg.msg })
          break

        case 'react':
          dispatch({ type: 'REACT_RECEIVED', text: msg.text })
          break

        // pong：bridge 内部处理，无需 dispatch
      }
    })

    return () => bridge.destroy()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}
