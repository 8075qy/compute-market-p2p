<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { Card, Button, Icon, Badge, Skeleton, EmptyState, Modal, Input } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { formatRelativeTime, maskPhone } from '@/utils/datetime'
import type { AdminUserListItem } from '@/types'

const router = useRouter()
const adminStore = useAdminStore()
const { success, danger } = useToast()

const isLoading = ref(false)
const keyword = ref('')
const roleFilter = ref<'all' | 'user' | 'admin'>('all')
const statusFilter = ref<'all' | 'active' | 'disabled'>('all')

const roleTabs = [
  { key: 'all', label: '全部角色' },
  { key: 'user', label: '普通用户' },
  { key: 'admin', label: '管理员' },
] as const

const statusTabs = [
  { key: 'all', label: '全部状态' },
  { key: 'active', label: '正常' },
  { key: 'disabled', label: '已封禁' },
] as const

const activeModalVisible = ref(false)
const activeTarget = ref<AdminUserListItem | null>(null)
const activeAction = ref<'disable' | 'enable'>('disable')
const activeReason = ref('')
const isSubmitting = ref(false)

async function loadUsers() {
  isLoading.value = true
  try {
    await adminStore.fetchUsers(1, 100, {
      keyword: keyword.value.trim() || undefined,
      role: roleFilter.value === 'all' ? undefined : roleFilter.value,
      is_active:
        statusFilter.value === 'all'
          ? undefined
          : statusFilter.value === 'active',
    })
  } catch (error: any) {
    danger(error.response?.data?.message || '加载用户列表失败')
  } finally {
    isLoading.value = false
  }
}

function changeRole(key: typeof roleFilter.value) {
  roleFilter.value = key
  loadUsers()
}

function changeStatus(key: typeof statusFilter.value) {
  statusFilter.value = key
  loadUsers()
}

function resetFilters() {
  keyword.value = ''
  roleFilter.value = 'all'
  statusFilter.value = 'all'
  loadUsers()
}

function isAdminUser(user: AdminUserListItem) {
  return user.roles.includes('admin')
}

function displayName(user: AdminUserListItem) {
  return user.nickname || user.username || maskPhone(user.phone) || user.email || '未命名用户'
}

function openActiveModal(user: AdminUserListItem) {
  activeTarget.value = user
  activeAction.value = user.is_active ? 'disable' : 'enable'
  activeReason.value = user.is_active ? '' : '恢复正常使用'
  activeModalVisible.value = true
}

async function submitActive() {
  const reason = activeReason.value.trim()
  if (!reason) {
    danger('请填写操作原因')
    return
  }
  if (!activeTarget.value) return
  isSubmitting.value = true
  try {
    await adminStore.setUserActive(
      activeTarget.value.id,
      activeAction.value === 'enable',
      reason
    )
    success(activeAction.value === 'disable' ? '用户已封禁' : '用户已解封')
    activeModalVisible.value = false
  } catch (error: any) {
    danger(error.response?.data?.message || '操作失败')
  } finally {
    isSubmitting.value = false
  }
}

function formatNumber(value: number) {
  return (value ?? 0).toLocaleString()
}

