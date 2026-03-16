/**
 * useAutoLoop.ts — ?? 自动模式反馈循环
 *
 * 触发条件（全部满足时启动下一轮）：
 *   1. autoMode = true
 *   2. phase = 'idle'（AI 本轮已流完）
 *   3. cmdQueue 为空（所有命令已确认/跳过）
 *   4. execTracker 为空（所有 shell 输出已收全）
 *   5. autoCmdResults 非空（本轮有实际执行结果可反馈）
 *
 * 终止条件：
 *   - AI 回复包含 [Done] / [DONE]
 *   - autoRound >= 9（第 10 轮结束）
 *   - 用户取消（CMD_CANCEL_ALL / QUERY_CANCEL / ERROR_RECEIVED 均重置 autoMode）
 */

import { useEffect } from 'react'
import type { MutableRefObject, Dispatch } from 'react'
import { PythonBridge } from '../bridge.js'
import { newQueryId } from '../ids.js'
import type { SessionState, Action } from '../types.js'

export function useAutoLoop(
  state: SessionState,
  dispatch: Dispatch<Action>,
  bridgeRef: MutableRefObject<PythonBridge | null>,
): void {
  const execTrackerSize = Object.keys(state.execTracker).length

  useEffect(() => {
    if (!state.autoMode) return
    if (state.phase !== 'idle') return
    if (state.cmdQueue.length > 0) return
    if (execTrackerSize > 0) return           // 还在等待 shell 输出
    if (state.autoCmdResults.length === 0) return  // 本轮没有执行任何命令

    // 检查 AI 是否已说完（[Done]）
    const lastAiMsg = [...state.messages].reverse().find(m => m.role === 'ai')
    const aiSaidDone =
      !!lastAiMsg?.text.includes('[Done]') ||
      !!lastAiMsg?.text.includes('[DONE]')

    if (aiSaidDone || state.autoRound >= 9) {
      dispatch({ type: 'AUTO_DONE' })
      return
    }

    // 构造反馈文本（格式同 commit 7cf3ad1 的 Python 实现）
    const feedback =
      '【命令执行结果】\n' +
      state.autoCmdResults.join('\n---\n') +
      '\n\n请继续。所有步骤完成后在回复末尾输出 [Done]。'

    const queryId = newQueryId()
    dispatch({ type: 'AUTO_LOOP_NEXT', queryId, feedback })
    bridgeRef.current?.query(queryId, feedback, state.history.slice(-20))
  }, [
    state.autoMode,
    state.phase,
    state.cmdQueue.length,
    execTrackerSize,
    state.autoCmdResults.length,
    state.autoRound,
  ]) // eslint-disable-line react-hooks/exhaustive-deps
}
