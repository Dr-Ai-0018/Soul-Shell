/** ID 生成器：前缀命名空间隔离 query 和 shell，防止 Python _tasks 冲突 */
let _q = 0
let _s = 0
let _m = 0

export const newQueryId = (): string => `q${++_q}`
export const newShellId = (): string => `s${++_s}`
export const newMsgId  = (): string => `m${++_m}`
