<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNotificationStore } from '@/stores/notification'
import { Card, Button, Icon, Skeleton, EmptyState } from '@/components/ui'
import type { Notification, NotificationType } from '@/types'

const router = useRouter()
const notificationStore = useNotificationStore()

const typeMeta: Record<NotificationType, { icon: string; label: string; color: string }> = {
  task_completed: { icon: 'check-circle', label: '任务完成', color: 'var(--color-success)' },
  task_failed: { icon: 'alert-triangle', label: '任务失败', color: 'var(--color-danger)' },
  task_assigned: { icon: 'task', label: '调度完成', color: 'var(--color-primary)' },
  task_started: { icon: 'activity', label: '开始执行', color: 'var(--color-success)' },
  task_cancelled: { icon: 'x', label: '任务取消', color: 'var(--color-text-muted)' },
  settlement_paid: { icon: 'wallet', label: '结算到账', color: 'var(--color-primary)' },
  node_online: { icon: 'gpu', label: '节点上线', color: 'var(--color-success)' },
  node_offline: { icon: 'gpu', label: '节点离线', color: 'var(--color-danger)' },
  system: { icon: 'info', label: '系统通知', color: 'var(--color-text-muted)' },
}

function formatRelativeTime(dateStr: string) {
  const date = new Date(dateStr)
  const diff = Date.now() - date.getTime()
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour

  if (diff < minute) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`
  if (diff < 2 * day) return '昨天'
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`

  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const now = new Date()
  return y === now.getFullYear() ? `${m}-${d}` : `${y}-${m}-${d}`
}

async function handleClick(n: Notification) {
  if (!n.is_read) await notificationStore.markRead(n.id)
  if (!n.ref_id) return
  if (n.type === 'settlement_paid') {
    router.push('/settlement')
  } else {
    router.push(`/task/${n.ref_id}`)
  }
}

onMounted(async () => {
  await Promise.all([
    notificationStore.fetchNotifications(true),
    notificationStore.fetchUnreadCount(),
  ])
})
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <div class="notifications-header">
        <div>
          <h2 class="notifications-title">消息通知</h2>
          <p class="notifications-subtitle">任务与结算动态实时触达</p>
        </div>
        <Button
          v-if="notificationStore.unreadCount > 0"
          variant="outline"
          @click="notificationStore.markAllRead()"
        >
          全部已读
        </Button>
      </div>

      <Card>
        <div
          v-if="notificationStore.isLoading && notificationStore.notifications.length === 0"
          class="notification-skeleton"
        >
          <Skeleton type="card" v-for="i in 4" :key="i" />
        </div>

        <div v-else-if="notificationStore.notifications.length === 0" class="notification-empty">
          <EmptyState
            icon="bell"
            title="暂无通知"
            description="任务完成、失败与结算到账的消息会显示在这里"
          />
        </div>

        <div v-else class="notification-list">
          <div
            v-for="n in notificationStore.notifications"
            :key="n.id"
            class="notification-item"
            :class="{ unread: !n.is_read }"
            role="button"
            tabindex="0"
            @click="handleClick(n)"
            @keydown.enter="handleClick(n)"
          >
            <div class="notification-icon">
              <Icon
                :name="typeMeta[n.type].icon"
                class="icon-lg"
                :style="{ color: typeMeta[n.type].color }"
              />
            </div>
            <div class="notification-body">
              <div class="notification-title-row">
                <span class="notification-title">{{ n.title }}</span>
                <span v-if="!n.is_read" class="notification-dot" aria-hidden="true"></span>
              </div>
              <p class="notification-content">{{ n.content }}</p>
              <div class="notification-meta">
                <span class="notification-type">{{ typeMeta[n.type].label }}</span>
                <span class="notification-time">{{ formatRelativeTime(n.created_at) }}</span>
              </div>
            </div>
            <Icon
              name="chevron-right"
              class="icon-md notification-arrow"
              style="color: var(--color-text-muted);"
            />
          </div>
        </div>

        <div v-if="notificationStore.hasMore" class="notification-loadmore">
          <Button
            variant="ghost"
            block
            :loading="notificationStore.isLoading"
            @click="notificationStore.loadMore()"
          >
            加载更多
          </Button>
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.notifications-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-12);
  margin-bottom: var(--space-16);
}

.notifications-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text);
}

.notifications-subtitle {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin-top: var(--space-4);
}

.notification-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
  padding: var(--space-16);
}

.notification-empty {
  padding: var(--space-32) 0;
}

.notification-list {
  display: flex;
  flex-direction: column;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-12);
  padding: var(--space-16);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.notification-item + .notification-item {
  border-top: 1px solid var(--color-line);
}

.notification-item:hover {
  background: var(--color-surface);
}

.notification-item.unread {
  background: var(--color-primary-bg);
}

.notification-item.unread:hover {
  background: var(--color-primary-hover-bg);
}

.notification-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-card);
  background: var(--color-surface);
  flex-shrink: 0;
}

.notification-body {
  flex: 1;
  min-width: 0;
}

.notification-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.notification-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text);
}

.notification-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-circle);
  background: var(--color-primary);
  flex-shrink: 0;
}

.notification-content {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-top: var(--space-4);
  line-height: 1.5;
  word-break: break-all;
}

.notification-meta {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  margin-top: var(--space-8);
}

.notification-type {
  font-size: var(--text-xs);
  color: var(--color-primary);
}

.notification-time {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.notification-arrow {
  flex-shrink: 0;
  margin-top: var(--space-12);
}

.notification-loadmore {
  padding: var(--space-8) var(--space-16) var(--space-16);
}
</style>