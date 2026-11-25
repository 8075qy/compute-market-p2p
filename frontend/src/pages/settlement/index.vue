<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { usePlatformStore } from '@/stores/platform'
import { Card, Button, Icon, Skeleton, EmptyState, ListRow, Input } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { formatDateTime } from '@/utils/datetime'
import type { Settlement, SettlementStatus } from '@/types'

const platformStore = usePlatformStore()
const { success, danger } = useToast()

const statusFilter = ref<'all' | SettlementStatus>('all')
const directionFilter = ref<'all' | 'income' | 'expense'>('all')
const dateRange = ref<{ start: string; end: string }>({ start: '', end: '' })

const statusTabs: { key: 'all' | SettlementStatus; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'settled', label: '已完成' },
  { key: 'pending', label: '处理中' },
  { key: 'refunded', label: '已退款' },
  { key: 'reversed', label: '已冲正' },
]

const directionTabs: { key: 'all' | 'income' | 'expense'; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'income', label: '收入' },
  { key: 'expense', label: '支出' },
]

/** 结算方向由记录角色决定：供给方为收入，需求方为支出 */
function getDirection(s: Settlement): 'income' | 'expense' {
  return s.role === 'supplier' ? 'income' : 'expense'
}

const filteredSettlements = computed(() => {
  let items = platformStore.settlements
  if (statusFilter.value !== 'all') {
    items = items.filter(s => s.status === statusFilter.value)
  }
  if (directionFilter.value !== 'all') {
    items = items.filter(s => getDirection(s) === directionFilter.value)
  }
  if (dateRange.value.start) {
    const start = new Date(`${dateRange.value.start}T00:00:00`)
    items = items.filter(s => new Date(s.created_at) >= start)
  }
  if (dateRange.value.end) {
    const end = new Date(`${dateRange.value.end}T23:59:59.999`)
    items = items.filter(s => new Date(s.created_at) <= end)
  }
  return items
})

const totals = computed(() => {
  let income = 0
  let expense = 0
  let fee = 0
  for (const s of filteredSettlements.value) {
    const net = Number.isFinite(s.net_points) ? s.net_points : 0
    const feePoints = Number.isFinite(s.platform_fee_points) ? s.platform_fee_points : 0
    if (getDirection(s) === 'income') {
      income += net
    } else {
      expense += Math.abs(net)
    }
    fee += feePoints
  }
  return { income, expense, fee }
})

function buildFilters() {
  return {
    status: statusFilter.value === 'all' ? undefined : statusFilter.value,
    role: directionFilter.value === 'all' ? undefined : directionFilter.value === 'income' ? 'supplier' : 'demander',
    start_date: dateRange.value.start || undefined,
    end_date: dateRange.value.end || undefined,
  }
}

async function loadSettlements() {
  await platformStore.fetchSettlements(1, 50, buildFilters())
}

async function handleExport() {
  try {
    const data = await platformStore.exportSettlements(buildFilters())
    window.open(data.download_url, '_blank')
    success('导出链接已生成')
  } catch (error: any) {
    danger(error.response?.data?.message || '导出失败')
  }
}

function formatPoints(points: number) {
  if (!Number.isFinite(points)) return '0'
  return points.toLocaleString()
}

function formatSignedPoints(points: number) {
  const value = Number.isFinite(points) ? points : 0
  return `${value > 0 ? '+' : ''}${value.toLocaleString()}`
}

function getStatusLabel(status: SettlementStatus) {
  const labels: Record<SettlementStatus, string> = {
    pending: '处理中',
    settled: '已完成',
    refunding: '退款中',
    refunded: '已退款',
    reversed: '已冲正',
  }
  return labels[status] ?? status
}

function getStatusDot(status: SettlementStatus): 'online' | 'offline' | 'maintenance' {
  if (status === 'settled') return 'online'
  if (status === 'pending' || status === 'refunding') return 'maintenance'
  return 'offline'
}

onMounted(() => {
  loadSettlements()
})
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <!-- 筛选栏 -->
      <Card style="margin-bottom: var(--space-16); padding: var(--space-12);">
        <div style="display: flex; flex-direction: column; gap: var(--space-12);">
          <div style="display: flex; gap: var(--space-8); overflow-x: auto; padding-bottom: var(--space-4); -webkit-overflow-scrolling: touch;">
            <button
              v-for="tab in statusTabs"
              :key="tab.key"
              class="top-tabbar-item"
              :class="{ active: statusFilter === tab.key }"
              @click="statusFilter = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>
          <div style="display: flex; gap: var(--space-8); overflow-x: auto; padding-bottom: var(--space-4); -webkit-overflow-scrolling: touch;">
            <button
              v-for="tab in directionTabs"
              :key="tab.key"
              class="top-tabbar-item"
              :class="{ active: directionFilter === tab.key }"
              @click="directionFilter = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>
          <div style="display: flex; gap: var(--space-8); flex-wrap: wrap;">
            <Input
              v-model="dateRange.start"
              type="date"
              label="开始日期"
              placeholder="开始日期"
              style="flex: 1; min-width: 140px;"
            />
            <Input
              v-model="dateRange.end"
              type="date"
              label="结束日期"
              placeholder="结束日期"
              style="flex: 1; min-width: 140px;"
            />
            <Button variant="outline" @click="loadSettlements">
              <Icon name="refresh-cw" class="icon-md" /> 筛选
            </Button>
            <Button variant="primary" @click="handleExport">
              <Icon name="download" class="icon-md" /> 导出 CSV
            </Button>
          </div>
        </div>
      </Card>

      <!-- 结算列表 -->
      <Card v-if="platformStore.isLoading" style="padding: 0;">
        <Skeleton type="card" v-for="i in 5" :key="i" style="margin: var(--space-16);" />
      </Card>

      <Card v-else-if="filteredSettlements.length === 0" style="padding: var(--space-32);">
        <EmptyState
          icon="wallet"
          title="暂无结算记录"
          description="完成任务后将生成结算记录"
        />
      </Card>

      <div v-else style="display: flex; flex-direction: column; gap: var(--space-8);">
        <ListRow
          v-for="settlement in filteredSettlements"
          :key="settlement.id"
          :title="`结算单 ${settlement.settlement_no}`"
          :subtitle="`任务 ${settlement.task_no || settlement.task_id.slice(0, 8)} · ${formatDateTime(settlement.created_at)}`"
          :status="getStatusDot(settlement.status)"
          :metaLabel="getStatusLabel(settlement.status)"
          :badge="`${formatSignedPoints(settlement.net_points)}分`"
          :badgeVariant="getDirection(settlement) === 'income' ? 'success' : 'danger'"
        />
      </div>

      <!-- 底部统计 -->
      <Card style="margin-top: var(--space-16);">
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-12); text-align: center;">
          <div>
            <div class="stat-value">{{ filteredSettlements.length }}</div>
            <div class="stat-label">结算笔数</div>
          </div>
          <div>
            <div class="stat-value" style="color: var(--color-success);">{{ formatPoints(totals.income) }}</div>
            <div class="stat-label">收入合计 (分)</div>
          </div>
          <div>
            <div class="stat-value" style="color: var(--color-danger);">{{ formatPoints(totals.expense) }}</div>
            <div class="stat-label">支出合计 (分)</div>
          </div>
          <div>
            <div class="stat-value">{{ formatPoints(totals.fee) }}</div>
            <div class="stat-label">平台总抽成 (分)</div>
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.stat-value {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-text);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  margin-top: var(--space-4);
}
</style>