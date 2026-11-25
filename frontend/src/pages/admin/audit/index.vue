<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { Card, Button, Icon, Badge, Skeleton, EmptyState, Input } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { formatDateTime } from '@/utils/datetime'
import type { AdminAuditLogItem } from '@/types'

const router = useRouter()
const adminStore = useAdminStore()
const { success, danger } = useToast()

const isLoading = ref(false)
const isVerifying = ref(false)
const verifyResult = ref<{ valid: boolean; errors: string[] } | null>(null)
const expandedId = ref<string | null>(null)

const filters = ref({
  event_type: '',
  entity_type: '',
  user_id: '',
})

async function loadLogs() {
  isLoading.value = true
  try {
    await adminStore.fetchAuditLogs(1, 50, {
      event_type: filters.value.event_type.trim() || undefined,
      entity_type: filters.value.entity_type.trim() || undefined,
      user_id: filters.value.user_id.trim() || undefined,
    })
  } catch (error: any) {
    danger(error.response?.data?.message || '加载审计日志失败')
  } finally {
    isLoading.value = false
  }
}

function resetFilters() {
  filters.value = { event_type: '', entity_type: '', user_id: '' }
  loadLogs()
}

async function verifyChain() {
  isVerifying.value = true
  verifyResult.value = null
  try {
    const result = await adminStore.verifyAuditChain()
    verifyResult.value = result
    if (result.valid) {
      success('哈希链校验通过')
    } else {
      danger(`校验发现 ${result.errors.length} 处异常`)
    }
  } catch (error: any) {
    danger(error.response?.data?.message || '哈希链校验失败')
  } finally {
    isVerifying.value = false
  }
}

function toggleExpand(log: AdminAuditLogItem) {
  expandedId.value = expandedId.value === log.id ? null : log.id
}

function formatPayload(payloadJson: string) {
  try {
    return JSON.stringify(JSON.parse(payloadJson), null, 2)
  } catch {
    return payloadJson
  }
}

function shortHash(hash: string) {
  return hash ? `${hash.slice(0, 12)}…` : '-'
}

