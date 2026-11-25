<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { Card, Button, Icon, Badge, StatusDot, Skeleton, EmptyState, Modal, Input } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { formatRelativeTime, maskPhone } from '@/utils/datetime'
import { onRealtime } from '@/composables/useRealtimeEvents'

const router = useRouter()
const adminStore = useAdminStore()
const { success, danger } = useToast()

const statusFilter = ref<'all' | 'online' | 'offline' | 'maintenance'>('all')
const isLoading = ref(false)

const statusTabs = [
  { key: 'all', label: '全部' },
  { key: 'online', label: '在线' },
  { key: 'offline', label: '离线' },
  { key: 'maintenance', label: '维护中' },
] as const

const offlineModalVisible = ref(false)
const offlineTargetId = ref('')
const offlineTargetName = ref('')
const offlineReason = ref('')
const isSubmitting = ref(false)

async function loadNodes() {
  isLoading.value = true
  try {
    await adminStore.fetchNodes(1, 100, statusFilter.value === 'all' ? undefined : statusFilter.value)
  } catch (error: any) {
    danger(error.response?.data?.message || '加载节点列表失败')
  } finally {
    isLoading.value = false
  }
}

function changeFilter(key: typeof statusFilter.value) {
  statusFilter.value = key
  loadNodes()
}

function openOfflineModal(nodeId: string, nodeName: string) {
  offlineTargetId.value = nodeId
  offlineTargetName.value = nodeName
  offlineReason.value = ''
  offlineModalVisible.value = true
}

async function submitOffline() {
  const reason = offlineReason.value.trim()
  if (!reason) {
    danger('请填写下线原因')
    return
  }
  isSubmitting.value = true
  try {
    await adminStore.forceNodeOffline(offlineTargetId.value, reason)
    success('节点已强制下线')
    offlineModalVisible.value = false
  } catch (error: any) {
    danger(error.response?.data?.message || '强制下线失败')
  } finally {
    isSubmitting.value = false
  }
}

function formatNumber(value: number) {
  return (value ?? 0).toLocaleString()
}

function benchmarkLabel(status?: string): string {
  if (status === 'verified') return '算力已对标'
  if (status === 'failed') return '算力异常'
  return '算力待对标'
}

function benchmarkVariant(status?: string): 'success' | 'danger' | 'muted' {
  if (status === 'verified') return 'success'
  if (status === 'failed') return 'danger'
  return 'muted'
}

const unsubscribeRealtime = onRealtime(({ event, data }) => {
  if (event !== 'node_status' || !data?.node_id) return
  const node = adminStore.nodes.find(n => n.id === data.node_id)
  if (node) {
    node.status = data.status
    node.is_online = data.is_online
  }
})

onMounted(() => {
  loadNodes()
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
            <h2 class="admin-title">节点管理</h2>
            <p class="admin-subtitle">共 {{ adminStore.nodesTotal }} 个节点</p>
          </div>
        </div>
        <button type="button" class="refresh-btn" :disabled="isLoading" @click="loadNodes">
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

      <div v-if="isLoading && adminStore.nodes.length === 0" class="list-stack">
        <Skeleton v-for="i in 4" :key="i" type="card" />
      </div>

      <Card v-else-if="adminStore.nodes.length === 0" padded>
        <EmptyState icon="gpu" title="暂无节点" description="该筛选条件下没有节点" />
      </Card>

      <div v-else class="list-stack">
        <Card v-for="node in adminStore.nodes" :key="node.id" hoverable>
          <div class="node-card">
            <div class="node-head">
              <div class="node-title-row">
                <span class="node-name">{{ node.name }}</span>
                <StatusDot :status="node.status" />
              </div>
              <div class="node-badges">
                <Badge :variant="benchmarkVariant(node.benchmark_status)">{{ benchmarkLabel(node.benchmark_status) }}</Badge>
                <Badge variant="muted">信誉 {{ node.reputation_score }}</Badge>
              </div>
            </div>

            <div class="node-spec">
              <span class="spec-item">{{ node.gpu_model }}</span>
              <span class="spec-dot">·</span>
              <span class="spec-item">{{ node.vram_gb }} GB 显存</span>
              <span class="spec-dot">·</span>
              <span class="spec-item">{{ node.peak_tflops }} TFLOPS</span>
            </div>

            <div class="node-meta">
              <span class="meta-item">机主 {{ maskPhone(node.owner_phone) }}</span>
              <span class="meta-item">完成 {{ formatNumber(node.total_tasks_completed) }} 单</span>
              <span class="meta-item">累计 {{ formatNumber(node.total_points_earned) }} 分</span>
            </div>

            <div class="node-foot">
              <span class="heartbeat">
                心跳 {{ node.last_heartbeat_at ? formatRelativeTime(node.last_heartbeat_at) : '无记录' }}
              </span>
              <Button
                v-if="node.status !== 'offline'"
                variant="outline"
                size="sm"
                @click="openOfflineModal(node.id, node.name)"
              >
                强制下线
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>

    <Modal
      :visible="offlineModalVisible"
      title="强制下线节点"
      @close="offlineModalVisible = false"
    >
      <p class="modal-hint">
        节点「{{ offlineTargetName }}」将被立即置为离线并停止派单，请填写下线原因。
      </p>
      <Input
        v-model="offlineReason"
        label="下线原因"
        placeholder="例如：心跳异常 / 硬件故障"
        :maxlength="256"
      />
      <template #footer>
        <Button variant="ghost" @click="offlineModalVisible = false">取消</Button>
        <Button variant="danger" :loading="isSubmitting" @click="submitOffline">确认下线</Button>
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

.node-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
}

.node-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
}

.node-badges {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-shrink: 0;
}

.node-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-width: 0;
}

.node-name {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-spec {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.spec-dot {
  color: var(--color-text-disabled);
}

.node-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-12);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.node-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  padding-top: var(--space-8);
  border-top: 1px solid var(--color-line);
}

.heartbeat {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.modal-hint {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-normal);
}
</style>