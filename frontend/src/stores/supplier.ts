import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Node, NodeDetail, NodeExecution, NodeCreateRequest, NodeUpdateRequest, NodeHeartbeatRequest, PaginatedResponse, GpuSpec } from '@/types'
import { api } from '@/composables/useApi'

export const useSupplierStore = defineStore('supplier', () => {
  const nodes = ref<Node[]>([])
  const currentNode = ref<Node | null>(null)
  const earnings = ref<{
    total: number
    today: number
    this_month: number
    this_week: number
    by_node: Record<string, number>
  } | null>(null)
  const executions = ref<NodeExecution[]>([])
  const isLoading = ref(false)
  const pagination = ref({
    page: 1,
    page_size: 20,
    total: 0,
    total_pages: 0,
  })

  const onlineNodes = computed(() => nodes.value.filter(n => n.status === 'online'))
  const offlineNodes = computed(() => nodes.value.filter(n => n.status === 'offline'))
  const maintenanceNodes = computed(() => nodes.value.filter(n => n.status === 'maintenance'))

  async function fetchNodes(page = 1, page_size = 20, status?: string) {
    isLoading.value = true
    try {
      const response = await api.get<PaginatedResponse<Node>>('/supplier/nodes', {
        page,
        page_size,
        status,
      })
      if (page === 1) {
        nodes.value = response.items
      } else {
        nodes.value.push(...response.items)
      }
      pagination.value = {
        page: response.page,
        page_size: response.page_size,
        total: response.total,
        total_pages: response.total_pages,
      }
      return response
    } finally {
      isLoading.value = false
    }
  }

  async function createNode(data: NodeCreateRequest) {
    isLoading.value = true
    try {
      const node = await api.post<Node>('/supplier/nodes', data)
      nodes.value.unshift(node)
      pagination.value.total += 1
      return node
    } finally {
      isLoading.value = false
    }
  }

  async function getNode(nodeId: string) {
    isLoading.value = true
    try {
      const node = await api.get<NodeDetail>(`/supplier/nodes/${nodeId}`)
      currentNode.value = node
      return node
    } finally {
      isLoading.value = false
    }
  }

  async function updateNode(nodeId: string, data: NodeUpdateRequest) {
    isLoading.value = true
    try {
      const node = await api.put<Node>(`/supplier/nodes/${nodeId}`, data)
      const index = nodes.value.findIndex(n => n.id === nodeId)
      if (index !== -1) {
        nodes.value[index] = node
      }
      if (currentNode.value?.id === nodeId) {
        currentNode.value = node
      }
      return node
    } finally {
      isLoading.value = false
    }
  }

  async function setNodeOnline(nodeId: string) {
    isLoading.value = true
    try {
      const node = await api.post<Node>(`/supplier/nodes/${nodeId}/online`)
      const index = nodes.value.findIndex(n => n.id === nodeId)
      if (index !== -1) {
        nodes.value[index] = node
      }
      if (currentNode.value?.id === nodeId) {
        currentNode.value = node
      }
      return node
    } finally {
      isLoading.value = false
    }
  }

  async function setNodeOffline(nodeId: string) {
    isLoading.value = true
    try {
      const node = await api.post<Node>(`/supplier/nodes/${nodeId}/offline`)
      const index = nodes.value.findIndex(n => n.id === nodeId)
      if (index !== -1) {
        nodes.value[index] = node
      }
      if (currentNode.value?.id === nodeId) {
        currentNode.value = node
      }
      return node
    } finally {
      isLoading.value = false
    }
  }

  async function deleteNode(nodeId: string) {
    isLoading.value = true
    try {
      await api.delete(`/supplier/nodes/${nodeId}`)
      nodes.value = nodes.value.filter(n => n.id !== nodeId)
      pagination.value.total -= 1
      if (currentNode.value?.id === nodeId) {
        currentNode.value = null
      }
    } finally {
      isLoading.value = false
    }
  }

  async function sendHeartbeat(nodeId: string, data: NodeHeartbeatRequest) {
    try {
      const result = await api.post<{
        status: string
        next_heartbeat_at: string
        assigned_tasks: string[]
      }>(`/supplier/nodes/${nodeId}/heartbeat`, data)
      return result
    } catch (error) {
      console.error('Heartbeat failed:', error)
      throw error
    }
  }

  async function fetchNodeExecutions(nodeId: string, page = 1, page_size = 20, status?: string) {
    isLoading.value = true
    try {
      const response = await api.get<PaginatedResponse<NodeExecution>>(`/supplier/nodes/${nodeId}/executions`, {
        page,
        page_size,
        status,
      })
      if (page === 1) {
        executions.value = response.items
      } else {
        executions.value.push(...response.items)
      }
      return response
    } finally {
      isLoading.value = false
    }
  }

  async function fetchNodeEarnings(nodeId: string, period: 'day' | 'week' | 'month' | 'year' = 'month') {
    isLoading.value = true
    try {
      const data = await api.get<{
        total: number
        today: number
        this_month: number
        this_week: number
        by_node: Record<string, number>
      }>(`/supplier/nodes/${nodeId}/earnings`, { period })
      earnings.value = data
      return data
    } finally {
      isLoading.value = false
    }
  }

  function clearNodes() {
    nodes.value = []
    currentNode.value = null
    earnings.value = null
    executions.value = []
    pagination.value = { page: 1, page_size: 20, total: 0, total_pages: 0 }
  }

  async function fetchGpuSpecs() {
    const data = await api.get<GpuSpec[]>('/gpu-specs')
    return data
  }

  async function matchGpuSpec(model: string) {
    const data = await api.get<GpuSpec | null>('/gpu-specs/match', { model })
    return data
  }

  return {
    nodes,
    currentNode,
    earnings,
    executions,
    isLoading,
    pagination,
    onlineNodes,
    offlineNodes,
    maintenanceNodes,
    fetchNodes,
    createNode,
    getNode,
    updateNode,
    setNodeOnline,
    setNodeOffline,
    deleteNode,
    sendHeartbeat,
    fetchNodeExecutions,
    fetchNodeEarnings,
    clearNodes,
    fetchGpuSpecs,
    matchGpuSpec,
  }
})