onMounted(() => {
  loadLogs()
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
            <h2 class="admin-title">审计日志</h2>
            <p class="admin-subtitle">哈希链式记录，共 {{ adminStore.auditTotal }} 条</p>
          </div>
        </div>
        <button type="button" class="refresh-btn" :disabled="isLoading" @click="loadLogs">
          <Icon name="refresh-cw" class="icon-sm" />
          <span>{{ isLoading ? '刷新中' : '刷新' }}</span>
        </button>
      </div>

      <Card padded>
        <div class="verify-panel">
          <div class="verify-text">
            <span class="verify-title">哈希链完整性校验</span>
            <span class="verify-desc">逐条重算哈希，确认历史记录未被篡改</span>
          </div>
          <Button variant="outline" :loading="isVerifying" @click="verifyChain">开始校验</Button>
        </div>

        <div v-if="verifyResult" class="verify-result" :class="verifyResult.valid ? 'is-valid' : 'is-invalid'">
          <Icon
            :name="verifyResult.valid ? 'check-circle' : 'alert-triangle'"
            class="icon-md"
          />
          <div class="verify-result-body">
            <span class="verify-result-title">
              {{ verifyResult.valid ? '校验通过，记录完整可信' : `发现 ${verifyResult.errors.length} 处异常` }}
            </span>
            <ul v-if="!verifyResult.valid" class="verify-errors">
              <li v-for="(err, i) in verifyResult.errors" :key="i">{{ err }}</li>
            </ul>
          </div>
        </div>
      </Card>

      <Card padded>
        <div class="filter-form">
          <Input v-model="filters.event_type" label="事件类型" placeholder="如 settlement_paid" />
          <Input v-model="filters.entity_type" label="实体类型" placeholder="如 task / node" />
          <Input v-model="filters.user_id" label="用户 ID" placeholder="UUID" />
          <div class="filter-actions">
            <Button variant="ghost" @click="resetFilters">重置</Button>
            <Button :loading="isLoading" @click="loadLogs">查询</Button>
          </div>
        </div>
      </Card>

      <div v-if="isLoading && adminStore.auditLogs.length === 0" class="list-stack">
        <Skeleton v-for="i in 4" :key="i" type="card" />
      </div>

      <Card v-else-if="adminStore.auditLogs.length === 0" padded>
        <EmptyState icon="file-text" title="暂无审计日志" description="调整筛选条件后重试" />
      </Card>

      <div v-else class="list-stack">
        <Card v-for="log in adminStore.auditLogs" :key="log.id" hoverable>
          <button type="button" class="log-item" @click="toggleExpand(log)">
            <div class="log-head">
              <div class="log-title-row">
                <Badge variant="primary">{{ log.event_type }}</Badge>
                <span class="log-entity">{{ log.entity_type }}</span>
              </div>
              <Icon
                :name="expandedId === log.id ? 'chevron-up' : 'chevron-down'"
                class="icon-sm log-toggle"
              />
            </div>

            <div class="log-meta">
              <span class="meta-item">{{ formatDateTime(log.created_at) }}</span>
              <span class="meta-item hash">hash {{ shortHash(log.hash) }}</span>
            </div>

            <div v-if="expandedId === log.id" class="log-detail">
              <div class="detail-row">
                <span class="detail-label">记录 ID</span>
                <span class="detail-value mono">{{ log.id }}</span>
              </div>
              <div v-if="log.entity_id" class="detail-row">
                <span class="detail-label">实体 ID</span>
                <span class="detail-value mono">{{ log.entity_id }}</span>
              </div>
              <div v-if="log.user_id" class="detail-row">
                <span class="detail-label">操作人</span>
                <span class="detail-value mono">{{ log.user_id }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">当前哈希</span>
                <span class="detail-value mono">{{ log.hash }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">前序哈希</span>
                <span class="detail-value mono">{{ log.prev_hash || '（链首）' }}</span>
              </div>
              <div class="detail-block">
                <span class="detail-label">变更内容</span>
                <pre class="payload-pre">{{ formatPayload(log.payload_json) }}</pre>
              </div>
            </div>
          </button>
        </Card>
      </div>
    </div>
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

.verify-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
}

.verify-text {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.verify-title {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--color-text);
}

.verify-desc {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.verify-result {
  display: flex;
  align-items: flex-start;
  gap: var(--space-8);
  margin-top: var(--space-12);
  padding: var(--space-12);
  border-radius: var(--radius-md);
}

.verify-result.is-valid {
  color: var(--color-success);
  background: var(--color-success-bg);
  border: 1px solid var(--color-success-border);
}

.verify-result.is-invalid {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  border: 1px solid var(--color-danger-border);
}

.verify-result-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.verify-result-title {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.verify-errors {
  margin: 0;
  padding-left: var(--space-16);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.filter-form {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-12);
}

.filter-actions {
  display: flex;
  gap: var(--space-8);
  justify-content: flex-end;
}

.list-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
}

.log-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  width: 100%;
  text-align: left;
  background: transparent;
}

.log-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
}

.log-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-width: 0;
}

.log-entity {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-toggle {
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.log-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-12);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.meta-item.hash {
  font-family: var(--font-mono);
}

.log-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  margin-top: var(--space-8);
  padding-top: var(--space-12);
  border-top: 1px solid var(--color-line);
}

.detail-row {
  display: flex;
  gap: var(--space-8);
  font-size: var(--text-xs);
}

.detail-label {
  flex-shrink: 0;
  width: 72px;
  color: var(--color-text-muted);
}

.detail-value {
  color: var(--color-text-secondary);
  word-break: break-all;
}

.detail-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.payload-pre {
  margin: 0;
  padding: var(--space-12);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: var(--leading-relaxed);
  color: var(--color-text-secondary);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.mono {
  font-family: var(--font-mono);
}

@media (min-width: 768px) {
  .filter-form {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .filter-actions {
    grid-column: 1 / -1;
  }
}
</style>