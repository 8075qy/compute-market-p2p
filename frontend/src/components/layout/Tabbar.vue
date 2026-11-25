<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'
import Icon from '@/components/ui/Icon.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()

onMounted(() => {
  if (authStore.isAuthenticated) {
    notificationStore.fetchUnreadCount()
  }
})

watch(
  () => authStore.isAuthenticated,
  (authenticated) => {
    if (authenticated) {
      notificationStore.fetchUnreadCount()
    }
  }
)

const tabs = computed(() => {
  const baseTabs = [
    { name: 'home', label: '首页', icon: 'home', activeIcon: 'home-active' },
  ]

  if (authStore.isUser) {
    baseTabs.push(
      { name: 'supplier-nodes', label: '节点', icon: 'gpu', activeIcon: 'gpu-active' },
      { name: 'supplier-earnings', label: '收益', icon: 'earnings', activeIcon: 'earnings-active' },
      { name: 'demand-publish', label: '发布', icon: 'task', activeIcon: 'task-active' },
      { name: 'demand-tasks', label: '任务', icon: 'task', activeIcon: 'task-active' }
    )
  }

  if (authStore.isAdmin) {
    baseTabs.push(
      { name: 'admin', label: '管理', icon: 'bar-chart', activeIcon: 'bar-chart' }
    )
  }

  baseTabs.push(
    { name: 'settlement', label: '结算', icon: 'wallet', activeIcon: 'wallet' },
    { name: 'settings', label: '我的', icon: 'profile', activeIcon: 'profile-active' }
  )

  return baseTabs
})

const currentTab = computed(() => {
  const name = (route.name as string) || 'home'
  if (name.startsWith('admin')) return 'admin'
  return name
})

function navigate(tabName: string) {
  router.push({ name: tabName })
}
</script>

<template>
  <nav class="tabbar" role="tablist" aria-label="主导航">
    <div class="tabbar-brand" aria-hidden="true">
      <Icon name="gpu" class="tabbar-brand-icon" />
      <span>算力共享中心</span>
    </div>
    <button
      class="tabbar-item tabbar-notify"
      :class="{ active: currentTab === 'notifications' }"
      @click="router.push('/notifications')"
      role="tab"
      :aria-selected="currentTab === 'notifications'"
      aria-label="通知"
    >
      <Icon
        :name="notificationStore.unreadCount > 0 ? 'bell-active' : 'bell'"
        class="tabbar-icon"
        aria-hidden="true"
      />
      <span>通知</span>
      <span v-if="notificationStore.unreadCount > 0" class="tabbar-badge">
        {{ notificationStore.unreadCount > 99 ? '99+' : notificationStore.unreadCount }}
      </span>
    </button>
    <button
      v-for="tab in tabs"
      :key="tab.name"
      class="tabbar-item"
      :class="{ active: currentTab === tab.name }"
      @click="navigate(tab.name)"
      role="tab"
      :aria-selected="currentTab === tab.name"
      :aria-label="tab.label"
    >
      <Icon
        :name="currentTab === tab.name ? tab.activeIcon : tab.icon"
        class="tabbar-icon"
        aria-hidden="true"
      />
      <span>{{ tab.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.tabbar {
  display: flex;
  justify-content: space-around;
  align-items: center;
}

.tabbar-brand {
  display: none;
}

.tabbar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--space-4) var(--space-8);
  color: var(--color-text-muted);
  font-size: var(--text-xs);
  min-width: 60px;
  transition: color var(--transition-fast);
}

.tabbar-item.active {
  color: var(--color-primary);
}

.tabbar-item:active {
  opacity: 0.7;
}

.tabbar-icon {
  width: 24px;
  height: 24px;
}

/* 通知入口：移动端隐藏，由顶部导航栏铃铛承担 */
.tabbar-notify {
  display: none;
}

/* 桌面端：底部标签栏切换为左侧侧边栏 */
@media (min-width: 1024px) {
  .tabbar {
    top: 0;
    bottom: 0;
    left: 0;
    right: auto;
    width: var(--sidebar-width);
    height: auto;
    padding: var(--space-16) var(--space-8);
    flex-direction: column;
    justify-content: flex-start;
    align-items: stretch;
    gap: var(--space-4);
    border-top: none;
    border-right: 1px solid var(--color-line);
  }

  .tabbar-brand {
    display: flex;
    align-items: center;
    gap: var(--space-8);
    padding: var(--space-8) var(--space-12);
    margin-bottom: var(--space-12);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text);
  }

  .tabbar-brand-icon {
    width: 28px;
    height: 28px;
    color: var(--color-primary);
  }

  .tabbar-item {
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    gap: var(--space-8);
    width: 100%;
    min-width: 0;
    padding: var(--space-8) var(--space-12);
    font-size: var(--text-sm);
    border-radius: var(--radius-md);
    transition: background var(--transition-fast), color var(--transition-fast);
  }

  .tabbar-item:hover {
    background: var(--color-surface);
    color: var(--color-text);
  }

  .tabbar-item.active {
    color: var(--color-primary);
  }

  .tabbar-icon {
    width: 20px;
    height: 20px;
  }

  .tabbar-notify {
    display: flex;
  }

  .tabbar-badge {
    margin-left: auto;
    min-width: 18px;
    height: 18px;
    padding: 0 var(--space-4);
    border-radius: var(--radius-pill);
    background: var(--color-danger);
    color: var(--color-text);
    font-size: 10px;
    font-weight: 600;
    line-height: 18px;
    text-align: center;
  }
}
</style>