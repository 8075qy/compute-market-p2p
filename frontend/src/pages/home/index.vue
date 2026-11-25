<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSupplierStore } from '@/stores/supplier'
import { useDemanderStore } from '@/stores/demander'
import { usePlatformStore } from '@/stores/platform'
import { Card, Button, Icon, Progress, StatusDot, Badge, Skeleton, EmptyState } from '@/components/ui'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const authStore = useAuthStore()
const supplierStore = useSupplierStore()
const demanderStore = useDemanderStore()
const platformStore = usePlatformStore()
const { success, danger, info } = useToast()

const stats = ref({
  balance: 0,
  frozen: 0,
  reserve: 0,
  totalEarned: 0,
  totalSpent: 0,
  onlineNodes: 0,
  totalNodes: 0,
  runningTasks: 0,
  pendingTasks: 0,
})

const recentNodes = ref<any[]>([])
const recentTasks = ref<any[]>([])
const marketplaceNodes = computed(() => platformStore.marketplaceNodes)
const isLoading = ref(false)

async function loadData() {
  isLoading.value = true
  try {
    await Promise.all([
      platformStore.fetchAccount(),
      platformStore.fetchMarketplaceNodes(1, 100).catch((error) => {
        console.error('Failed to load marketplace nodes:', error)
        return null
      }),
      authStore.isUser ? supplierStore.fetchNodes(1, 5) : Promise.resolve(),
      authStore.isUser ? demanderStore.fetchTasks(1, 5) : Promise.resolve(),
    ])

    if (platformStore.account) {
      stats.value.balance = platformStore.account.balance_points || 0
      stats.value.frozen = platformStore.account.frozen_points || 0
      stats.value.reserve = platformStore.account.reserve_points || 0
      stats.value.totalEarned = platformStore.account.total_earned
      stats.value.totalSpent = platformStore.account.total_spent
    }

    if (authStore.isUser) {
      stats.value.onlineNodes = supplierStore.onlineNodes.length
      stats.value.totalNodes = supplierStore.nodes.length
      recentNodes.value = supplierStore.onlineNodes.slice(0, 3)

      stats.value.runningTasks = demanderStore.runningTasks.length
      stats.value.pendingTasks = demanderStore.pendingTasks.length
      recentTasks.value = demanderStore.tasks.slice(0, 3)
    }
  } catch (error) {
    console.error('Failed to load home data:', error)
  } finally {
    isLoading.value = false
  }
}

function formatPoints(points: number | null | undefined) {
  return (points ?? 0).toLocaleString()
}

