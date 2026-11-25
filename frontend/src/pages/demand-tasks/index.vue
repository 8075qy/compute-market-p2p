<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDemanderStore } from '@/stores/demander'
import { Card, Button, Icon, Badge, StatusDot, Skeleton, EmptyState, ListRow, ActionSheet } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { onRealtime } from '@/composables/useRealtimeEvents'

const router = useRouter()
const demanderStore = useDemanderStore()
const { success, danger, warning } = useToast()

const statusFilter = ref<'all' | 'pending' | 'scheduling' | 'running' | 'completed' | 'failed' | 'cancelled'>('all')
const typeFilter = ref<'all' | 'inference' | 'training'>('all')

const statusTabs = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待调度' },
  { key: 'scheduling', label: '调度中' },
  { key: 'running', label: '运行中' },
  { key: 'completed', label: '已完成' },
  { key: 'failed', label: '失败' },
  { key: 'cancelled', label: '已取消' },
]

const typeTabs = [
  { key: 'all', label: '全部' },
  { key: 'inference', label: '推理' },
  { key: 'training', label: '训练' },
]

const filteredTasks = computed(() => {
  let tasks = demanderStore.tasks
  if (statusFilter.value !== 'all') {
    tasks = statusFilter.value === 'scheduling'
      ? tasks.filter(t => t.status === 'scheduling' || t.status === 'assigned')
      : tasks.filter(t => t.status === statusFilter.value)
  }
  if (typeFilter.value !== 'all') {
    tasks = tasks.filter(t => t.type === typeFilter.value)
  }
  return tasks
})

async function loadTasks() {
  await demanderStore.fetchTasks(1, 50)
}

async function handleRetry(task: any) {
  try {
    await demanderStore.retryTask(task.id)
    success('重试已提交')
  } catch (error: any) {
    danger(error.response?.data?.message || '重试失败')
  }
}

async function handleCancel(task: any) {
  const confirmed = confirm('确定要取消该任务吗？已执行部分将按实际用量结算。')
  if (confirmed) {
    try {
      await demanderStore.cancelTask(task.id)
      success('任务已取消')
    } catch (error: any) {
      danger(error.response?.data?.message || '取消失败')
    }
  }
}

async function handleViewLogs(task: any) {
  router.push(`/task/${task.id}?tab=logs`)
}

async function handleViewResult(task: any) {
  router.push(`/task/${task.id}?tab=result`)
}

function getStatusBadgeVariant(status: string) {
  switch (status) {
    case 'running': return 'success'
    case 'completed': return 'primary'
    case 'failed': return 'danger'
    case 'cancelled': return 'muted'
    default: return 'warning'
  }
}

function getStatusLabel(status: string) {
  switch (status) {
    case 'pending': return '待调度'
    case 'scheduling': return '调度中'
    case 'assigned': return '已分配'
    case 'running': return '运行中'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    default: return status
  }
}

function formatDuration(minutes: number) {
  if (!minutes) return '0 分钟'
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h > 0 && m > 0) return `${h} 小时 ${m} 分钟`
  if (h > 0) return `${h} 小时`
  return `${m} 分钟`
}

const unsubscribeRealtime = onRealtime(({ event, data }) => {
  if (event !== 'task_status' || !data?.task_id) return
  const task = demanderStore.tasks.find(t => t.id === data.task_id)
  if (task) {
    task.status = data.status
  } else {
    loadTasks()
  }
})

onMounted(() => {
  loadTasks()
})

