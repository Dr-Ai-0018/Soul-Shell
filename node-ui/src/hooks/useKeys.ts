/**
 * useKeys.ts — 键盘事件路由
 *
 * 优先级（从高到低）：
 *   层 1  Ctrl+C          → 取消 activeQuery + exit()
 *   层 2  cmdQueue 非空   → y / n / q 处理队首 cmd
 *   层 3  querying 状态   → ESC 取消 AI 流
 *   层 4  idle 状态       → Enter / Backspace / 字符 → 正常输入
 */

import type { MutableRefObject, Dispatch } from 'react'
import { useInput } from 'ink'
import { PythonBridge } from '../bridge.js'
import { newQueryId, newShellId } from '../ids.js'
import type { SessionState, Action } from '../types.js'

export function useKeys(
  state: SessionState,
  dispatch: Dispatch<Action>,
  bridgeRef: MutableRefObject<PythonBridge | null>,
  exit: () => void,
): void {
  useInput((char, key) => {
    const bridge = bridgeRef.current

    // ── 层 1：始终可退出 ─────────────────────────────────────────────────────
    if (key.ctrl && char === 'c') {
      if (state.activeQueryId) bridge?.cancel(state.activeQueryId)
      exit()
      return
    }

    // ── 层 2：cmd 确认模式（优先于 AI 流）───────────────────────────────────
    if (state.cmdQueue.length > 0) {
      const head = state.cmdQueue[0]

      if (char === 'y' || char === 'Y') {
        // 发 shell 请求（shellId 已在 CMD_RECEIVED 时生成）
        bridge?.shell(head.shellId, head.cmd)
        dispatch({ type: 'CMD_CONFIRM', shellId: head.shellId })
      } else if (char === 'n' || char === 'N') {
        dispatch({ type: 'CMD_SKIP', shellId: head.shellId })
      } else if (char === 'q' || char === 'Q' || key.escape) {
        // 取消整个 query
        if (state.activeQueryId) bridge?.cancel(state.activeQueryId)
        dispatch({ type: 'CMD_CANCEL_ALL' })
      }
      return
    }

    // ── 层 3：ESC 取消正在进行的 AI 流 ──────────────────────────────────────
    if (state.phase === 'querying' && key.escape) {
      if (state.activeQueryId) bridge?.cancel(state.activeQueryId)
      dispatch({ type: 'QUERY_CANCEL' })
      return
    }

    // ── 层 4：idle 模式，正常输入 ────────────────────────────────────────────
    if (state.phase !== 'idle') return

    if (key.return) {
      const text = state.inputText.trim()
      if (!text || state.connStatus !== 'ready' || !bridge?.isReady()) return

      // ? / ？ / ?? 前缀 → AI 查询；其余 → 直接执行 shell
      const aiPrefixMatch = text.match(/^[?？]{1,2}\s*/)
      if (aiPrefixMatch) {
        const queryText = text.slice(aiPrefixMatch[0].length).trim()
        if (!queryText) return
        const queryId = newQueryId()
        dispatch({ type: 'SUBMIT_QUERY', text: queryText, queryId })
        bridge.query(queryId, queryText, state.history.slice(-20))
      } else {
        const shellId = newShellId()
        dispatch({ type: 'SUBMIT_SHELL', cmd: text, shellId })
        bridge.shell(shellId, text)
      }
      return
    }

    if (key.backspace || key.delete) {
      dispatch({ type: 'INPUT_CHANGE', text: state.inputText.slice(0, -1) })
      return
    }

    if (char && !key.ctrl && !key.meta) {
      dispatch({ type: 'INPUT_CHANGE', text: state.inputText + char })
    }
  })
}
