<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useReserveStore } from '@/stores/reserve'
import { usePlatformStore } from '@/stores/platform'
import { Card, Button, Input, Icon, Skeleton, EmptyState, ListRow, Badge } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { formatRelativeTime } from '@/utils/datetime'

const reserveStore = useReserveStore()
const platformStore = usePlatformStore()
const { success, danger } = useToast()

const amountPoints = ref<string>('')
const activeTab = ref<'interest' | 'borrows' | 'records'>('interest')

const tabs = [
  { key: 'interest', label: '我的利息' },
  { key: 'borrows', label: '借用流水' },
  { key: 'records', label: '公共池利息' },
] as const

const contributionPercent = computed(() => {
  const account = platformStore.account
  if (!account) return '0.00'
  return (account.reserve_contribution / 100).toFixed(2)
})

function formatPoints(points: number): string {
  return points.toLocaleString()
}

async function loadAll() {
  await Promise.all([
    reserveStore.fetchPoolOverview(),
    reserveStore.fetchMyInterest(),
    reserveStore.fetchBorrowRecords(),
    reserveStore.fetchInterestRecords(),
    platformStore.fetchAccount(),
  ])
}

async function handleBorrow() {
  const amount = Number(amountPoints.value)
  if (!Number.isFinite(amount) || amount <= 0) {
    danger('请输入有效的借用数量')
    return
  }
  try {
    const result = await reserveStore.borrow(amount)
    await Promise.all([platformStore.fetchAccount(), reserveStore.fetchPoolOverview(), reserveStore.fetchBorrowRecords()])
    amountPoints.value = ''
    success(`已取用 ${result.amount_points.toLocaleString()} 分，剩余储备 ${result.reserve_points.toLocaleString()} 分`)
  } catch (error: any) {
    danger(error.response?.data?.message || '借用失败')
  }
}
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <!-- 公共池概览 -->
      <Card style="margin-bottom: var(--space-16);">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text);">算力时间银行</h2>
          <Badge variant="primary">
            <Icon name="trending-up" class="icon-sm" /> 公共池
          </Badge>
        </div>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-12);">
          <div class="pool-card">
            <div class="pool-label">池内储备分</div>
            <div class="pool-value">{{ formatPoints(reserveStore.poolOverview?.pool_total_points ?? 0) }}</div>
          </div>
          <div class="pool-card">
            <div class="pool-label">贡献人数</div>
            <div class="pool-value">{{ reserveStore.poolOverview?.pool_contributors ?? 0 }}</div>
          </div>
          <div class="pool-card">
            <div class="pool-label">累计输出算力</div>
            <div class="pool-value">{{ formatPoints(reserveStore.poolOverview?.total_output_points ?? 0) }}</div>
          </div>
          <div class="pool-card">
            <div class="pool-label">累计派息</div>
            <div class="pool-value" style="color: var(--color-success);">{{ formatPoints(reserveStore.poolOverview?.total_interest_points ?? 0) }}</div>
          </div>
        </div>
        <p v-if="reserveStore.poolOverview?.last_distributed_at" style="font-size: var(--text-xs); color: var(--color-text-muted); margin-top: var(--space-12);">
          <Icon name="clock" class="icon-sm" /> 最近派息：{{ formatRelativeTime(reserveStore.poolOverview.last_distributed_at) }}
        </p>
      </Card>

      <!-- 我的储备与贡献 -->
      <Card style="margin-bottom: var(--space-16);">
        <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">我的储备</h2>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-12);">
          <div class="pool-card">
            <div class="pool-label">我的储备分</div>
            <div class="pool-value">{{ formatPoints(platformStore.account?.reserve_points ?? 0) }}</div>
          </div>
          <div class="pool-card">
            <div class="pool-label">储备贡献率</div>
            <div class="pool-value">{{ contributionPercent }}%</div>
          </div>
        </div>
      </Card>

      <!-- 借用 / 取用 -->
      <Card style="margin-bottom: var(--space-16);">
        <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">借用储备分</h2>
        <p style="font-size: var(--text-sm); color: var(--color-text-muted); margin-bottom: var(--space-12);">
          将储备分取用为自由分，取用后储备贡献率将相应降低。
        </p>
        <div style="display: flex; flex-direction: column; gap: var(--space-12);">
          <Input
            v-model="amountPoints"
            type="number"
            label="取用数量（分）"
            placeholder="请输入取用数量"
            suffix="分"
          />
          <Button variant="primary" :loading="reserveStore.borrowing" :disabled="!amountPoints" @click="handleBorrow" block>
            <Icon name="credit-card" class="icon-md" /> 立即取用
          </Button>
        </div>
      </Card>

      <!-- 明细 tab -->
      <Card style="padding: var(--space-12);">
        <div style="display: flex; gap: var(--space-8); overflow-x: auto; padding-bottom: var(--space-4); -webkit-overflow-scrolling: touch;">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="top-tabbar-item"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- 我的利息 -->
        <div v-if="activeTab === 'interest'">
          <Skeleton v-if="reserveStore.isLoading" type="card" v-for="i in 4" :key="i" style="margin: var(--space-16);" />
          <EmptyState
            v-else-if="reserveStore.myInterest.length === 0"
            icon="activity"
            title="暂无利息明细"
            description="每日派息后将在此展示"
            style="margin: var(--space-24) 0;"
          />
          <div v-else style="display: flex; flex-direction: column; gap: var(--space-8); margin-top: var(--space-8);">
            <ListRow
              v-for="item in reserveStore.myInterest"
              :key="item.id"
              title="储备派息"
              :subtitle="`派息前储备 ${formatPoints(item.reserve_points_before)} 分 · ${formatRelativeTime(item.distributed_at)}`"
              :badge="`+${formatPoints(item.interest_points)} 分`"
              badgeVariant="success"
            />
          </div>
        </div>

        <!-- 借用流水 -->
        <div v-else-if="activeTab === 'borrows'">
          <Skeleton v-if="reserveStore.isLoading" type="card" v-for="i in 4" :key="i" style="margin: var(--space-16);" />
          <EmptyState
            v-else-if="reserveStore.borrowRecords.length === 0"
            icon="credit-card"
            title="暂无借用记录"
            description="取用储备分后将在此展示"
            style="margin: var(--space-24) 0;"
          />
          <div v-else style="display: flex; flex-direction: column; gap: var(--space-8); margin-top: var(--space-8);">
            <ListRow
              v-for="item in reserveStore.borrowRecords"
              :key="item.id"
              title="取用储备分"
              :subtitle="`取用前：自由 ${formatPoints(item.balance_before)} · 储备 ${formatPoints(item.reserve_before)} · ${formatRelativeTime(item.created_at)}`"
              :badge="`-${formatPoints(item.amount_points)} 分`"
              badgeVariant="warning"
            />
          </div>
        </div>

        <!-- 公共池利息记录 -->
        <div v-else>
          <Skeleton v-if="reserveStore.isLoading" type="card" v-for="i in 4" :key="i" style="margin: var(--space-16);" />
          <EmptyState
            v-else-if="reserveStore.interestRecords.length === 0"
            icon="trending-up"
            title="暂无公共池派息记录"
            description="每日派息后将在此展示"
            style="margin: var(--space-24) 0;"
          />
          <div v-else style="display: flex; flex-direction: column; gap: var(--space-8); margin-top: var(--space-8);">
            <ListRow
              v-for="item in reserveStore.interestRecords"
              :key="item.id"
              title="公共池派息"
              :subtitle="`周期输出 ${formatPoints(item.cycle_output_points)} 分 · 池内 ${formatPoints(item.total_reserve_points)} 分 · ${formatRelativeTime(item.distributed_at)}`"
              :badge="`+${formatPoints(item.interest_points)} 分`"
              badgeVariant="success"
            />
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.pool-card {
  padding: var(--space-16);
  background: var(--color-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card);
  text-align: center;
}

.pool-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  margin-bottom: var(--space-4);
}

.pool-value {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-text);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
</style>