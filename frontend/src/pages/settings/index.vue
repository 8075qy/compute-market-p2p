<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { usePlatformStore } from '@/stores/platform'
import { Button, Input, Card, Badge, Icon } from '@/components/ui'
import { useToast } from '@/composables/useToast'

const authStore = useAuthStore()
const platformStore = usePlatformStore()
const { success, danger, info } = useToast()

onMounted(() => {
  platformStore.fetchAccount().catch((error) => {
    console.error('Failed to load account:', error)
  })
})

const profileForm = reactive({
  nickname: authStore.user?.nickname || '',
  avatar_url: authStore.user?.avatar_url || '',
})

const isUpdatingProfile = ref(false)
const roleLabels = computed(() => {
  const labels = (authStore.user?.roles ?? []).map(r => (r === 'user' ? '普通用户' : r === 'admin' ? '管理员' : r))
  return labels.length ? labels.join(' + ') : '未设置'
})
const roleBadgeVariant = computed(() => {
  const roles = authStore.user?.roles ?? []
  if (roles.includes('admin')) return 'warning'
  return 'primary'
})
const contributionPercent = computed(() => {
  const contribution = platformStore.account?.reserve_contribution ?? 0
  return (contribution / 100).toFixed(2)
})

async function updateProfile() {
  if (isUpdatingProfile.value) return
  isUpdatingProfile.value = true
  try {
    await authStore.updateProfile(profileForm.nickname || undefined, profileForm.avatar_url || undefined)
    success('资料更新成功')
  } catch (error: any) {
    danger(error.response?.data?.message || '更新失败')
  } finally {
    isUpdatingProfile.value = false
  }
}

function logout() {
  const confirmed = confirm('确定要退出登录吗？')
  if (confirmed) {
    authStore.logout()
    info('已退出登录')
  }
}
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <!-- 个人资料 -->
      <Card style="margin-bottom: var(--space-16);">
        <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">个人资料</h2>
        <div style="display: flex; flex-direction: column; gap: var(--space-16);">
          <div style="display: flex; align-items: center; gap: var(--space-12);">
            <div style="width: 56px; height: 56px; border-radius: var(--radius-circle); background: var(--color-primary-hover); display: flex; align-items: center; justify-content: center;">
              <Icon name="user" class="icon-xl" style="color: var(--color-primary);" />
            </div>
            <div style="flex: 1;">
              <h3 style="font-size: var(--text-base); font-weight: 600; color: var(--color-text);">{{ authStore.user?.nickname || '未设置昵称' }}</h3>
              <p style="font-size: var(--text-sm); color: var(--color-text-muted);">{{ authStore.user?.phone }}</p>
              <p style="font-size: var(--text-xs); color: var(--color-text-muted); margin-top: 2px;">角色：{{ roleLabels }}</p>
            </div>
            <Badge :variant="roleBadgeVariant">
              {{ roleLabels }}
            </Badge>
          </div>
          <Input
            v-model="profileForm.nickname"
            label="昵称"
            placeholder="请输入昵称"
            clearable
          />
          <Button variant="primary" :loading="isUpdatingProfile" @click="updateProfile" style="margin-top: var(--space-8);">
            保存资料
          </Button>
        </div>
      </Card>

      <!-- 账户余额 -->
      <Card style="margin-bottom: var(--space-16);">
        <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">账户余额</h2>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-12);">
          <div class="balance-card">
            <div class="balance-label">可用余额</div>
            <div class="balance-value">{{ platformStore.account?.balance_points ? platformStore.account.balance_points.toLocaleString() : 0 }} 分</div>
          </div>
          <div class="balance-card">
            <div class="balance-label">冻结余额</div>
            <div class="balance-value">{{ platformStore.account?.frozen_points ? platformStore.account.frozen_points.toLocaleString() : 0 }} 分</div>
          </div>
          <div class="balance-card">
            <div class="balance-label">储备分</div>
            <div class="balance-value">{{ platformStore.account?.reserve_points ? platformStore.account.reserve_points.toLocaleString() : 0 }} 分</div>
          </div>
          <div class="balance-card">
            <div class="balance-label">储备贡献率</div>
            <div class="balance-value">{{ contributionPercent }}%</div>
          </div>
          <div class="balance-card">
            <div class="balance-label">累计获得</div>
            <div class="balance-value">{{ platformStore.account?.total_earned ? platformStore.account.total_earned.toLocaleString() : 0 }} 分</div>
          </div>
          <div class="balance-card">
            <div class="balance-label">累计消费</div>
            <div class="balance-value">{{ platformStore.account?.total_spent ? platformStore.account.total_spent.toLocaleString() : 0 }} 分</div>
          </div>
        </div>
        <div style="margin-top: var(--space-16); display: flex; gap: var(--space-8); flex-wrap: wrap;">
          <Button variant="primary" @click="$router.push('/settlement')">
            <Icon name="wallet" class="icon-md" /> 结算明细
          </Button>
          <Button variant="outline" @click="$router.push('/reserve-bank')">
            <Icon name="trending-up" class="icon-md" /> 算力时间银行
          </Button>
        </div>
      </Card>

      <!-- 关于与退出 -->
      <Card style="margin-bottom: var(--space-32);">
        <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">关于</h2>
        <div style="display: flex; flex-direction: column; gap: var(--space-12); font-size: var(--text-sm); color: var(--color-text-muted);">
          <div style="display: flex; justify-content: space-between;">
            <span>版本</span>
            <span class="tabular-nums">1.0.0</span>
          </div>
          <div style="display: flex; justify-content: space-between;">
            <span>运行环境</span>
            <span>UniApp / Vue 3</span>
          </div>
          <div style="display: flex; justify-content: space-between;">
            <span>数据存储</span>
            <span>本地加密存储</span>
          </div>
          <Button variant="danger" @click="logout" style="margin-top: var(--space-8);">
            <Icon name="log-out" class="icon-md" /> 退出登录
          </Button>
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.balance-card {
  padding: var(--space-16);
  background: var(--color-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card);
  text-align: center;
}

.balance-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  margin-bottom: var(--space-4);
}

.balance-value {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-text);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
</style>