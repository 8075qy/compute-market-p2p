<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSupplierStore } from '@/stores/supplier'
import { Card, Button, Icon, Badge, Skeleton, EmptyState } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { formatRelativeTime } from '@/utils/datetime'

const route = useRoute()
const router = useRouter()
const supplierStore = useSupplierStore()
const { danger } = useToast()

const nodeId = route.params.id as string
const nodeName = ref('')
const isLoading = ref(false)

function statusLabel(status?: string): string {
  switch (status) {
    case 'running': return '运行中'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    case 'pending': return '待执行'
    case 'scheduling': return '调度中'
    case 'assigned': return '已分配'
    case 'cancelled': return '已取消'
    default: return status || '-'
  }
}

function statusVariant(status?: string): 'success' | 'danger' | 'warning' | 'muted' {
  switch (status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'running': return 'warning'
    default: return 'muted'
  }
}

function formatDuration(seconds?: number | null): string {
  if (!seconds) return '0 分钟'
  const totalMin = Math.floor(seconds / 60)
  const h = Math.floor(totalMin / 60)
  const min = totalMin % 60
  if (h > 0 && min > 0) return `${h} 小时 ${min} 分钟`
  if (h > 0) return `${h} 小时`
  return `${min} 分钟`
}

function formatNumber(value?: number | null): string {
  return (value ?? 0).toLocaleString()
}

async function loadData() {
  isLoading.value = true
  try {
    const node = await supplierStore.getNode(nodeId)
    nodeName.value = node.name
    await supplierStore.fetchNodeExecutions(nodeId, 1, 50)
  } catch (error: any) {
    danger(error.response?.data?.message || '加载执行记录失败')
  } finally {
    isLoading.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <div class="detail-header">
        <div class="detail-header-left">
          <button type="button" class="back-btn" aria-label="返回" @click="router.back()">
            <Icon name="chevron-left" class="icon-md" />
          </button>
          <div>
            <h2 class="detail-title">执行记录</h2>
            <p class="detail-subtitle">{{ nodeName || '加载中...' }}</p>
          </div>
        </div>
      </div>

      <Skeleton v-if="isLoading" type="card" v-for="i in 3" :key="i" style="margin-bottom: var(--space-16);" />

      <Card v-else-if="supplierStore.executions.length === 0" padded>
        <EmptyState icon="activity" title="暂无执行记录" description="该节点尚未执行任何算力任务" />
      </Card>

      <div v-else class="list-stack">
        <Card v-for="exec in supplierStore.executions" :key="exec.id">
          <div class="exec-card">
            <div class="exec-head">
              <div class="exec-title-row">
                <span class="exec-title">#{{ exec.task_no || exec.task_id.slice(0, 8) }}</span>
                <Badge :variant="statusVariant(exec.status)">{{ statusLabel(exec.status) }}</Badge>
              </div>
              <span class="exec-time">{{ formatRelativeTime(exec.started_at || exec.created_at) }}</span>
            </div>

            <div class="exec-metrics">
              <div class="exec-metric">
                <span class="metric-label">算力时长</span>
                <span class="metric-value">{{ formatDuration(exec.compute_duration_seconds) }}</span>
              </div>
              <div class="exec-metric">
                <span class="metric-label">结算积分</span>
                <span class="metric-value">{{ formatNumber(exec.compute_points) }} 分</span>
              </div>
              <div class="exec-metric">
                <span class="metric-label">我的收益</span>
                <span class="metric-value metric-highlight">{{ formatNumber(exec.supplier_earnings_points) }} 分</span>
              </div>
            </div>

            <p v-if="exec.error_message" class="exec-error">{{ exec.error_message }}</p>
          </div>
        </Card>
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-12);
  margin-bottom: var(--space-16);
}

.detail-header-left {
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

.detail-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}

.detail-subtitle {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin-top: var(--space-4);
}

.list-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
}

.exec-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
}

.exec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
}

.exec-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-width: 0;
}

.exec-title {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.exec-time {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.exec-metrics {
  display: flex;
  gap: var(--space-16);
  flex-wrap: wrap;
}

.exec-metric {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 80px;
}

.metric-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.metric-value {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
}

.metric-highlight {
  color: var(--color-success);
}

.exec-error {
  font-size: var(--text-xs);
  color: var(--color-danger);
  line-height: var(--leading-normal);
  word-break: break-all;
}
</style>