function navigateTo(path: string) {
  router.push(path)
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="page-layout">
    <div class="page-content home">
      <!-- 积分概览 -->
      <section class="balance-card">
        <div class="balance-head">
          <span class="balance-title">
            <span class="balance-dot" aria-hidden="true"></span>
            可用积分
          </span>
          <button type="button" class="link-btn" @click="navigateTo('/settlement')">
            明细
            <Icon name="chevron-right" />
          </button>
        </div>

        <div class="balance-value">{{ formatPoints(stats.balance) }}</div>

        <div class="balance-meta">
          <div class="meta-item">
            <span class="meta-label">冻结</span>
            <span class="meta-num">{{ formatPoints(stats.frozen) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">储备</span>
            <span class="meta-num">{{ formatPoints(stats.reserve) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">累计获得</span>
            <span class="meta-num">{{ formatPoints(stats.totalEarned) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">累计消费</span>
            <span class="meta-num">{{ formatPoints(stats.totalSpent) }}</span>
          </div>
        </div>
      </section>

      <!-- 快捷操作 -->
      <nav class="quick" aria-label="快捷操作">
        <button type="button" class="quick-item" @click="navigateTo('/supplier/nodes')">
          <span class="quick-icon"><Icon name="gpu" /></span>
          <span class="quick-label">管理节点</span>
        </button>
        <button type="button" class="quick-item" @click="navigateTo('/demand/publish')">
          <span class="quick-icon"><Icon name="task" /></span>
          <span class="quick-label">发布任务</span>
        </button>
        <button type="button" class="quick-item" @click="navigateTo('/settlement')">
          <span class="quick-icon"><Icon name="wallet" /></span>
          <span class="quick-label">结算明细</span>
        </button>
      </nav>

      <!-- 算力市场：所有在线共享 GPU 设备 -->
      <section class="panel">
        <header class="panel-head">
          <h2 class="panel-title">算力市场</h2>
          <span class="market-count">{{ marketplaceNodes.length }} 台在线</span>
        </header>

        <div v-if="isLoading" class="stack">
          <Skeleton type="card" v-for="i in 3" :key="i" />
        </div>

        <div v-else-if="marketplaceNodes.length === 0" class="empty-wrap">
          <EmptyState
            icon="network"
            title="暂无在线节点"
            description="还没有 GPU 接入共享网络"
          />
        </div>

        <div v-else class="market-list">
          <div v-for="node in marketplaceNodes" :key="node.id" class="gpu-card">
            <div class="gpu-card-head">
              <div class="gpu-id">
                <span class="gpu-icon"><Icon name="cpu" /></span>
                <div class="gpu-id-main">
                  <h4 class="gpu-name">{{ node.name }}</h4>
                  <p class="gpu-owner">{{ node.owner_nickname || '匿名供给方' }}</p>
                </div>
              </div>
              <StatusDot :status="node.status" />
            </div>

            <div class="gpu-spec">
              <span class="gpu-model">{{ node.gpu_model }}</span>
              <span class="gpu-vram">{{ node.vram_gb }}GB</span>
              <span class="gpu-tflops">{{ node.peak_tflops }} TFLOPS</span>
            </div>

            <div class="gpu-load-row">
              <div class="gpu-load-bar">
                <div class="gpu-load-fill" :style="{ width: `${node.gpu_utilization ?? 0}%` }"></div>
              </div>
              <span class="gpu-load-num">{{ node.gpu_utilization != null ? Math.round(node.gpu_utilization) + '%' : '—' }}</span>
            </div>

            <div class="gpu-card-foot">
              <span class="gpu-region">{{ node.region_province && node.region_city ? `${node.region_province} · ${node.region_city}` : '地区未知' }}</span>
              <span class="gpu-rep">信誉 {{ node.reputation_score }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 我的节点 -->
      <section v-if="authStore.isUser" class="panel">
        <header class="panel-head">
          <h2 class="panel-title">我的节点</h2>
          <button type="button" class="link-btn" @click="navigateTo('/supplier/nodes')">查看全部</button>
        </header>

        <div v-if="isLoading" class="stack">
          <Skeleton type="card" v-for="i in 3" :key="i" />
        </div>

        <div v-else-if="recentNodes.length === 0" class="empty-wrap">
          <EmptyState
            icon="gpu"
            title="暂无节点"
            description="接入闲置GPU/NPU开始赚取积分"
            actionLabel="添加节点"
            :action="() => navigateTo('/supplier/nodes')"
          />
        </div>

        <div v-else class="stack">
          <div v-for="node in recentNodes" :key="node.id" class="list-card">
            <div class="list-icon"><Icon name="gpu" /></div>
            <div class="list-main">
              <h4 class="list-title">{{ node.name }}</h4>
              <p class="list-sub">{{ node.gpu_model }} · {{ node.vram_gb }}GB VRAM</p>
            </div>
            <div class="list-end">
              <StatusDot :status="node.status" />
              <span class="list-price">{{ node.peak_tflops }} TFLOPS</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 最近任务 -->
      <section v-if="authStore.isUser" class="panel">
        <header class="panel-head">
          <h2 class="panel-title">最近任务</h2>
          <button type="button" class="link-btn" @click="navigateTo('/demand/tasks')">查看全部</button>
        </header>

        <div v-if="isLoading" class="stack">
          <Skeleton type="card" v-for="i in 3" :key="i" />
        </div>

        <div v-else-if="recentTasks.length === 0" class="empty-wrap">
          <EmptyState
            icon="task"
            title="暂无任务"
            description="发布推理或训练任务使用算力"
            actionLabel="发布任务"
            :action="() => navigateTo('/demand/publish')"
          />
        </div>

        <div v-else class="stack">
          <div v-for="task in recentTasks" :key="task.id" class="list-card" @click="navigateTo(`/task/${task.id}`)">
            <div class="list-icon" :class="task.type === 'training' ? 'is-warn' : 'is-primary'">
              <Icon :name="task.type === 'training' ? 'trending-up' : 'activity'" />
            </div>
            <div class="list-main">
              <h4 class="list-title">{{ task.title }}</h4>
              <p class="list-sub">
                <Badge :variant="task.type === 'training' ? 'warning' : 'primary'">{{ task.type === 'training' ? '训练' : '推理' }}</Badge>
                <span class="list-budget">预算 {{ task.budget_points }}分</span>
              </p>
            </div>
            <div class="list-end">
              <Badge :variant="task.status === 'running' ? 'success' : task.status === 'completed' ? 'primary' : task.status === 'failed' ? 'danger' : 'muted'">
                {{ task.status === 'running' ? '运行中' : task.status === 'completed' ? '已完成' : task.status === 'failed' ? '失败' : '待调度' }}
              </Badge>
              <Icon name="chevron-right" class="chev" />
            </div>
          </div>
        </div>
      </section>

      <!-- 数据概览 -->
      <section class="panel">
        <header class="panel-head">
          <h2 class="panel-title">数据概览</h2>
        </header>

        <div class="stat-grid">
          <div v-if="authStore.isUser" class="stat-item">
            <div class="stat-value">{{ stats.onlineNodes }} / {{ stats.totalNodes }}</div>
            <div class="stat-label">在线节点 / 总节点</div>
          </div>
          <div v-if="authStore.isUser" class="stat-item">
            <div class="stat-value">{{ supplierStore.earnings?.today || 0 }}</div>
            <div class="stat-label">今日收益 (分)</div>
          </div>
          <div v-if="authStore.isUser" class="stat-item">
            <div class="stat-value">{{ stats.runningTasks }}</div>
            <div class="stat-label">运行中任务</div>
          </div>
          <div v-if="authStore.isUser" class="stat-item">
            <div class="stat-value">{{ stats.pendingTasks }}</div>
            <div class="stat-label">待调度任务</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ formatPoints(stats.balance) }}</div>
            <div class="stat-label">账户余额</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ formatPoints(stats.totalEarned) }}</div>
            <div class="stat-label">累计获得</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.home {
  gap: var(--space-16);
}

/* ===== 积分概览 ===== */
.balance-card {
  position: relative;
  overflow: hidden;
  padding: var(--space-20);
  border-radius: var(--radius-panel);
  background:
    linear-gradient(135deg, var(--color-primary-bg), var(--color-accent-bg)),
    var(--color-surface);
  border: 1px solid var(--color-line);
}

.balance-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.balance-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-8);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.balance-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-circle);
  background: var(--color-primary);
  box-shadow: var(--shadow-glow);
}

.link-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-8);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.link-btn:hover {
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

.link-btn .icon {
  font-size: var(--icon-sm);
}

.balance-value {
  margin: var(--space-12) 0 var(--space-16);
  font-size: var(--text-4xl);
  font-weight: 700;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
  color: var(--color-text);
}

.balance-meta {
  display: flex;
  gap: var(--space-16);
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.meta-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.meta-num {
  font-size: var(--text-sm);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-secondary);
}

/* ===== 快捷操作 ===== */
.quick {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-8);
}

