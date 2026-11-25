<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSupplierStore } from '@/stores/supplier'
import { Card, Button, Icon, Skeleton, EmptyState, ListRow } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { onRealtime } from '@/composables/useRealtimeEvents'

const router = useRouter()
const authStore = useAuthStore()
const supplierStore = useSupplierStore()
const { success, danger } = useToast()

const statusFilter = ref<'all' | 'online' | 'offline' | 'maintenance'>('all')

const filteredNodes = computed(() => {
  if (statusFilter.value === 'all') return supplierStore.nodes
  return supplierStore.nodes.filter(n => n.status === statusFilter.value)
})

function regionText(node: { region_province?: string | null; region_city?: string | null }): string {
  if (node.region_province && node.region_city) {
    return `${node.region_province}${node.region_city}`
  }
  return ''
}

function benchmarkLabel(node: { benchmark_status?: 'pending' | 'verified' | 'failed' }): string {
  switch (node.benchmark_status) {
    case 'verified':
      return '算力已对标'
    case 'failed':
      return '算力对标异常'
    default:
      return '算力待对标'
  }
}

function gpuSummary(node: { gpu_count?: number; gpu_model: string; vram_gb: number }): string {
  const count = node.gpu_count || 1
  if (count > 1) {
    return `${count}×${node.gpu_model} · ${node.vram_gb * count}GB 总显存`
  }
  return `${node.gpu_model} · ${node.vram_gb}GB VRAM`
}

const tabs = [
  { key: 'all', label: '全部' },
  { key: 'online', label: '在线' },
  { key: 'offline', label: '离线' },
  { key: 'maintenance', label: '维护' },
]

async function loadNodes() {
  await supplierStore.fetchNodes(1, 50)
}

async function handleAddNode() {
  router.push('/supplier/nodes/add')
}

async function handleNodeAction(node: any, action: string) {
  try {
    switch (action) {
      case 'online':
        await supplierStore.setNodeOnline(node.id)
        success('节点已上线')
        break
      case 'offline':
        await supplierStore.setNodeOffline(node.id)
        success('节点已下线')
        break
      case 'edit':
        router.push(`/supplier/nodes/${node.id}/edit`)
        break
      case 'earnings':
        router.push(`/supplier/earnings?node=${node.id}`)
        break
      case 'executions':
        router.push(`/supplier/nodes/${node.id}/executions`)
        break
      case 'delete':
        const confirmed = confirm('确定要删除该节点吗？此操作不可恢复。')
        if (confirmed) {
          await supplierStore.deleteNode(node.id)
          success('节点已删除')
        }
        break
    }
  } catch (error: any) {
    danger(error.response?.data?.message || '操作失败')
  }
}

const unsubscribeRealtime = onRealtime(({ event, data }) => {
  if (event !== 'node_status' || !data?.node_id) return
  const node = supplierStore.nodes.find(n => n.id === data.node_id)
  if (node) {
    node.status = data.status
    node.is_online = data.is_online
  } else {
    loadNodes()
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
      <!-- 筛选标签 -->
      <div class="top-tabbar" style="margin: calc(var(--space-16) * -1) calc(var(--space-16) * -1) var(--space-16); padding-top: var(--space-8);">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="top-tabbar-item"
          :class="{ active: statusFilter === tab.key }"
          @click="statusFilter = tab.key as any"
        >
          {{ tab.label }}
          <span v-if="tab.key !== 'all' && supplierStore.nodes.filter(n => n.status === tab.key).length > 0"
                class="badge badge-primary" style="margin-left: var(--space-8); font-size: 10px; padding: 0 6px; height: 16px;">
            {{ supplierStore.nodes.filter(n => n.status === tab.key).length }}
          </span>
        </button>
      </div>

      <!-- 节点列表 -->
      <Card v-if="supplierStore.isLoading" style="padding: 0;">
        <Skeleton type="card" v-for="i in 5" :key="i" style="margin: var(--space-16);" />
      </Card>

      <Card v-else-if="filteredNodes.length === 0" style="padding: var(--space-32);">
        <EmptyState
          icon="gpu"
          title="暂无节点"
          description="接入闲置GPU/NPU开始赚取积分"
          actionLabel="添加节点"
          :action="handleAddNode"
        />
      </Card>

      <div v-else style="display: flex; flex-direction: column; gap: var(--space-8);">
        <ListRow
          v-for="node in filteredNodes"
          :key="node.id"
          :title="node.name"
          :subtitle="`${gpuSummary(node)} · ${node.peak_tflops} TFLOPS${regionText(node) ? ' · ' + regionText(node) : ''} · ${benchmarkLabel(node)}`"
          :meta="`${node.total_tasks_completed} 单完成`"
          :metaLabel="`信誉 ${node.reputation_score} · 收益 ${node.total_points_earned} 分`"
          :status="node.status"
          :badge="node.benchmark_status === 'failed' ? '算力异常' : (node.is_online ? '在线' : '离线')"
          :badgeVariant="node.benchmark_status === 'failed' ? 'danger' : (node.is_online ? 'success' : 'muted')"
          rightIcon="chevron-right"
          :onClick="() => router.push(`/supplier/nodes/${node.id}`)"
        />
      </div>

      <!-- 添加节点按钮 -->
      <div style="margin-top: var(--space-24); padding-bottom: var(--space-32);">
        <Button variant="outline" block @click="handleAddNode">
          <Icon name="plus" class="icon-md" /> 添加节点
        </Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 额外样式 */
</style>