import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Account, Settlement, PaginatedResponse, MarketplaceNode, PlatformModel } from '@/types'
import { api } from '@/composables/useApi'

export const usePlatformStore = defineStore('platform', () => {
  const account = ref<Account | null>(null)
  const marketplaceNodes = ref<MarketplaceNode[]>([])
  const models = ref<PlatformModel[]>([])
  const settlements = ref<Settlement[]>([])
  const isLoading = ref(false)
  const settlementPagination = ref({
    page: 1,
    page_size: 20,
    total: 0,
    total_pages: 0,
  })

  const availableBalance = computed(() => account.value?.balance_points || 0)
  const totalEarned = computed(() => account.value?.total_earned || 0)
  const totalSpent = computed(() => account.value?.total_spent || 0)

  async function fetchAccount() {
    isLoading.value = true
    try {
      const data = await api.get<Account>('/account')
      account.value = data
      return data
    } finally {
      isLoading.value = false
    }
  }

  async function fetchMarketplaceNodes(page = 1, page_size = 20) {
    const response = await api.get<PaginatedResponse<MarketplaceNode>>('/marketplace/nodes', { page, page_size })
    if (page === 1) {
      marketplaceNodes.value = response.items
    } else {
      marketplaceNodes.value.push(...response.items)
    }
    return response
  }

  async function fetchModels(keyword?: string) {
    const response = await api.get<PaginatedResponse<PlatformModel>>('/demand/models', { page: 1, page_size: 100, keyword })
    models.value = response.items
    return response
  }

  async function fetchSettlements(page = 1, page_size = 20, filters?: {
    status?: string
    role?: string
    start_date?: string
    end_date?: string
  }) {
    isLoading.value = true
    try {
      const response = await api.get<PaginatedResponse<Settlement>>('/settlements', {
        page,
        page_size,
        ...filters,
      })
      if (page === 1) {
        settlements.value = response.items
      } else {
        settlements.value.push(...response.items)
      }
      settlementPagination.value = {
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

  async function exportSettlements(filters?: {
    status?: string
    role?: string
    start_date?: string
    end_date?: string
  }) {
    isLoading.value = true
    try {
      const data = await api.get<{ download_url: string; expires_at: string }>('/settlements/export', filters)
      return data
    } finally {
      isLoading.value = false
    }
  }

  function clearData() {
    account.value = null
    marketplaceNodes.value = []
    models.value = []
    settlements.value = []
    settlementPagination.value = { page: 1, page_size: 20, total: 0, total_pages: 0 }
  }

  return {
    account,
    marketplaceNodes,
    models,
    settlements,
    isLoading,
    settlementPagination,
    availableBalance,
    totalEarned,
    totalSpent,
    fetchAccount,
    fetchMarketplaceNodes,
    fetchModels,
    fetchSettlements,
    exportSettlements,
    clearData,
  }
})