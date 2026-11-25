/** 时间友好展示工具：相对时间与本地化日期时间。 */

export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return '-'
  const diff = Date.now() - date.getTime()
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour

  if (diff < 0) return formatDateTime(dateStr)
  if (diff < minute) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`
  if (diff < 2 * day) return '昨天'
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`
  return formatDateTime(dateStr)
}

export function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return '-'
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}`
}

export function formatShortDate(dateStr: string): string {
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return '-'
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const now = new Date()
  return date.getFullYear() === now.getFullYear()
    ? `${m}-${d}`
    : `${date.getFullYear()}-${m}-${d}`
}

/** 手机号脱敏：138****8000 */
export function maskPhone(phone?: string | null): string {
  if (!phone) return '-'
  if (phone.length < 7) return phone
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`
}