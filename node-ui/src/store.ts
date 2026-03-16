/**
 * store.ts — 纯函数状态机
 *
 * 设计约束：
 *  - reducer 不产生副作用，不调用 bridge
 *  - AI 流（streamText）和 cmd 队列是正交的，互不阻塞
 *  - ?? 自动模式：execTracker 收集命令执行结果，autoCmdResults 积累后由
 *    useAutoLoop hook 读取并发起下一轮 AI 交互
 */

import { newMsgId } from './ids.js'
import type { SessionState, Action, ChatMsg, ExecRecord } from './types.js'

export const initialState: SessionState = {
  connStatus: 'connecting',
  phase: 'idle',
  activeQueryId: null,
  streamText: '',
  cmdQueue: [],
  messages: [],
  history: [],
  inputText: '',
  cursorPos: 0,
  autoMode: false,
  autoRound: 0,
  execTracker: {},
  autoCmdResults: [],
}

function addMsg(messages: ChatMsg[], msg: Omit<ChatMsg, 'id'>): ChatMsg[] {
  return [...messages, { id: newMsgId(), ...msg }]
}

/** 重置 ?? 自动模式相关字段 */
function resetAuto(): Partial<SessionState> {
  return {
    autoMode: false,
    autoRound: 0,
    execTracker: {},
    autoCmdResults: [],
  }
}

