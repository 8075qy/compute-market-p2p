import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Notification, NotificationList } from '@/types'
import { api } from '@/composables/useApi'

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref<Notification[]>([])
  const unreadCount = ref(0)
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const isLoading = ref(false)

  const hasMore = computed(() => notifications.value.length < total.value)

  async function fetchUnreadCount() {
    try {
      const data = await api.get<{ unread_count: number }>('/notifications/unread-count')
      unreadCount.value = data.unread_count
    } catch {
      // 未读数获取失败不阻塞页面
    }
  }

  async function fetchNotifications(reset = false) {
    if (isLoading.value) return
    isLoading.value = true
    if (reset) {
      page.value = 1
      notifications.value = []
    }
    try {
      const data = await api.get<NotificationList>('/notifications', {
        page: page.value,
        page_size: pageSize.value,
      })
      if (reset) {
        notifications.value = data.items
      } else {
        notifications.value = [...notifications.value, ...data.items]
      }
      total.value = data.total
      page.value = data.page
    } finally {
      isLoading.value = false
    }
  }

  async function loadMore() {
    if (!hasMore.value || isLoading.value) return
    page.value += 1
    await fetchNotifications(false)
  }

  async function markRead(id: string) {
    try {
      await api.post<{ ok: boolean }>(`/notifications/${id}/read`)
      const target = notifications.value.find((n) => n.id === id)
      if (target && !target.is_read) {
        target.is_read = true
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    } catch {
      // 标记失败静默处理
    }
  }

  async function markAllRead() {
    try {
      const data = await api.post<{ updated: number }>('/notifications/read-all')
      notifications.value.forEach((n) => {
        n.is_read = true
      })
      unreadCount.value = 0
      return data.updated
    } catch {
      return 0
    }
  }

  function pushNotification(notification: Notification) {
    if (notifications.value.some((n) => n.id === notification.id)) return
    notifications.value = [notification, ...notifications.value]
    total.value += 1
    if (!notification.is_read) {
      unreadCount.value += 1
    }
  }

  return {
    notifications,
    unreadCount,
    total,
    page,
    pageSize,
    isLoading,
    hasMore,
    fetchUnreadCount,
    fetchNotifications,
    loadMore,
    markRead,
    markAllRead,
    pushNotification,
  }
})