.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-16) var(--space-8);
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.quick-item:hover {
  border-color: var(--color-primary-border);
  background: var(--color-surface-hover);
}

.quick-item:active {
  transform: scale(0.97);
}

.quick-icon {
  font-size: var(--icon-xl);
  color: var(--color-primary);
}

.quick-label {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

/* ===== 面板 ===== */
.panel {
  padding: var(--space-16);
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-panel);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-16);
}

.panel-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text);
}

.stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
}

.empty-wrap {
  padding: var(--space-24) 0;
}

/* ===== 列表卡片 ===== */
.list-card {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  padding: var(--space-12);
  background: var(--color-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.list-card:hover {
  border-color: var(--color-line-hover);
}

.list-card:active {
  background: var(--color-surface-hover);
}

.list-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-card);
  background: var(--color-primary-bg);
  font-size: var(--icon-lg);
  color: var(--color-primary);
}

.list-icon.is-warn {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.list-icon.is-primary {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.list-main {
  flex: 1;
  min-width: 0;
}

.list-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.list-sub {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  margin-top: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.list-budget {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.list-end {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  flex-shrink: 0;
}

.list-price {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-primary);
  font-weight: 600;
}

.chev {
  font-size: var(--icon-sm);
  color: var(--color-text-muted);
}

/* ===== 数据概览 ===== */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-12);
}

.stat-item {
  text-align: center;
  padding: var(--space-16) var(--space-8);
  background: var(--color-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card);
}

.stat-value {
  font-size: var(--text-xl);
  font-weight: 700;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
  color: var(--color-text);
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  margin-top: var(--space-4);
}

/* ===== 算力市场 ===== */
.market-count {
  font-size: var(--text-xs);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  color: var(--color-primary);
  padding: var(--space-4) var(--space-10);
  background: var(--color-primary-bg);
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-pill);
}

.market-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
}

.gpu-card {
  padding: var(--space-16);
  background: var(--color-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card);
  transition: border-color var(--transition-fast);
}

.gpu-card:hover {
  border-color: var(--color-primary-border);
}

.gpu-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-12);
}

.gpu-id {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  min-width: 0;
}

.gpu-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-card);
  background: var(--color-primary-bg);
  font-size: var(--icon-lg);
  color: var(--color-primary);
}

.gpu-id-main {
  min-width: 0;
}

.gpu-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gpu-owner {
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.gpu-spec {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  flex-wrap: wrap;
  margin-top: var(--space-12);
}

.gpu-model {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.gpu-vram {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  padding: var(--space-2) var(--space-8);
  background: var(--color-surface);
  border-radius: var(--radius-sm);
}

.gpu-tflops {
  font-size: var(--text-sm);
  font-weight: 600;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-accent);
}

.gpu-load-row {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  margin-top: var(--space-12);
}

.gpu-load-bar {
  flex: 1;
  height: 6px;
  border-radius: var(--radius-pill);
  background: var(--color-line);
  overflow: hidden;
}

.gpu-load-fill {
  height: 100%;
  border-radius: var(--radius-pill);
  background: var(--gradient-primary);
  transition: width var(--transition-fast);
}

.gpu-load-num {
  min-width: 40px;
  text-align: right;
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-muted);
}

.gpu-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--space-12);
  padding-top: var(--space-12);
  border-top: 1px solid var(--color-line);
}

.gpu-region {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.gpu-rep {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-warning);
}
</style>