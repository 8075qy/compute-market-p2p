import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'
import { emitRealtime } from '@/composables/useRealtimeEvents'
import type { Notification } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const HEARTBEAT_INTERVAL = 25_000
const BASE_RECONNECT_DELAY = 3_000
const MAX_RECONNECT_DELAY = 30_000

function buildWsUrl(): string {
  let protocol: string
  let host: string
  if (API_BASE.startsWith('http://') || API_BASE.startsWith('https://')) {
    const url = new URL(API_BASE)
    protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    host = url.host
  } else {
    protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    host = window.location.host
  }
  return `${protocol}//${host}/api/v1/ws/notifications`
}

export function useNotificationSocket() {
  const authStore = useAuthStore()
  const notificationStore = useNotificationStore()
  const connected = ref(false)

  let socket: WebSocket | null = null
  let heartbeatTimer: number | null = null
  let reconnectTimer: number | null = null
  let reconnectAttempts = 0
  let closedByUser = false

  function clearHeartbeat() {
    if (heartbeatTimer !== null) {
      window.clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function clearReconnect() {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function startHeartbeat() {
    clearHeartbeat()
    heartbeatTimer = window.setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send('ping')
      }
    }, HEARTBEAT_INTERVAL)
  }

  function scheduleReconnect() {
    if (reconnectTimer !== null) return
    const delay = Math.min(BASE_RECONNECT_DELAY * 2 ** reconnectAttempts, MAX_RECONNECT_DELAY)
    reconnectAttempts += 1
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      if (!authStore.isAuthenticated) return
      connect()
    }, delay)
  }

  function connect() {
    const token = authStore.accessToken
    if (!token) return
    if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) {
      return
    }
    closedByUser = false
    clearReconnect()

    const url = `${buildWsUrl()}?token=${encodeURIComponent(token)}`
    socket = new WebSocket(url)

    socket.onopen = () => {
      connected.value = true
      reconnectAttempts = 0
      startHeartbeat()
    }

    socket.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'notification' && message.data) {
          notificationStore.pushNotification(message.data as Notification)
          return
        }
        if ((message.type === 'task_status' || message.type === 'node_status') && message.data) {
          emitRealtime(message.type, message.data)
        }
      } catch {
        // 心跳 pong 等非 JSON 消息忽略
      }
    }

    socket.onclose = () => {
      connected.value = false
      clearHeartbeat()
      socket = null
      if (!closedByUser) {
        scheduleReconnect()
      }
    }

    socket.onerror = () => {
      socket?.close()
    }
  }

  function disconnect() {
    closedByUser = true
    clearHeartbeat()
    clearReconnect()
    reconnectAttempts = 0
    socket?.close()
    socket = null
    connected.value = false
  }

  onMounted(() => {
    if (authStore.isAuthenticated) connect()
  })

  onBeforeUnmount(() => disconnect())

  watch(
    () => authStore.isAuthenticated,
    (authenticated) => {
      if (authenticated) connect()
      else disconnect()
    }
  )

  return { connected, disconnect }
}