export function reducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {

    // ── 连接生命周期 ──────────────────────────────────────────────────────────

    case 'CONN_READY':
      return { ...state, connStatus: 'ready' }

    case 'CONN_ERROR':
      return {
        ...state,
        connStatus: 'error',
        phase: 'idle',
        activeQueryId: null,
        streamText: '',
        cmdQueue: [],
        ...resetAuto(),
        messages: addMsg(state.messages, {
          role: 'error',
          text: `Python 进程退出 (code=${action.code})`,
        }),
      }

    // ── 用户直接提交 shell 命令（无 AI，直接进队列）──────────────────────────

    case 'SUBMIT_SHELL':
      return {
        ...state,
        inputText: '',
        cursorPos: 0,
        messages: addMsg(state.messages, { role: 'user', text: action.cmd }),
      }

    // ── 用户发送查询（? 前缀 → AI，单轮，不循环）────────────────────────────

    case 'SUBMIT_QUERY':
      return {
        ...state,
        phase: 'querying',
        activeQueryId: action.queryId,
        inputText: '',
        cursorPos: 0,
        streamText: '',
        ...resetAuto(),
        history: [...state.history, { role: 'user', content: action.text }],
        messages: addMsg(state.messages, { role: 'user', text: action.text }),
      }

    // ── 用户发送自动任务（?? 前缀 → AI + 命令反馈循环）──────────────────────

    case 'SUBMIT_AUTO':
      return {
        ...state,
        phase: 'querying',
        activeQueryId: action.queryId,
        inputText: '',
        cursorPos: 0,
        streamText: '',
        autoMode: true,
        autoRound: 0,
        execTracker: {},
        autoCmdResults: [],
        history: [...state.history, { role: 'user', content: action.text }],
        messages: addMsg(state.messages, {
          role: 'system',
          text: `⟳ 自动模式  (最多 10 轮)`,
        }),
      }

    // ── AI 流式输出 ───────────────────────────────────────────────────────────

    case 'TOKEN_RECEIVED':
      if (action.id !== state.activeQueryId) return state
      return { ...state, streamText: state.streamText + action.text }

    case 'CMD_RECEIVED': {
      if (action.id !== state.activeQueryId) return state
      return {
        ...state,
        cmdQueue: [
          ...state.cmdQueue,
          { shellId: action.shellId, queryId: action.id, cmd: action.cmd },
        ],
      }
    }

    case 'QUERY_DONE': {
      if (action.id !== state.activeQueryId) return state
      const final = state.streamText
      const newMessages = final
        ? addMsg(state.messages, { role: 'ai', text: final })
        : state.messages
      const newHistory = final
        ? [...state.history, { role: 'assistant' as const, content: final }]
        : state.history
      const nextPhase = state.cmdQueue.length > 0 ? 'querying' : 'idle'
      return {
        ...state,
        phase: nextPhase,
        streamText: '',
        messages: newMessages,
        history: newHistory,
        activeQueryId: nextPhase === 'idle' ? null : state.activeQueryId,
      }
    }

    // ── Shell 执行反馈 ────────────────────────────────────────────────────────

    case 'RISK_RECEIVED':
      return {
        ...state,
        messages: addMsg(state.messages, {
          role: 'risk',
          text: action.cmd,
          riskScore: action.score,
        }),
      }

    case 'OUTPUT_RECEIVED': {
      let msgs = state.messages
      let execTracker = state.execTracker
      let autoCmdResults = state.autoCmdResults

      if (action.text) {
        msgs = addMsg(msgs, { role: 'shell', text: action.text })
        // 在 ?? 模式中积累输出块
        if (state.autoMode && action.id in execTracker) {
          const rec = execTracker[action.id]
          execTracker = {
            ...execTracker,
            [action.id]: { ...rec, chunks: [...rec.chunks, action.text] },
          }
        }
      }

      if (action.exit !== null) {
        const label =
          action.exit === 0 ? '✓ 执行成功' : `✗ 退出码 ${action.exit}`
        msgs = addMsg(msgs, { role: 'system', text: label })

        // ?? 模式：收到最终 exit，记录结果并从 tracker 移除
        if (state.autoMode && action.id in execTracker) {
          const { cmd, chunks } = execTracker[action.id]
          const output = chunks.join('').trim()
          const status = action.exit === 0 ? '成功' : `失败(exit ${action.exit})`
          const result = `\`${cmd}\` → ${status}\n${output || '（无输出）'}`
          autoCmdResults = [...autoCmdResults, result]
          const { [action.id]: _gone, ...rest } = execTracker
          execTracker = rest
        }
      }

      return { ...state, messages: msgs, execTracker, autoCmdResults }
    }

    case 'ERROR_RECEIVED':
      return {
        ...state,
        phase: 'idle',
        activeQueryId: null,
        streamText: '',
        cmdQueue: [],
        ...resetAuto(),
        messages: addMsg(state.messages, { role: 'error', text: action.msg }),
      }

    // ── 命令确认交互 ──────────────────────────────────────────────────────────

    case 'CMD_CONFIRM': {
      const confirmed = state.cmdQueue.find(c => c.shellId === action.shellId)
      const remaining = state.cmdQueue.filter(c => c.shellId !== action.shellId)
      const shouldIdle = remaining.length === 0 && state.streamText === ''

      // ?? 模式：开始跟踪这条命令的执行输出
      let execTracker = state.execTracker
      if (state.autoMode && confirmed) {
        execTracker = {
          ...execTracker,
          [action.shellId]: { cmd: confirmed.cmd, chunks: [] } satisfies ExecRecord,
        }
      }

      return {
        ...state,
        cmdQueue: remaining,
        phase: shouldIdle ? 'idle' : state.phase,
        activeQueryId: shouldIdle ? null : state.activeQueryId,
        execTracker,
      }
    }

    case 'CMD_SKIP': {
      const skipped = state.cmdQueue.find(c => c.shellId === action.shellId)
      const remaining = state.cmdQueue.filter(c => c.shellId !== action.shellId)
      const shouldIdle = remaining.length === 0 && state.streamText === ''

      // ?? 模式：跳过的命令也记录反馈
      let autoCmdResults = state.autoCmdResults
      if (state.autoMode && skipped) {
        autoCmdResults = [
          ...autoCmdResults,
          `\`${skipped.cmd}\` → 用户跳过`,
        ]
      }

      return {
        ...state,
        cmdQueue: remaining,
        phase: shouldIdle ? 'idle' : state.phase,
        activeQueryId: shouldIdle ? null : state.activeQueryId,
        autoCmdResults,
        messages: skipped
          ? addMsg(state.messages, { role: 'system', text: `↷ 跳过: ${skipped.cmd}` })
          : state.messages,
      }
    }

    case 'CMD_CANCEL_ALL':
      return {
        ...state,
        phase: 'idle',
        activeQueryId: null,
        streamText: '',
        cmdQueue: [],
        ...resetAuto(),
        messages: addMsg(state.messages, { role: 'system', text: '✗ 已取消' }),
      }

    case 'QUERY_CANCEL': {
      if (state.phase !== 'querying') return state
      const partial = state.streamText
      return {
        ...state,
        phase: 'idle',
        activeQueryId: null,
        streamText: '',
        cmdQueue: [],
        ...resetAuto(),
        messages: partial
          ? addMsg(state.messages, { role: 'ai', text: partial + ' [已取消]' })
          : addMsg(state.messages, { role: 'system', text: '✗ 已取消' }),
      }
    }

    // ── 输入框 ────────────────────────────────────────────────────────────────

    case 'INPUT_SET':
      return { ...state, inputText: action.text, cursorPos: action.cursorPos }

    case 'REACT_RECEIVED':
      return {
        ...state,
        messages: addMsg(state.messages, { role: 'ai', text: action.text }),
      }

    // ── ?? 自动模式循环 ────────────────────────────────────────────────────────

    case 'AUTO_LOOP_NEXT':
      // useAutoLoop hook 已确认条件满足，发起下一轮 AI 交互
      return {
        ...state,
        phase: 'querying',
        activeQueryId: action.queryId,
        streamText: '',
        autoRound: state.autoRound + 1,
        autoCmdResults: [],
        execTracker: {},
        history: [...state.history, { role: 'user', content: action.feedback }],
        messages: addMsg(state.messages, {
          role: 'system',
          text: `⟳ 第 ${state.autoRound + 2} 轮`,
        }),
      }

    case 'AUTO_DONE':
      return {
        ...state,
        ...resetAuto(),
        messages: addMsg(state.messages, {
          role: 'system',
          text: `✓ 自动模式完成（共 ${state.autoRound + 1} 轮）`,
        }),
      }

    default:
      return state
  }
}
