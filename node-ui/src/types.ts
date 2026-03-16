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

/** ?? 模式中正在执行的 shell 命令，用于收集输出以反馈给 AI */
export interface ExecRecord {
  cmd: string
  chunks: string[]
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
  cursorPos: number         // 光标在 inputText 中的位置（0 = 最左）

  // ── ?? 自动模式（agentic loop）────────────────────────────────────────────
  autoMode: boolean         // 当前是否在 ?? 循环中
  autoRound: number         // 已完成的轮次（0-indexed，最多 9）
  execTracker: Record<string, ExecRecord>  // shellId → 执行跟踪（收集输出）
  autoCmdResults: string[]  // 格式化的命令执行结果，等待反馈给 AI
}

// ─── Action 类型 ──────────────────────────────────────────────────────────────

export type Action =
  // 连接生命周期
  | { type: 'CONN_READY' }
  | { type: 'CONN_ERROR'; code: number }

  // 用户发送查询（? 前缀触发 AI）
  | { type: 'SUBMIT_QUERY'; text: string; queryId: string }

  // 用户发送自动任务（?? 前缀，触发 AI + 命令反馈循环）
  | { type: 'SUBMIT_AUTO'; text: string; queryId: string }

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

  // 输入框（text + cursorPos 同步更新）
  | { type: 'INPUT_SET'; text: string; cursorPos: number }

  // Python react：shell 执行后 AI 点评
  | { type: 'REACT_RECEIVED'; text: string }

  // ?? 自动模式
  | { type: 'AUTO_LOOP_NEXT'; queryId: string; feedback: string }  // 触发下一轮
  | { type: 'AUTO_DONE' }                                           // 循环结束
