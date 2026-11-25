<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { Card, Icon, Skeleton } from '@/components/ui'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const adminStore = useAdminStore()
const { danger } = useToast()

const isLoading = ref(false)

const stats = computed(() => [
  {
    key: 'online_nodes',
    label: '在线节点',
    display: formatNumber(adminStore.dashboard?.online_nodes ?? 0),
    icon: 'gpu',
    tone: 'success',
  },
  {
    key: 'pending_tasks',
    label: '待调度任务',
    display: formatNumber(adminStore.dashboard?.pending_tasks ?? 0),
    icon: 'task',
    tone: 'warning',
  },
  {
    key: 'today_fee_points',
    label: '今日平台抽成',
    display: formatNumber(adminStore.dashboard?.today_fee_points ?? 0),
    icon: 'earnings',
    tone: 'primary',
  },
  {
    key: 'fee_rate',
    label: '抽成比例',
    display: `${((adminStore.dashboard?.fee_rate ?? 0) / 100).toFixed(2)}%`,
    icon: 'bar-chart',
    tone: 'accent',
  },
])

function formatNumber(value: number) {
  return value.toLocaleString()
}

const entries = [
  {
    path: '/admin/nodes',
    label: '节点管理',
    desc: '查看全部节点状态，强制下线异常节点',
    icon: 'gpu',
  },
  {
    path: '/admin/tasks',
    label: '任务管理',
    desc: '查看全部任务，取消卡死的调度',
    icon: 'task',
  },
  {
    path: '/admin/users',
    label: '用户管理',
    desc: '检索平台用户，封禁违规账号',
    icon: 'user',
  },
  {
    path: '/admin/audit',
    label: '审计日志',
    desc: '哈希链校验，确认记录未被篡改',
    icon: 'file-text',
  },
  {
    path: '/admin/config',
    label: '平台配置',
    desc: '抽成比例、结算单位与超时阈值',
    icon: 'settings',
  },
]

async function loadData() {
  isLoading.value = true
  try {
    await adminStore.fetchDashboard()
  } catch (error: any) {
    danger(error.response?.data?.message || '加载平台概览失败')
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <div class="admin-header">
        <div>
          <h2 class="admin-title">平台管理</h2>
          <p class="admin-subtitle">全局运行状态与运营操作入口</p>
        </div>
        <button type="button" class="refresh-btn" :disabled="isLoading" @click="loadData">
          <Icon name="refresh-cw" class="icon-sm" />
          <span>{{ isLoading ? '刷新中' : '刷新' }}</span>
        </button>
      </div>

      <div class="stat-grid">
        <Card v-for="item in stats" :key="item.key" hoverable>
          <div class="stat-card">
            <div class="stat-icon" :class="`stat-icon-${item.tone}`">
              <Icon :name="item.icon" class="icon-lg" />
            </div>
            <div class="stat-body">
              <span class="stat-label">{{ item.label }}</span>
              <Skeleton v-if="isLoading" type="text" />
              <span v-else class="stat-value">{{ item.display }}</span>
            </div>
          </div>
        </Card>
      </div>

      <Card padded>
        <div class="entry-list">
          <button
            v-for="entry in entries"
            :key="entry.path"
            type="button"
            class="entry-item"
            @click="router.push(entry.path)"
          >
            <span class="entry-icon"><Icon :name="entry.icon" class="icon-md" /></span>
            <span class="entry-body">
              <span class="entry-label">{{ entry.label }}</span>
              <span class="entry-desc">{{ entry.desc }}</span>
            </span>
            <Icon name="chevron-right" class="icon-md entry-arrow" />
          </button>
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-12);
}

.admin-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}

.admin-subtitle {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin-top: var(--space-4);
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-10);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--color-text-secondary);
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-pill);
  transition: all var(--transition-fast);
}

.refresh-btn:hover:not(:disabled) {
  color: var(--color-primary);
  border-color: var(--color-primary-border);
}

.refresh-btn:disabled {
  opacity: 0.6;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-12);
}

.stat-card {
  display: flex;
  align-items: center;
  gap: var(--space-12);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-card);
  flex-shrink: 0;
}

.stat-icon-success {
  color: var(--color-success);
  background: var(--color-success-bg);
}

.stat-icon-warning {
  color: var(--color-warning);
  background: var(--color-warning-bg);
}

.stat-icon-primary {
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

.stat-icon-accent {
  color: var(--color-accent);
  background: var(--color-accent-bg);
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.stat-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.entry-list {
  display: flex;
  flex-direction: column;
}

.entry-item {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  padding: var(--space-12) 0;
  text-align: left;
  background: transparent;
  transition: opacity var(--transition-fast);
}

.entry-item + .entry-item {
  border-top: 1px solid var(--color-line);
}

.entry-item:hover {
  opacity: 0.8;
}

.entry-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  color: var(--color-primary);
  background: var(--color-primary-bg);
  flex-shrink: 0;
}

.entry-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}

.entry-label {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--color-text);
}

.entry-desc {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.entry-arrow {
  color: var(--color-text-muted);
  flex-shrink: 0;
}

@media (min-width: 768px) {
  .stat-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>