<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { Card, Button, Icon, Skeleton } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { formatDateTime } from '@/utils/datetime'

const router = useRouter()
const adminStore = useAdminStore()
const { success, danger } = useToast()

const isLoading = ref(false)
const isSubmitting = ref(false)

const form = ref({
  platform_fee_rate: '',
  min_settlement_unit: '',
  max_task_retries: '',
  node_offline_threshold_minutes: '',
  task_scheduling_timeout_minutes: '',
  settlement_timeout_hours: '',
  reserve_ratio: '',
  max_borrow_ratio: '',
  reserve_interest_ratio: '',
})

const fields = [
  {
    key: 'platform_fee_rate',
    label: '平台抽成比例',
    suffix: '万分比',
    hint: '1000 表示 10%，范围 0 - 10000',
    min: 0,
    max: 10000,
  },
  {
    key: 'min_settlement_unit',
    label: '最小结算单位',
    suffix: '分',
    hint: '单次结算的最小积分粒度，需 ≥ 1',
    min: 1,
    max: undefined,
  },
  {
    key: 'max_task_retries',
    label: '任务最大重试次数',
    suffix: '次',
    hint: '范围 0 - 10',
    min: 0,
    max: 10,
  },
  {
    key: 'node_offline_threshold_minutes',
    label: '节点离线判定阈值',
    suffix: '分钟',
    hint: '心跳中断超过该时长判定离线，范围 1 - 60',
    min: 1,
    max: 60,
  },
  {
    key: 'task_scheduling_timeout_minutes',
    label: '任务调度超时',
    suffix: '分钟',
    hint: '超过该时长未派单视为调度异常，范围 1 - 120',
    min: 1,
    max: 120,
  },
  {
    key: 'settlement_timeout_hours',
    label: '结算超时',
    suffix: '小时',
    hint: '超过该时长未结算触发告警，范围 1 - 72',
    min: 1,
    max: 72,
  },
  {
    key: 'reserve_ratio',
    label: '准备金率',
    suffix: '%',
    hint: '结算时强制锁定进储备池的比例，范围 0 - 100',
    min: 0,
    max: 100,
  },
  {
    key: 'max_borrow_ratio',
    label: '单人借用上限',
    suffix: '%',
    hint: '单账户最多借用公共池储备的比例，范围 0 - 100',
    min: 0,
    max: 100,
  },
  {
    key: 'reserve_interest_ratio',
    label: '储备利息比例',
    suffix: '%',
    hint: '公共池产出返还给储备贡献者的比例，范围 0 - 100',
    min: 0,
    max: 100,
  },
] as const

type FieldKey = (typeof fields)[number]['key']

const feeRatePercent = computed(() => {
  const raw = Number(form.value.platform_fee_rate)
  if (Number.isNaN(raw)) return '-'
  return `${(raw / 100).toFixed(2)}%`
})

function fillForm() {
  const config = adminStore.config
  if (!config) return
  form.value = {
    platform_fee_rate: String(config.platform_fee_rate),
    min_settlement_unit: String(config.min_settlement_unit),
    max_task_retries: String(config.max_task_retries),
    node_offline_threshold_minutes: String(config.node_offline_threshold_minutes),
    task_scheduling_timeout_minutes: String(config.task_scheduling_timeout_minutes),
    settlement_timeout_hours: String(config.settlement_timeout_hours),
    reserve_ratio: String(config.reserve_ratio),
    max_borrow_ratio: String(config.max_borrow_ratio),
    reserve_interest_ratio: String(config.reserve_interest_ratio),
  }
}

async function loadConfig() {
  isLoading.value = true
  try {
    await adminStore.fetchConfig()
    fillForm()
  } catch (error: any) {
    danger(error.response?.data?.message || '加载平台配置失败')
  } finally {
    isLoading.value = false
  }
}

