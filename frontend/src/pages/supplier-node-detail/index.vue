<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSupplierStore } from '@/stores/supplier'
import { Card, Button, Icon, Badge, Skeleton, EmptyState } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { formatRelativeTime, formatDateTime } from '@/utils/datetime'
import type { NodeDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const supplierStore = useSupplierStore()
const { success, danger } = useToast()

const nodeId = route.params.id as string
const node = ref<NodeDetail | null>(null)
const isLoading = ref(false)
const isSubmitting = ref(false)

function statusLabel(status?: string): string {
  switch (status) {
    case 'online': return '在线'
    case 'offline': return '离线'
    case 'maintenance': return '维护中'
    default: return status || '-'
  }
}

function statusVariant(status?: string): 'success' | 'warning' | 'muted' {
  switch (status) {
    case 'online': return 'success'
    case 'maintenance': return 'warning'
    default: return 'muted'
  }
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

function formatNumber(value?: number | null): string {
  return (value ?? 0).toLocaleString()
}

function regionText(node: NodeDetail): string {
  const parts = [node.region_province, node.region_city, node.region_district].filter(Boolean)
  return parts.length > 0 ? parts.join(' ') : '未设置'
}

async function loadNode() {
  isLoading.value = true
  try {
    node.value = await supplierStore.getNode(nodeId)
  } catch (error: any) {
    danger(error.response?.data?.message || '加载节点失败')
  } finally {
    isLoading.value = false
  }
}

async function handleToggleOnline() {
  if (!node.value || isSubmitting.value) return
  isSubmitting.value = true
  try {
    if (node.value.status === 'online') {
      await supplierStore.setNodeOffline(nodeId)
      success('节点已下线')
    } else {
      await supplierStore.setNodeOnline(nodeId)
      success('节点已上线')
    }
    await loadNode()
  } catch (error: any) {
    danger(error.response?.data?.message || '操作失败')
  } finally {
    isSubmitting.value = false
  }
}

async function handleDelete() {
  if (!node.value || isSubmitting.value) return
  const confirmed = confirm('确定要删除该节点吗？删除后该节点将无法继续接入平台，此操作不可撤销。')
  if (!confirmed) return
  isSubmitting.value = true
  try {
    await supplierStore.deleteNode(nodeId)
    success('节点已删除')
    router.replace('/supplier/nodes')
  } catch (error: any) {
    danger(error.response?.data?.message || '删除失败')
  } finally {
    isSubmitting.value = false
  }
}

onMounted(loadNode)
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
            <h2 class="detail-title">节点详情</h2>
            <p class="detail-subtitle">{{ node?.name || '加载中...' }}</p>
          </div>
        </div>
      </div>

      <Skeleton v-if="isLoading && !node" type="card" v-for="i in 3" :key="i" style="margin-bottom: var(--space-16);" />

      <template v-else-if="node">
        <!-- 状态概览 -->
        <Card style="margin-bottom: var(--space-16);">
          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-16); flex-wrap: wrap;">
            <div style="flex: 1; min-width: 200px;">
              <div style="display: flex; align-items: center; gap: var(--space-8); flex-wrap: wrap; margin-bottom: var(--space-8);">
                <h2 style="font-size: var(--text-xl); font-weight: 700; color: var(--color-text);">{{ node.name }}</h2>
                <Badge :variant="statusVariant(node.status)">{{ statusLabel(node.status) }}</Badge>
                <Badge :variant="benchmarkVariant(node.benchmark_status)">{{ benchmarkLabel(node.benchmark_status) }}</Badge>
              </div>
              <p style="font-size: var(--text-sm); color: var(--color-text-muted);">
                信誉分 {{ formatNumber(node.reputation_score) }} · 注册于 {{ formatDateTime(node.created_at) }}
              </p>
            </div>
            <div style="display: flex; gap: var(--space-8); flex-wrap: wrap;">
              <Button
                :variant="node.status === 'online' ? 'outline' : 'primary'"
                :loading="isSubmitting"
                @click="handleToggleOnline"
              >
                <Icon :name="node.status === 'online' ? 'x-circle' : 'check-circle'" class="icon-md" />
                {{ node.status === 'online' ? '下线' : '上线' }}
              </Button>
              <Button variant="danger" :loading="isSubmitting" @click="handleDelete">
                <Icon name="trash" class="icon-md" /> 删除
              </Button>
            </div>
          </div>
        </Card>

        <!-- 算力规格与对标 -->
        <Card style="margin-bottom: var(--space-16);">
          <h3 style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">算力规格与对标</h3>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">GPU 型号</span>
              <span class="info-value">{{ node.gpu_count > 1 ? `${node.gpu_count}×${node.gpu_model}` : node.gpu_model }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">显存</span>
              <span class="info-value">{{ node.gpu_count > 1 ? `${formatNumber(node.vram_gb * node.gpu_count)} GB（${node.gpu_count}×${formatNumber(node.vram_gb)}GB）` : `${formatNumber(node.vram_gb)} GB` }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">登记算力</span>
              <span class="info-value">{{ formatNumber(node.peak_tflops) }} TFLOPS</span>
            </div>
            <div class="info-item">
              <span class="info-label">对标算力</span>
              <span class="info-value">{{ node.benchmark_tflops != null ? `${formatNumber(node.benchmark_tflops)} TFLOPS` : '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">对标状态</span>
              <span class="info-value">
                <Badge :variant="benchmarkVariant(node.benchmark_status)">{{ benchmarkLabel(node.benchmark_status) }}</Badge>
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">对标时间</span>
              <span class="info-value">{{ node.benchmarked_at ? formatRelativeTime(node.benchmarked_at) : '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">所在地区</span>
              <span class="info-value">{{ regionText(node) }}</span>
            </div>
            <div class="info-item info-item-wide">
              <span class="info-label">GPU 唯一标识</span>
              <span class="info-value uuid">{{ node.gpu_uuid || '未上报' }}</span>
            </div>
          </div>
        </Card>

        <!-- 实时运行状态 -->
        <Card style="margin-bottom: var(--space-16);">
          <h3 style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">实时运行状态</h3>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">GPU 利用率</span>
              <span class="info-value">{{ node.gpu_utilization != null ? `${formatNumber(node.gpu_utilization)}%` : '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">显存占用</span>
              <span class="info-value">{{ node.vram_used_gb != null ? `${formatNumber(node.vram_used_gb)} GB` : '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">GPU 温度</span>
              <span class="info-value">{{ node.temp_c != null ? `${formatNumber(node.temp_c)}°C` : '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">最近心跳</span>
              <span class="info-value">{{ node.last_heartbeat_at ? formatRelativeTime(node.last_heartbeat_at) : '暂无' }}</span>
            </div>
          </div>
        </Card>

        <!-- 贡献统计 -->
        <Card>
          <h3 style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">贡献统计</h3>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">今日任务</span>
              <span class="info-value">{{ formatNumber(node.today_tasks) }} 个</span>
            </div>
            <div class="info-item">
              <span class="info-label">今日积分</span>
              <span class="info-value">{{ formatNumber(node.today_points) }} 分</span>
            </div>
            <div class="info-item">
              <span class="info-label">累计完成任务</span>
              <span class="info-value">{{ formatNumber(node.total_tasks_completed) }} 个</span>
            </div>
            <div class="info-item">
              <span class="info-label">累计收益</span>
              <span class="info-value">{{ formatNumber(node.total_points_earned) }} 分</span>
            </div>
          </div>
        </Card>
      </template>

      <Card v-else padded>
        <EmptyState icon="gpu" title="节点不存在" description="该节点可能已被删除，或您无权查看" />
      </Card>
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

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-16);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.info-item-wide {
  grid-column: 1 / -1;
}

.info-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.info-value {
  font-size: var(--text-sm);
  color: var(--color-text);
  font-weight: var(--font-medium);
  word-break: break-all;
}

.uuid {
  font-family: var(--font-mono, monospace);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

@media (max-width: 480px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>