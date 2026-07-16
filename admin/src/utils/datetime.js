/** 统一按东八区（北京时间）展示，与 API 的 +08:00 / Z 时间戳无关（客户端本地时区不影响） */
const BJ = 'Asia/Shanghai'

/**
 * @param {string|number|Date|null|undefined} value ISO 串或时间戳
 * @returns {string} 如 2026-04-24 19:43:40
 */
export function formatBeijingTime (value) {
  if (value == null || value === '') return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d
    .toLocaleString('sv-SE', {
      timeZone: BJ,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })
    .replace('T', ' ')
}
