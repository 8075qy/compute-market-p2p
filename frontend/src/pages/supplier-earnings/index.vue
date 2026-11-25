<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useSupplierStore } from '@/stores/supplier'
import { Card, Icon, Badge, Progress, Skeleton, EmptyState } from '@/components/ui'
import { useToast } from '@/composables/useToast'

const authStore = useAuthStore()
const supplierStore = useSupplierStore()
const { success, danger } = useToast()

const period = ref<'day' | 'week' | 'month' | 'year'>('month')
const selectedNodeId = ref<string | null>(null)
const showNodePicker = ref(false)

const periods = [
  { key: 'day', label: '今日' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
  { key: 'year', label: '今年' },
]

async function loadEarnings() {
  if (supplierStore.nodes.length === 0) {
    await supplierStore.fetchNodes()
  }
  if (supplierStore.nodes.length > 0) {
    const nodeId = selectedNodeId.value || supplierStore.nodes[0].id
    await supplierStore.fetchNodeEarnings(nodeId, period.value)
  }
}

function formatPoints(points: number) {
  return points.toLocaleString()
}

onMounted(() => {
  loadEarnings()
})

// 监听周期和节点变化
import { watch } from 'vue'
watch([period, selectedNodeId], loadEarnings)
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <!-- 收益概览卡片 -->
      <Card class="earnings-overview" style="margin-bottom: var(--space-16);">
        <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text);">收益概览</h2>
          <div style="display: flex; gap: var(--space-4);">
            <button
              v-for="p in periods"
              :key="p.key"
              class="btn btn-ghost btn-sm"
              :class="{ 'btn-primary': period === p.key }"
              @click="period = p.key as any"
            >
              {{ p.label }}
            </button>
          </div>
        </div>

        <div v-if="supplierStore.isLoading" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-16);">
          <Skeleton type="rect" v-for="i in 4" :key="i" style="height: 80px; border-radius: var(--radius-card);" />
        </div>

        <div v-else-if="supplierStore.earnings" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-16);">
          <div class="earnings-stat">
            <div class="stat-label">今日收益</div>
            <div class="stat-value">{{ formatPoints(supplierStore.earnings.today) }} 分</div>
          </div>
          <div class="earnings-stat">
            <div class="stat-label">本周收益</div>
            <div class="stat-value">{{ formatPoints(supplierStore.earnings.this_week) }} 分</div>
          </div>
          <div class="earnings-stat">
            <div class="stat-label">本月收益</div>
            <div class="stat-value">{{ formatPoints(supplierStore.earnings.this_month) }} 分</div>
          </div>
          <div class="earnings-stat">
            <div class="stat-label">累计收益</div>
            <div class="stat-value">{{ formatPoints(supplierStore.earnings.total) }} 分</div>
          </div>
        </div>
      </Card>

      <!-- 节点收益分布 -->
      <Card style="margin-bottom: var(--space-16);">
        <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">节点收益分布</h2>

        <div v-if="supplierStore.isLoading" style="display: flex; flex-direction: column; gap: var(--space-12);">
          <Skeleton type="card" v-for="i in 3" :key="i" />
        </div>

        <div v-else-if="!supplierStore.earnings || !supplierStore.earnings.by_node || Object.keys(supplierStore.earnings.by_node).length === 0" style="text-align: center; padding: var(--space-32) 0;">
          <EmptyState
            icon="bar-chart"
            title="暂无收益数据"
            description="节点上线并完成任务后将显示收益分布"
          />
        </div>

        <div v-else style="display: flex; flex-direction: column; gap: var(--space-12);">
          <div
            v-for="(amount, nodeId) in supplierStore.earnings.by_node"
            :key="nodeId"
            class="node-earnings-item"
          >
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <div style="display: flex; align-items: center; gap: var(--space-12); flex: 1; min-width: 0;">
                <div style="width: 40px; height: 40px; border-radius: var(--radius-card); background: var(--color-primary-hover); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                  <Icon name="gpu" class="icon-md" style="color: var(--color-primary);" />
                </div>
                <div style="min-width: 0;">
                  <div style="font-weight: 600; color: var(--color-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    {{ supplierStore.nodes.find(n => n.id === nodeId)?.name || nodeId }}
                  </div>
                  <div style="font-size: var(--text-xs); color: var(--color-text-muted);">
                    ID: {{ nodeId.slice(0, 8) }}...
                  </div>
                </div>
              </div>
              <div style="text-align: right;">
                <div style="font-size: var(--text-lg); font-weight: 700; color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ formatPoints(amount) }} 分</div>
                <div v-if="supplierStore.earnings.total > 0" style="font-size: var(--text-xs); color: var(--color-text-muted); margin-top: 2px;">
                  占比 {{ ((amount / supplierStore.earnings.total) * 100).toFixed(1) }}%
                </div>
              </div>
            </div>
            <Progress :value="supplierStore.earnings.total > 0 ? (amount / supplierStore.earnings.total) * 100 : 0" size="sm" style="margin-top: var(--space-8);" />
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.earnings-overview {
  background: linear-gradient(135deg, var(--color-surface) 0%, var(--color-bg) 100%);
}

.earnings-stat {
  text-align: center;
  padding: var(--space-16) var(--space-8);
  background: var(--color-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card);
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--space-4);
}

.stat-value {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-text);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.node-earnings-item {
  padding: var(--space-12);
  background: var(--color-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card);
}
</style>