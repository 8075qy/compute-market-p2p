import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Task, TaskCreateRequest, TaskExecution, PaginatedResponse, PresignUploadResponse, UploadConfirmResponse, InputConfirmResponse } from '@/types'
import { api } from '@/composables/useApi'

export const useDemanderStore = defineStore('demander', () => {
  const tasks = ref<Task[]>([])
  const currentTask = ref<Task | null>(null)
  const executions = ref<TaskExecution[]>([])
  const isLoading = ref(false)
  const pagination = ref({
    page: 1,
    page_size: 20,
    total: 0,
    total_pages: 0,
  })

  const pendingTasks = computed(() => tasks.value.filter(t => t.status === 'pending' || t.status === 'scheduling' || t.status === 'assigned'))
  const runningTasks = computed(() => tasks.value.filter(t => t.status === 'running'))
  const completedTasks = computed(() => tasks.value.filter(t => t.status === 'completed'))
  const failedTasks = computed(() => tasks.value.filter(t => t.status === 'failed'))

  async function fetchTasks(page = 1, page_size = 20, status?: string, type?: string) {
    isLoading.value = true
    try {
      const response = await api.get<PaginatedResponse<Task>>('/demand/tasks', {
        page,
        page_size,
        status,
        type,
      })
      if (page === 1) {
        tasks.value = response.items
      } else {
        tasks.value.push(...response.items)
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

  async function createTask(data: TaskCreateRequest) {
    isLoading.value = true
    try {
      const task = await api.post<Task>('/demand/tasks', data)
      tasks.value.unshift(task)
      pagination.value.total += 1
      return task
    } finally {
      isLoading.value = false
    }
  }

  async function getTask(taskId: string) {
    isLoading.value = true
    try {
      const task = await api.get<Task>(`/demand/tasks/${taskId}`)
      currentTask.value = task
      return task
    } finally {
      isLoading.value = false
    }
  }

  async function cancelTask(taskId: string) {
    isLoading.value = true
    try {
      const task = await api.post<Task>(`/demand/tasks/${taskId}/cancel`)
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        tasks.value[index] = task
      }
      if (currentTask.value?.id === taskId) {
        currentTask.value = task
      }
      return task
    } finally {
      isLoading.value = false
    }
  }

  async function retryTask(taskId: string) {
    isLoading.value = true
    try {
      const task = await api.post<Task>(`/demand/tasks/${taskId}/retry`)
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        tasks.value[index] = task
      }
      if (currentTask.value?.id === taskId) {
        currentTask.value = task
      }
      return task
    } finally {
      isLoading.value = false
    }
  }

  async function fetchTaskLogs(taskId: string, attempt_no?: number) {
    isLoading.value = true
    try {
      const params = attempt_no ? { attempt_no } : {}
      const data = await api.get<{ logs: string; attempt_no: number; status: string }>(`/demand/tasks/${taskId}/logs`, params)
      return data
    } finally {
      isLoading.value = false
    }
  }

  async function fetchTaskResult(taskId: string) {
    isLoading.value = true
    try {
      const data = await api.get<{ result_url: string; completed_at: string }>(`/demand/tasks/${taskId}/result`)
      return data
    } finally {
      isLoading.value = false
    }
  }

  async function uploadModelFile(file: File) {
    const presign = await api.post<PresignUploadResponse>('/demand/uploads/model/presign', {
      filename: file.name,
      size: file.size,
      content_type: file.type || 'application/octet-stream',
    })

    const putResponse = await fetch(presign.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      body: file,
    })
    if (!putResponse.ok) {
      throw new Error(`文件上传失败（${putResponse.status}）`)
    }

    const confirmed = await api.post<UploadConfirmResponse>('/demand/uploads/model/confirm', {
      object_key: presign.object_key,
    })
    return { object_key: confirmed.object_key, size: confirmed.size }
  }

  async function uploadInputFile(file: File) {
    const presign = await api.post<PresignUploadResponse>('/demand/uploads/input/presign', {
      filename: file.name,
      size: file.size,
      content_type: file.type || 'application/octet-stream',
    })

    const putResponse = await fetch(presign.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      body: file,
    })
    if (!putResponse.ok) {
      throw new Error(`文件上传失败（${putResponse.status}）`)
    }

    const confirmed = await api.post<InputConfirmResponse>('/demand/uploads/input/confirm', {
      object_key: presign.object_key,
    })
    return {
      object_key: confirmed.object_key,
      file_count: confirmed.file_count,
      file_size: confirmed.file_size,
    }
  }

  function clearTasks() {
    tasks.value = []
    currentTask.value = null
    executions.value = []
    pagination.value = { page: 1, page_size: 20, total: 0, total_pages: 0 }
  }

  return {
    tasks,
    currentTask,
    executions,
    isLoading,
    pagination,
    pendingTasks,
    runningTasks,
    completedTasks,
    failedTasks,
    fetchTasks,
    createTask,
    getTask,
    cancelTask,
    retryTask,
    fetchTaskLogs,
    fetchTaskResult,
    uploadModelFile,
    uploadInputFile,
    clearTasks,
  }
})