function validate(): string | null {
  for (const field of fields) {
    const raw = form.value[field.key as FieldKey]
    const value = Number(raw)
    if (raw === '' || Number.isNaN(value) || !Number.isInteger(value)) {
      return `${field.label}需填写整数`
    }
    if (value < field.min) return `${field.label}不得小于 ${field.min}`
    if (field.max !== undefined && value > field.max) return `${field.label}不得大于 ${field.max}`
  }
  return null
}

async function submit() {
  const error = validate()
  if (error) {
    danger(error)
    return
  }
  isSubmitting.value = true
  try {
    await adminStore.updateConfig({
      platform_fee_rate: Number(form.value.platform_fee_rate),
      min_settlement_unit: Number(form.value.min_settlement_unit),
      max_task_retries: Number(form.value.max_task_retries),
      node_offline_threshold_minutes: Number(form.value.node_offline_threshold_minutes),
      task_scheduling_timeout_minutes: Number(form.value.task_scheduling_timeout_minutes),
      settlement_timeout_hours: Number(form.value.settlement_timeout_hours),
      reserve_ratio: Number(form.value.reserve_ratio),
      max_borrow_ratio: Number(form.value.max_borrow_ratio),
      reserve_interest_ratio: Number(form.value.reserve_interest_ratio),
    })
    fillForm()
    success('平台配置已更新')
  } catch (error: any) {
    danger(error.response?.data?.message || '更新平台配置失败')
  } finally {
    isSubmitting.value = false
  }
}

onMounted(() => {
  loadConfig()
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
            <h2 class="admin-title">平台配置</h2>
            <p class="admin-subtitle">抽成、结算、超时与储备治理</p>
          </div>
        </div>
        <button type="button" class="refresh-btn" :disabled="isLoading" @click="loadConfig">
          <Icon name="refresh-cw" class="icon-sm" />
          <span>{{ isLoading ? '刷新中' : '刷新' }}</span>
        </button>
      </div>

      <Card v-if="isLoading && !adminStore.config" padded>
        <Skeleton type="text" />
        <Skeleton type="text" />
        <Skeleton type="text" />
      </Card>

      <Card v-else padded>
        <div class="config-summary">
          <span class="summary-label">当前抽成比例</span>
          <span class="summary-value">{{ feeRatePercent }}</span>
        </div>

        <div class="config-grid">
          <label v-for="field in fields" :key="field.key" class="config-field">
            <span class="field-label">{{ field.label }}</span>
            <div class="field-input-row">
              <input
                v-model="form[field.key]"
                type="number"
                inputmode="numeric"
                class="field-input"
                :min="field.min"
                :max="field.max"
              />
              <span class="field-suffix">{{ field.suffix }}</span>
            </div>
            <span class="field-hint">{{ field.hint }}</span>
          </label>
        </div>

        <div class="config-foot">
          <span class="config-meta">
            <template v-if="adminStore.config">
              最近更新 {{ formatDateTime(adminStore.config.updated_at) }}
            </template>
          </span>
          <div class="config-actions">
            <Button variant="ghost" :disabled="isLoading" @click="fillForm">还原</Button>
            <Button :loading="isSubmitting" @click="submit">保存配置</Button>
          </div>
        </div>
      </Card>
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

.config-summary {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-8);
  padding-bottom: var(--space-12);
  border-bottom: 1px solid var(--color-line);
}

.summary-label {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.summary-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-16);
  padding: var(--space-16) 0;
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text-secondary);
}

.field-input-row {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-8) var(--space-12);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  transition: border-color var(--transition-fast);
}

.field-input-row:focus-within {
  border-color: var(--color-primary-border);
}

.field-input {
  flex: 1;
  min-width: 0;
  font-size: var(--text-base);
  font-family: var(--font-mono);
  color: var(--color-text);
  background: transparent;
  border: none;
  outline: none;
}

.field-suffix {
  flex-shrink: 0;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.field-hint {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.config-foot {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
  padding-top: var(--space-12);
  border-top: 1px solid var(--color-line);
}

.config-meta {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.config-actions {
  display: flex;
  gap: var(--space-8);
  justify-content: flex-end;
}

@media (min-width: 768px) {
  .config-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .config-foot {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
}
</style>