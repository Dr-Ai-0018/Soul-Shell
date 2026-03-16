/**
 * useKeys.ts — 键盘事件路由
 *
 * 优先级（从高到低）：
 *   层 1  Ctrl+C          → 取消 activeQuery + exit()
 *   层 2  cmdQueue 非空   → y / n / q 处理队首 cmd（其余键忽略）
 *   层 3  querying 状态   → ESC 取消 AI 流
 *   层 4  输入框编辑       → idle 和 querying 均允许编辑；仅 idle 时可 Enter 提交
 *
 * 输入模式（idle 下 Enter 提交时）：
 *   裸文本           → 直接执行 shell 命令
 *   ?  前缀          → 单轮 AI 查询（无反馈循环）
 *   ?? 前缀          → 自动模式：AI 提命令 → 用户确认 → 结果反馈给 AI → 循环至多 10 轮
 */

import type { MutableRefObject, Dispatch } from 'react'
import { useInput } from 'ink'
import { PythonBridge } from '../bridge.js'
import { newQueryId, newShellId } from '../ids.js'
import type { SessionState, Action } from '../types.js'

/**
 * ?? 自动模式协议头，注入到第一条用户消息里，让 AI 知道规则。
 * 与 commit 7cf3ad1 中 Python _AUTO_PROTOCOL 设计一致。
 */
const AUTO_PROTOCOL =
`【连续执行模式】你现在处于自主任务执行模式：
- 先简短描述整体执行计划
- 每次只给一条命令（<cmd>命令</cmd>），看到我的反馈再给下一条，不要一次给多条
- 遇到报错，分析原因后调整方案，不要重复失败的命令
- 所有步骤完成后必须在回复末尾输出 [Done]，否则系统会继续等待你的下一条命令
任务：`

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

    // ── 层 2：cmd 确认模式（拦截所有键，只处理 y/n/q）────────────────────────
    if (state.cmdQueue.length > 0) {
      const head = state.cmdQueue[0]

      if (char === 'y' || char === 'Y') {
        bridge?.shell(head.shellId, head.cmd)
        dispatch({ type: 'CMD_CONFIRM', shellId: head.shellId })
      } else if (char === 'n' || char === 'N') {
        dispatch({ type: 'CMD_SKIP', shellId: head.shellId })
      } else if (char === 'q' || char === 'Q' || key.escape) {
        if (state.activeQueryId) bridge?.cancel(state.activeQueryId)
        dispatch({ type: 'CMD_CANCEL_ALL' })
      }
      // 其余键（包括中文 IME 字母）不做任何处理，避免误触
      return
    }

    // ── 层 3：ESC 取消正在进行的 AI 流 ──────────────────────────────────────
    if (state.phase === 'querying' && key.escape) {
      if (state.activeQueryId) bridge?.cancel(state.activeQueryId)
      dispatch({ type: 'QUERY_CANCEL' })
      return
    }

    // ── 层 4：输入框编辑 ──────────────────────────────────────────────────────
    // idle 和 querying 均可编辑；仅 idle 时才允许 Enter 提交

    const { inputText, cursorPos } = state

    // Enter：提交（仅在 idle 时有效）
    if (key.return) {
      if (state.phase !== 'idle') return
      const text = inputText.trim()
      if (!text || state.connStatus !== 'ready' || !bridge?.isReady()) return

      // ?? 双问号 → 自动模式（agentic loop）
      const autoMatch = text.match(/^[?？]{2}\s*/)
      if (autoMatch) {
        const taskText = text.slice(autoMatch[0].length).trim()
        if (!taskText) return
        const queryId = newQueryId()
        const fullText = AUTO_PROTOCOL + taskText
        dispatch({ type: 'SUBMIT_AUTO', text: fullText, queryId })
        bridge.query(queryId, fullText, state.history.slice(-20))
        return
      }

      // ? 单问号 → 单轮 AI 查询
      const singleMatch = text.match(/^[?？]\s*/)
      if (singleMatch) {
        const queryText = text.slice(singleMatch[0].length).trim()
        if (!queryText) return
        const queryId = newQueryId()
        dispatch({ type: 'SUBMIT_QUERY', text: queryText, queryId })
        bridge.query(queryId, queryText, state.history.slice(-20))
        return
      }

      // 裸文本 → 直接执行 shell 命令
      const shellId = newShellId()
      dispatch({ type: 'SUBMIT_SHELL', cmd: text, shellId })
      bridge.shell(shellId, text)
      return
    }

    // ── 光标移动 ─────────────────────────────────────────────────────────────

    if (key.leftArrow) {
      dispatch({ type: 'INPUT_SET', text: inputText, cursorPos: Math.max(0, cursorPos - 1) })
      return
    }
    if (key.rightArrow) {
      dispatch({ type: 'INPUT_SET', text: inputText, cursorPos: Math.min(inputText.length, cursorPos + 1) })
      return
    }
    if (key.ctrl && char === 'a') {
      dispatch({ type: 'INPUT_SET', text: inputText, cursorPos: 0 })
      return
    }
    if (key.ctrl && char === 'e') {
      dispatch({ type: 'INPUT_SET', text: inputText, cursorPos: inputText.length })
      return
    }

    // ── 删除 ─────────────────────────────────────────────────────────────────

    if (key.backspace || key.delete) {
      if (cursorPos > 0) {
        const newText = inputText.slice(0, cursorPos - 1) + inputText.slice(cursorPos)
        dispatch({ type: 'INPUT_SET', text: newText, cursorPos: cursorPos - 1 })
      }
      return
    }

    // ── 字符插入（在光标处）──────────────────────────────────────────────────

    if (char && !key.ctrl && !key.meta) {
      // 过滤 ASCII 控制字符（< 32），防止 IME 内部序列漏进来导致光标错位
      const cp = char.codePointAt(0) ?? 0
      if (cp < 32) return

      const newText = inputText.slice(0, cursorPos) + char + inputText.slice(cursorPos)
      const insertLen = Array.from(char).length
      dispatch({ type: 'INPUT_SET', text: newText, cursorPos: cursorPos + insertLen })
    }
  })
}
