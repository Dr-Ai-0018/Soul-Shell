/**
 * store.ts — 纯函数状态机
 *
 * 设计约束：
 *  - reducer 不产生副作用，不调用 bridge
 *  - AI 流（streamText）和 cmd 队列是正交的，互不阻塞
 *  - phase 转换规则见各 case 注释
 */

import { newMsgId } from './ids.js'
import type { SessionState, Action, ChatMsg } from './types.js'

export const initialState: SessionState = {
  connStatus: 'connecting',
  phase: 'idle',
  activeQueryId: null,
  streamText: '',
  cmdQueue: [],
  messages: [],
  history: [],
  inputText: '',
}

function addMsg(messages: ChatMsg[], msg: Omit<ChatMsg, 'id'>): ChatMsg[] {
  return [...messages, { id: newMsgId(), ...msg }]
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
        messages: addMsg(state.messages, {
          role: 'error',
          text: `Python 进程退出 (code=${action.code})`,
        }),
      }

    // ── 用户直接提交 shell 命令（无 AI，直接进队列）──────────────────────────

    case 'SUBMIT_SHELL':
      // 只记录到消息历史，不改 phase（phase 留 idle，用户可继续输入）
      // Python 会异步返回 risk + output
      return {
        ...state,
        inputText: '',
        messages: addMsg(state.messages, { role: 'user', text: action.cmd }),
      }

    // ── 用户发送查询（? 前缀 → AI）───────────────────────────────────────────

    case 'SUBMIT_QUERY':
      // 前置条件由 useKeys 层保证（phase=idle, connStatus=ready）
      return {
        ...state,
        phase: 'querying',
        activeQueryId: action.queryId,
        inputText: '',
        streamText: '',
        history: [...state.history, { role: 'user', content: action.text }],
        messages: addMsg(state.messages, { role: 'user', text: action.text }),
      }

    // ── AI 流式输出 ───────────────────────────────────────────────────────────

    case 'TOKEN_RECEIVED':
      if (action.id !== state.activeQueryId) return state
      return { ...state, streamText: state.streamText + action.text }

    case 'CMD_RECEIVED': {
      // AI 提出命令，加入队列（不阻断流式输出，两条轨道独立）
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
      // AI 流结束
      // - cmdQueue 为空 → 回到 idle，可接受新输入
      // - cmdQueue 非空 → 保持 querying，等 cmd 全部处理完再 idle
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
        // cmdQueue 为空时顺便清 activeQueryId
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
      if (action.text) {
        msgs = addMsg(msgs, { role: 'shell', text: action.text })
      }
      if (action.exit !== null && action.exit !== undefined) {
        const label =
          action.exit === 0 ? '✓ 执行成功' : `✗ 退出码 ${action.exit}`
        msgs = addMsg(msgs, { role: 'system', text: label })
      }
      return { ...state, messages: msgs }
    }

    case 'ERROR_RECEIVED':
      return {
        ...state,
        phase: 'idle',
        activeQueryId: null,
        streamText: '',
        cmdQueue: [],   // 清掉残留的待确认命令，避免孤儿 shell 请求
        messages: addMsg(state.messages, { role: 'error', text: action.msg }),
      }

    // ── 命令确认交互 ──────────────────────────────────────────────────────────

    case 'CMD_CONFIRM': {
      const remaining = state.cmdQueue.filter(c => c.shellId !== action.shellId)
      // cmd 队列清空 且 AI 流也结束了 → 回到 idle
      const shouldIdle = remaining.length === 0 && state.streamText === ''
      return {
        ...state,
        cmdQueue: remaining,
        phase: shouldIdle ? 'idle' : state.phase,
        activeQueryId: shouldIdle ? null : state.activeQueryId,
      }
    }

    case 'CMD_SKIP': {
      const skipped = state.cmdQueue.find(c => c.shellId === action.shellId)
      const remaining = state.cmdQueue.filter(c => c.shellId !== action.shellId)
      const shouldIdle = remaining.length === 0 && state.streamText === ''
      return {
        ...state,
        cmdQueue: remaining,
        phase: shouldIdle ? 'idle' : state.phase,
        activeQueryId: shouldIdle ? null : state.activeQueryId,
        messages: skipped
          ? addMsg(state.messages, { role: 'system', text: `↷ 跳过: ${skipped.cmd}` })
          : state.messages,
      }
    }

    case 'CMD_CANCEL_ALL':
      // 取消整个 query（q 键或 ESC，由 useKeys 同时发 bridge.cancel）
      return {
        ...state,
        phase: 'idle',
        activeQueryId: null,
        streamText: '',
        cmdQueue: [],
        messages: addMsg(state.messages, { role: 'system', text: '✗ 已取消' }),
      }

    case 'QUERY_CANCEL': {
      // ESC 取消正在流式的 AI 输出（无 cmdQueue 时才触发此 action）
      if (state.phase !== 'querying') return state
      const partial = state.streamText
      return {
        ...state,
        phase: 'idle',
        activeQueryId: null,
        streamText: '',
        cmdQueue: [],
        messages: partial
          ? addMsg(state.messages, { role: 'ai', text: partial + ' [已取消]' })
          : addMsg(state.messages, { role: 'system', text: '✗ 已取消' }),
      }
    }

    // ── 输入框 ────────────────────────────────────────────────────────────────

    case 'INPUT_CHANGE':
      return { ...state, inputText: action.text }

    default:
      return state
  }
}