onMounted(() => {
  loadUsers()
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
            <h2 class="admin-title">用户管理</h2>
            <p class="admin-subtitle">共 {{ adminStore.usersTotal }} 个用户</p>
          </div>
        </div>
        <button type="button" class="refresh-btn" :disabled="isLoading" @click="loadUsers">
          <Icon name="refresh-cw" class="icon-sm" />
          <span>{{ isLoading ? '刷新中' : '刷新' }}</span>
        </button>
      </div>

      <Card padded>
        <div class="filter-form">
          <Input v-model="keyword" label="关键词" placeholder="用户名 / 手机号 / 邮箱 / 昵称" />
          <div class="filter-actions">
            <Button variant="ghost" @click="resetFilters">重置</Button>
            <Button :loading="isLoading" @click="loadUsers">查询</Button>
          </div>
        </div>
      </Card>

      <div class="filter-bar">
        <button
          v-for="tab in roleTabs"
          :key="tab.key"
          type="button"
          class="filter-chip"
          :class="{ active: roleFilter === tab.key }"
          @click="changeRole(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="filter-bar">
        <button
          v-for="tab in statusTabs"
          :key="tab.key"
          type="button"
          class="filter-chip"
          :class="{ active: statusFilter === tab.key }"
          @click="changeStatus(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>

      <div v-if="isLoading && adminStore.users.length === 0" class="list-stack">
        <Skeleton v-for="i in 4" :key="i" type="card" />
      </div>

      <Card v-else-if="adminStore.users.length === 0" padded>
        <EmptyState icon="users" title="暂无用户" description="调整筛选条件后重试" />
      </Card>

      <div v-else class="list-stack">
        <Card v-for="user in adminStore.users" :key="user.id" hoverable>
          <div class="user-card">
            <div class="user-head">
              <div class="user-title-row">
                <span class="user-name">{{ displayName(user) }}</span>
              </div>
              <div class="user-badges">
                <Badge :variant="isAdminUser(user) ? 'primary' : 'muted'">
                  {{ isAdminUser(user) ? '管理员' : '用户' }}
                </Badge>
                <Badge :variant="user.is_active ? 'success' : 'danger'">
                  {{ user.is_active ? '正常' : '已封禁' }}
                </Badge>
              </div>
            </div>

            <div class="user-meta">
              <span v-if="user.username" class="meta-item">账号 {{ user.username }}</span>
              <span v-if="user.phone" class="meta-item">手机 {{ maskPhone(user.phone) }}</span>
              <span v-if="user.email" class="meta-item">邮箱 {{ user.email }}</span>
            </div>

            <div class="user-foot">
              <span class="balance">
                可用积分 {{ formatNumber(user.balance_points) }} 分
              </span>
              <span class="registered">注册 {{ formatRelativeTime(user.created_at) }}</span>
            </div>

            <div v-if="!isAdminUser(user)" class="user-actions">
              <Button
                v-if="user.is_active"
                variant="danger"
                size="sm"
                @click="openActiveModal(user)"
              >
                封禁
              </Button>
              <Button
                v-else
                variant="outline"
                size="sm"
                @click="openActiveModal(user)"
              >
                解封
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>

    <Modal
      :visible="activeModalVisible"
      :title="activeAction === 'disable' ? '封禁用户' : '解封用户'"
      @close="activeModalVisible = false"
    >
      <p class="modal-hint">
        {{
          activeAction === 'disable'
            ? `用户「${activeTarget ? displayName(activeTarget) : ''}」将被封禁，封禁后无法登录与使用系统，请填写封禁原因。`
            : `用户「${activeTarget ? displayName(activeTarget) : ''}」将恢复为正常状态，可正常登录与使用系统。`
        }}
      </p>
      <Input
        v-model="activeReason"
        label="操作原因"
        placeholder="请填写操作原因"
        :maxlength="256"
      />
      <template #footer>
        <Button variant="ghost" @click="activeModalVisible = false">取消</Button>
        <Button
          :variant="activeAction === 'disable' ? 'danger' : 'primary'"
          :loading="isSubmitting"
          @click="submitActive"
        >
          {{ activeAction === 'disable' ? '确认封禁' : '确认解封' }}
        </Button>
      </template>
    </Modal>
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

.filter-form {
  display: flex;
  align-items: flex-end;
  gap: var(--space-8);
}

.filter-form :deep(.input-wrapper) {
  flex: 1;
}

.filter-actions {
  display: flex;
  gap: var(--space-8);
  flex-shrink: 0;
}

.filter-bar {
  display: flex;
  gap: var(--space-8);
  overflow-x: auto;
  padding-bottom: var(--space-4);
  -webkit-overflow-scrolling: touch;
}

.filter-chip {
  flex-shrink: 0;
  padding: var(--space-4) var(--space-12);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text-muted);
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-pill);
  transition: all var(--transition-fast);
}

.filter-chip.active {
  color: var(--color-primary);
  background: var(--color-primary-bg);
  border-color: var(--color-primary-border);
}

.list-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
}

.user-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
}

.user-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-8);
}

.user-name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}

.user-badges {
  display: flex;
  gap: var(--space-4);
  flex-shrink: 0;
}

.user-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4) var(--space-12);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.user-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.balance {
  color: var(--color-text-secondary);
}

.user-actions {
  display: flex;
  justify-content: flex-end;
}

.modal-hint {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-12);
  line-height: var(--leading-normal);
}
</style>