export type RealtimeHandler = (data: any) => void

const handlers = new Set<RealtimeHandler>()

export function onRealtime(handler: RealtimeHandler): () => void {
  handlers.add(handler)
  return () => handlers.delete(handler)
}

export function emitRealtime(event: string, data: any): void {
  const payload = { event, data }
  handlers.forEach((handler) => {
    try {
      handler(payload)
    } catch {
      // 单个订阅者异常不影响其他订阅
    }
  })
}