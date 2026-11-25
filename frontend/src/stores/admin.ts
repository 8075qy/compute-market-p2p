import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  AdminAuditLogItem,
  AdminAuditVerifyResult,
  AdminDashboardStats,
  AdminNodeListItem,
  AdminTaskListItem,
  AdminUserListItem,
  PaginatedResponse,
  PlatformConfig,
} from '@/types'
import { api } from '@/composables/useApi'

export const useAdminStore = defineStore('admin', () => {
  const dashboard = ref<AdminDashboardStats | null>(null)
  const nodes = ref<AdminNodeListItem[]>([])
  const nodesTotal = ref(0)
  const tasks = ref<AdminTaskListItem[]>([])
  const tasksTotal = ref(0)
  const users = ref<AdminUserListItem[]>([])
  const usersTotal = ref(0)
  const auditLogs = ref<AdminAuditLogItem[]>([])
  const auditTotal = ref(0)
  const config = ref<PlatformConfig | null>(null)
  const isLoading = ref(false)

  async function fetchDashboard() {
    isLoading.value = true
    try {
      dashboard.value = await api.get<AdminDashboardStats>('/admin/dashboard')
      return dashboard.value
    } finally {
      isLoading.value = false
    }
  }

  async function fetchNodes(page = 1, pageSize = 20, status?: string) {
    isLoading.value = true
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize }
      if (status) params.status = status
      const data = await api.get<PaginatedResponse<AdminNodeListItem>>('/admin/nodes', params)
      nodes.value = data.items
      nodesTotal.value = data.total
      return data
    } finally {
      isLoading.value = false
    }
  }

  async function forceNodeOffline(nodeId: string, reason: string) {
    const node = await api.post<AdminNodeListItem>(`/admin/nodes/${nodeId}/force-offline`, {
      reason,
    })
    const index = nodes.value.findIndex((n) => n.id === nodeId)
    if (index !== -1) nodes.value[index] = node
    return node
  }

  async function fetchTasks(page = 1, pageSize = 20, status?: string) {
    isLoading.value = true
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize }
      if (status) params.status = status
      const data = await api.get<PaginatedResponse<AdminTaskListItem>>('/admin/tasks', params)
      tasks.value = data.items
      tasksTotal.value = data.total
      return data
    } finally {
      isLoading.value = false
    }
  }

  async function cancelTaskScheduling(taskId: string) {
    const task = await api.post<AdminTaskListItem>(`/admin/tasks/${taskId}/cancel-scheduling`)
    const index = tasks.value.findIndex((t) => t.id === taskId)
    if (index !== -1) tasks.value[index] = task
    return task
  }

  async function fetchUsers(
    page = 1,
    pageSize = 20,
    filters?: { keyword?: string; role?: string; is_active?: boolean }
  ) {
    isLoading.value = true
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize }
      if (filters?.keyword) params.keyword = filters.keyword
      if (filters?.role) params.role = filters.role
      if (filters?.is_active !== undefined) params.is_active = filters.is_active
      const data = await api.get<PaginatedResponse<AdminUserListItem>>('/admin/users', params)
      users.value = data.items
      usersTotal.value = data.total
      return data
    } finally {
      isLoading.value = false
    }
  }

  async function setUserActive(userId: string, isActive: boolean, reason: string) {
    const user = await api.post<AdminUserListItem>(`/admin/users/${userId}/set-active`, {
      is_active: isActive,
      reason,
    })
    const index = users.value.findIndex((u) => u.id === userId)
    if (index !== -1) users.value[index] = user
    return user
  }

  async function fetchAuditLogs(
    page = 1,
    pageSize = 20,
    filters?: { event_type?: string; entity_type?: string; user_id?: string }
  ) {
    isLoading.value = true
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize }
      if (filters?.event_type) params.event_type = filters.event_type
      if (filters?.entity_type) params.entity_type = filters.entity_type
      if (filters?.user_id) params.user_id = filters.user_id
      const data = await api.get<PaginatedResponse<AdminAuditLogItem>>('/admin/audit-logs', params)
      auditLogs.value = data.items
      auditTotal.value = data.total
      return data
    } finally {
      isLoading.value = false
    }
  }

  async function verifyAuditChain(startFrom?: string) {
    const params: Record<string, unknown> = {}
    if (startFrom) params.start_from = startFrom
    return api.get<AdminAuditVerifyResult>('/admin/audit-logs/verify', params)
  }

  async function fetchConfig() {
    isLoading.value = true
    try {
      config.value = await api.get<PlatformConfig>('/admin/config')
      return config.value
    } finally {
      isLoading.value = false
    }
  }

  async function updateConfig(payload: Partial<PlatformConfig>) {
    isLoading.value = true
    try {
      config.value = await api.put<PlatformConfig>('/admin/config', payload)
      return config.value
    } finally {
      isLoading.value = false
    }
  }

  return {
    dashboard,
    nodes,
    nodesTotal,
    tasks,
    tasksTotal,
    users,
    usersTotal,
    auditLogs,
    auditTotal,
    config,
    isLoading,
    fetchDashboard,
    fetchNodes,
    forceNodeOffline,
    fetchTasks,
    cancelTaskScheduling,
    fetchUsers,
    setUserActive,
    fetchAuditLogs,
    verifyAuditChain,
    fetchConfig,
    updateConfig,
  }
})