onBeforeUnmount(() => {
  unsubscribeRealtime()
})
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <!-- 筛选标签 -->
      <div class="top-tabbar" style="margin: calc(var(--space-16) * -1) calc(var(--space-16) * -1) var(--space-16); padding-top: var(--space-8);">
        <div style="display: flex; gap: var(--space-4); overflow-x: auto; padding-bottom: var(--space-4); -webkit-overflow-scrolling: touch;">
          <button
            v-for="tab in statusTabs"
            :key="tab.key"
            class="top-tabbar-item"
            :class="{ active: statusFilter === tab.key }"
            @click="statusFilter = tab.key as any"
          >
            {{ tab.label }}
            <span v-if="statusFilter !== 'all' && demanderStore.tasks.filter(t => t.status === tab.key).length > 0"
                  class="badge badge-primary" style="margin-left: var(--space-8); font-size: 10px; padding: 0 6px; height: 16px;">
              {{ demanderStore.tasks.filter(t => t.status === tab.key).length }}
            </span>
          </button>
        </div>
        <div style="display: flex; gap: var(--space-4); margin-top: var(--space-8); overflow-x: auto; padding-bottom: var(--space-4); -webkit-overflow-scrolling: touch;">
          <button
            v-for="tab in typeTabs"
            :key="tab.key"
            class="top-tabbar-item"
            :class="{ active: typeFilter === tab.key }"
            @click="typeFilter = tab.key as any"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>

      <!-- 任务列表 -->
      <Card v-if="demanderStore.isLoading" style="padding: 0;">
        <Skeleton type="card" v-for="i in 5" :key="i" style="margin: var(--space-16);" />
      </Card>

      <Card v-else-if="filteredTasks.length === 0" style="padding: var(--space-32);">
        <EmptyState
          v-if="statusFilter === 'all'"
          icon="task"
          title="暂无任务"
          description="发布推理或训练任务开始使用算力"
          actionLabel="发布任务"
          :action="() => router.push('/demand/publish')"
        />
        <EmptyState
          v-else
          :icon="typeFilter === 'training' ? 'trending-up' : 'activity'"
          :title="`${statusTabs.find(t => t.key === statusFilter)?.label || '该状态'}下暂无任务`"
          description="调整筛选条件或发布新任务"
        />
      </Card>

      <div v-else style="display: flex; flex-direction: column; gap: var(--space-8);">
        <ListRow
          v-for="task in filteredTasks"
          :key="task.id"
          :title="task.title"
          :subtitle="`${task.type === 'training' ? '训练' : '推理'} · 预算 ${task.budget_points}分 · 最大 ${formatDuration(task.timeout_minutes)}`"
          :meta="getStatusLabel(task.status)"
          :metaLabel="`创建于 ${new Date(task.created_at).toLocaleDateString()}${task.completed_at ? ' · 完成于 ' + new Date(task.completed_at).toLocaleDateString() : ''}`"
          :status="task.status === 'running' ? 'online' : task.status === 'completed' ? 'online' : 'offline'"
          :badge="task.retry_count > 0 ? `重试 ${task.retry_count}/${task.max_retries}` : ''"
          :badgeVariant="task.retry_count > 0 ? 'warning' : 'muted'"
          rightIcon="chevron-right"
          @click="router.push(`/task/${task.id}`)"
        >
          <template #default>
            <div style="display: flex; flex-direction: column; gap: var(--space-4);">
              <div style="display: flex; align-items: center; gap: var(--space-8); flex-wrap: wrap;">
                <h4 style="font-size: var(--text-base); font-weight: 600; color: var(--color-text);">{{ task.title }}</h4>
                <Badge :variant="task.type === 'training' ? 'warning' : 'primary'">
                  {{ task.type === 'training' ? '训练' : '推理' }}
                </Badge>
                <Badge :variant="getStatusBadgeVariant(task.status)">
                  {{ getStatusLabel(task.status) }}
                </Badge>
              </div>
              <p style="font-size: var(--text-sm); color: var(--color-text-muted);">
                {{ task.type === 'training' ? '训练' : '推理' }} · 预算 {{ task.budget_points }}分 · 最大 {{ formatDuration(task.timeout_minutes) }}
              </p>
              <div style="display: flex; flex-wrap: wrap; gap: var(--space-8); font-size: var(--text-xs); color: var(--color-text-muted);">
                <span>创建: {{ new Date(task.created_at).toLocaleString() }}</span>
                <span v-if="task.completed_at">完成: {{ new Date(task.completed_at).toLocaleString() }}</span>
                <span v-if="task.assigned_node_id">节点: {{ task.assigned_node_id.slice(0, 8) }}...</span>
                <span v-if="task.retry_count > 0" style="color: var(--color-warning);">重试 {{ task.retry_count }}/{{ task.max_retries }}</span>
              </div>
            </div>
          </template>
        </ListRow>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 额外样式 */
</style>