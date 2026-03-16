// ─── Python → Node 消息（判别联合体）────────────────────────────────────────

export type PyMsg =
  | { type: 'token';  id: string; text: string }
  | { type: 'cmd';    id: string; cmd: string }
  | { type: 'done';   id: string }
  | { type: 'risk';   id: string; score: number; cmd: string }
  | { type: 'output'; id: string; text: string; exit: number | null }
  | { type: 'error';  id: string; msg: string }
  | { type: 'pong' }
  | { type: 'react';  id: string; text: string }

// ─── Node → Python 消息 ──────────────────────────────────────────────────────

export type NodeMsg =
  | { type: 'query';  id: string; text: string; history: HistoryEntry[] }
  | { type: 'shell';  id: string; cmd: string }
  | { type: 'cancel'; id: string }
  | { type: 'ping' }

// ─── 会话状态 ─────────────────────────────────────────────────────────────────

export type ConnStatus = 'connecting' | 'ready' | 'error'

/**
 * 用户交互通道的状态：
 *   idle     = 可接受新输入
 *   querying = AI 响应中（可 ESC 取消）
 *
 * 注意：phase 和 cmdQueue 是正交的——AI 还在流式输出时也可以有 cmd 待确认
 */
export type Phase = 'idle' | 'querying'

/** 等待用户 y/n/q 的命令（shellId 独立生成，永不等于 queryId）*/
export interface PendingCmd {
  shellId: string
  queryId: string
  cmd: string
}

export interface HistoryEntry {
  role: 'user' | 'assistant'
  content: string
}

export type MsgRole = 'user' | 'ai' | 'shell' | 'system' | 'error' | 'risk'

export interface ChatMsg {
  id: string
  role: MsgRole
  text: string
  riskScore?: number  // 仅 role=risk 时携带
}

export interface SessionState {
  connStatus: ConnStatus
  phase: Phase
  activeQueryId: string | null
  streamText: string        // 正在累积的 AI 流式文本
  cmdQueue: PendingCmd[]    // 待确认命令队列（支持多个）
  messages: ChatMsg[]       // 已完成的历史消息（进入 Static）
  history: HistoryEntry[]   // 发给 Python 的对话上下文
  inputText: string
}

// ─── Action 类型 ──────────────────────────────────────────────────────────────

export type Action =
  // 连接生命周期
  | { type: 'CONN_READY' }
  | { type: 'CONN_ERROR'; code: number }

  // 用户发送查询（? 前缀触发 AI）
  | { type: 'SUBMIT_QUERY'; text: string; queryId: string }

  // 用户直接提交 shell 命令（无 ? 前缀）
  | { type: 'SUBMIT_SHELL'; cmd: string; shellId: string }

  // Python 事件
  | { type: 'TOKEN_RECEIVED';  id: string; text: string }
  | { type: 'CMD_RECEIVED';    id: string; cmd: string; shellId: string }
  | { type: 'QUERY_DONE';      id: string }
  | { type: 'RISK_RECEIVED';   id: string; score: number; cmd: string }
  | { type: 'OUTPUT_RECEIVED'; id: string; text: string; exit: number | null }
  | { type: 'ERROR_RECEIVED';  id: string; msg: string }

  // 用户交互
  | { type: 'CMD_CONFIRM';    shellId: string }  // y
  | { type: 'CMD_SKIP';       shellId: string }  // n
  | { type: 'CMD_CANCEL_ALL' }                   // q 或 ESC（取消整个 query）
  | { type: 'QUERY_CANCEL' }                     // ESC（仅取消 AI 流，无待确认 cmd 时）
  | { type: 'INPUT_CHANGE';   text: string }
