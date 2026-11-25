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

const showBack = computed(() => route.name !== 'home')
const pageTitle = computed(() => route.meta.title as string || '')

function goBack() {
  router.back()
}

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
</script>

<template>
  <nav class="navbar" :class="{ 'has-back': showBack }">
    <div class="navbar-left">
      <button v-if="showBack" class="navbar-btn" @click="goBack" aria-label="返回">
        <Icon name="arrow-left" class="icon-lg" />
      </button>
      <h1 class="navbar-title">{{ pageTitle }}</h1>
    </div>
    <div class="navbar-right">
      <button class="navbar-btn navbar-notify" @click="router.push('/notifications')" aria-label="通知">
        <Icon :name="notificationStore.unreadCount > 0 ? 'bell-active' : 'bell'" class="icon-lg" />
        <span v-if="notificationStore.unreadCount > 0" class="navbar-badge">
          {{ notificationStore.unreadCount > 99 ? '99+' : notificationStore.unreadCount }}
        </span>
      </button>
      <button class="navbar-btn" @click="router.push('/settings')" aria-label="设置">
        <Icon name="settings" class="icon-lg" />
      </button>
    </div>
  </nav>
</template>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.navbar-left,
.navbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.navbar-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: -0.02em;
  margin-left: var(--space-8);
}

.navbar.has-back .navbar-title {
  margin-left: 0;
}

/* 桌面端：隐藏移动端顶部栏，导航交由侧边栏承担 */
@media (min-width: 1024px) {
  .navbar {
    display: none;
  }
}

.navbar-notify {
  position: relative;
}

.navbar-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 16px;
  height: 16px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-pill);
  background: var(--color-danger);
  color: var(--color-text);
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
}
</style>