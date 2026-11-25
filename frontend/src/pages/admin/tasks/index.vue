<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { Card, Button, Icon, Badge, Skeleton, EmptyState, Modal } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { formatRelativeTime, maskPhone } from '@/utils/datetime'
import { onRealtime } from '@/composables/useRealtimeEvents'
import type { TaskStatus } from '@/types'

const router = useRouter()
const adminStore = useAdminStore()
const { success, danger } = useToast()

const statusFilter = ref<'all' | TaskStatus>('all')
const isLoading = ref(false)

const statusTabs: Array<{ key: 'all' | TaskStatus; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待调度' },
  { key: 'scheduling', label: '调度中' },
  { key: 'running', label: '运行中' },
  { key: 'completed', label: '已完成' },
  { key: 'failed', label: '失败' },
  { key: 'cancelled', label: '已取消' },
]

const cancelModalVisible = ref(false)
const cancelTargetId = ref('')
const cancelTargetNo = ref('')
const isSubmitting = ref(false)

const statusMeta: Record<TaskStatus, { label: string; variant: 'primary' | 'success' | 'warning' | 'danger' | 'muted' }> = {
  pending: { label: '待调度', variant: 'warning' },
  scheduling: { label: '调度中', variant: 'warning' },
  assigned: { label: '已分配', variant: 'primary' },
  running: { label: '运行中', variant: 'success' },
  completed: { label: '已完成', variant: 'primary' },
  failed: { label: '失败', variant: 'danger' },
  cancelled: { label: '已取消', variant: 'muted' },
}

const typeLabel: Record<string, string> = {
  inference: '推理',
  training: '训练',
}

async function loadTasks() {
  isLoading.value = true
  try {
    await adminStore.fetchTasks(1, 100, statusFilter.value === 'all' ? undefined : statusFilter.value)
  } catch (error: any) {
    danger(error.response?.data?.message || '加载任务列表失败')
  } finally {
    isLoading.value = false
  }
}

function changeFilter(key: 'all' | TaskStatus) {
  statusFilter.value = key
  loadTasks()
}

function openCancelModal(taskId: string, taskNo: string) {
  cancelTargetId.value = taskId
  cancelTargetNo.value = taskNo
  cancelModalVisible.value = true
}

async function submitCancel() {
  isSubmitting.value = true
  try {
    await adminStore.cancelTaskScheduling(cancelTargetId.value)
    success('已取消调度')
    cancelModalVisible.value = false
  } catch (error: any) {
    danger(error.response?.data?.message || '取消调度失败')
  } finally {
    isSubmitting.value = false
  }
}

const unsubscribeRealtime = onRealtime(({ event, data }) => {
  if (event !== 'task_status' || !data?.task_id) return
  const task = adminStore.tasks.find(t => t.id === data.task_id)
  if (task) {
    task.status = data.status
    task.assigned_node_id = data.assigned_node_id
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
      <div class="admin-header">
        <div class="admin-header-left">
          <button type="button" class="back-btn" aria-label="返回" @click="router.push('/admin')">
            <Icon name="chevron-left" class="icon-md" />
          </button>
          <div>
            <h2 class="admin-title">任务管理</h2>
            <p class="admin-subtitle">共 {{ adminStore.tasksTotal }} 个任务</p>
          </div>
        </div>
        <button type="button" class="refresh-btn" :disabled="isLoading" @click="loadTasks">
          <Icon name="refresh-cw" class="icon-sm" />
          <span>{{ isLoading ? '刷新中' : '刷新' }}</span>
        </button>
      </div>

      <div class="filter-bar">
        <button
          v-for="tab in statusTabs"
          :key="tab.key"
          type="button"
          class="filter-chip"
          :class="{ active: statusFilter === tab.key }"
          @click="changeFilter(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>

      <div v-if="isLoading && adminStore.tasks.length === 0" class="list-stack">
        <Skeleton v-for="i in 4" :key="i" type="card" />
      </div>

      <Card v-else-if="adminStore.tasks.length === 0" padded>
        <EmptyState icon="task" title="暂无任务" description="该筛选条件下没有任务" />
      </Card>

      <div v-else class="list-stack">
        <Card v-for="task in adminStore.tasks" :key="task.id" hoverable>
          <div class="task-card">
            <div class="task-head">
              <span class="task-no">{{ task.task_no }}</span>
              <Badge :variant="statusMeta[task.status].variant">
                {{ statusMeta[task.status].label }}
              </Badge>
            </div>

            <div class="task-meta">
              <span class="meta-item">{{ typeLabel[task.type] || task.type }}</span>
              <span class="meta-item">需求方 {{ maskPhone(task.demander_phone) }}</span>
              <span class="meta-item">发布 {{ formatRelativeTime(task.created_at) }}</span>
            </div>

            <div class="task-foot">
              <span class="node-ref">
                {{ task.assigned_node_id ? '已分配节点' : '尚未分配节点' }}
              </span>
              <div class="task-actions">
                <Button variant="ghost" size="sm" @click="router.push(`/task/${task.id}`)">
                  详情
                </Button>
                <Button
                  v-if="['pending', 'scheduling'].includes(task.status)"
                  variant="outline"
                  size="sm"
                  @click="openCancelModal(task.id, task.task_no)"
                >
                  取消调度
                </Button>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>

    <Modal :visible="cancelModalVisible" title="取消任务调度" @close="cancelModalVisible = false">
      <p class="modal-hint">
        任务「{{ cancelTargetNo }}」将停止调度并退回冻结积分，该操作会记入审计日志。
      </p>
      <template #footer>
        <Button variant="ghost" @click="cancelModalVisible = false">取消</Button>
        <Button variant="danger" :loading="isSubmitting" @click="submitCancel">确认取消调度</Button>
      </template>
    </Modal>
  </div>
</template>

<style scoped>
.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-12);
}

.admin-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  color: var(--color-text-secondary);
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  flex-shrink: 0;
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

.filter-bar {
  display: flex;
  gap: var(--space-8);
  overflow-x: auto;
  padding-bottom: var(--space-4);
  -webkit-overflow-scrolling: touch;
}

.filter-chip {
  flex-shrink: 0;
  padding: var(--space-4) var(--space-12);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text-muted);
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-pill);
  transition: all var(--transition-fast);
}

.filter-chip.active {
  color: var(--color-primary);
  background: var(--color-primary-bg);
  border-color: var(--color-primary-border);
}

.list-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
}

.task-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
}

.task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
}

.task-no {
  font-family: var(--font-mono);
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-12);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.task-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  padding-top: var(--space-8);
  border-top: 1px solid var(--color-line);
}

.node-ref {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.task-actions {
  display: flex;
  gap: var(--space-8);
}

.modal-hint {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-normal);
}
</style>