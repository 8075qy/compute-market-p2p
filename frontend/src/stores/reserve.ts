import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  PoolOverview,
  InterestRecord,
  InterestAllocation,
  BorrowRecord,
  BorrowResponse,
  PaginatedResponse,
} from '@/types'
import { api } from '@/composables/useApi'

export const useReserveStore = defineStore('reserve', () => {
  const poolOverview = ref<PoolOverview | null>(null)
  const interestRecords = ref<InterestRecord[]>([])
  const myInterest = ref<InterestAllocation[]>([])
  const borrowRecords = ref<BorrowRecord[]>([])
  const isLoading = ref(false)
  const borrowing = ref(false)

  async function fetchPoolOverview() {
    const data = await api.get<PoolOverview>('/reserve/pool')
    poolOverview.value = data
    return data
  }

  async function fetchInterestRecords(page = 1, page_size = 20) {
    const data = await api.get<PaginatedResponse<InterestRecord>>('/reserve/interest-records', { page, page_size })
    interestRecords.value = data.items
    return data
  }

  async function fetchMyInterest(page = 1, page_size = 20) {
    isLoading.value = true
    try {
      const data = await api.get<PaginatedResponse<InterestAllocation>>('/reserve/interest', { page, page_size })
      myInterest.value = data.items
      return data
    } finally {
      isLoading.value = false
    }
  }

  async function fetchBorrowRecords(page = 1, page_size = 20) {
    isLoading.value = true
    try {
      const data = await api.get<PaginatedResponse<BorrowRecord>>('/reserve/borrows', { page, page_size })
      borrowRecords.value = data.items
      return data
    } finally {
      isLoading.value = false
    }
  }

  async function borrow(amount_points: number): Promise<BorrowResponse> {
    borrowing.value = true
    try {
      return await api.post<BorrowResponse>('/reserve/borrow', { amount_points })
    } finally {
      borrowing.value = false
    }
  }

  function clearData() {
    poolOverview.value = null
    interestRecords.value = []
    myInterest.value = []
    borrowRecords.value = []
  }

  return {
    poolOverview,
    interestRecords,
    myInterest,
    borrowRecords,
    isLoading,
    borrowing,
    fetchPoolOverview,
    fetchInterestRecords,
    fetchMyInterest,
    fetchBorrowRecords,
    borrow,
    clearData,
  }
})