import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { useAuthStore } from '@/stores/auth'
import type { ApiResponse } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

class ApiClient {
  private client: AxiosInstance
  private refreshPromise: Promise<string> | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const authStore = useAuthStore()
        if (authStore.accessToken) {
          config.headers.Authorization = `Bearer ${authStore.accessToken}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    this.client.interceptors.response.use(
      (response) => response.data as unknown as AxiosResponse,
      async (error: AxiosError<ApiResponse>) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
        const url = originalRequest?.url || ''
        const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh')

        if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
          originalRequest._retry = true

          try {
            const newToken = await this.refreshAccessToken()
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            return this.client(originalRequest)
          } catch {
            const authStore = useAuthStore()
            authStore.logout()
            if (window.location.pathname !== '/login') {
              window.location.href = '/login'
            }
            return Promise.reject(error)
          }
        }

        return Promise.reject(error)
      }
    )
  }

  private async refreshAccessToken(): Promise<string> {
    if (this.refreshPromise) {
      return this.refreshPromise
    }

    const authStore = useAuthStore()
    if (!authStore.refreshToken) {
      throw new Error('No refresh token')
    }

    this.refreshPromise = (async () => {
      try {
        const response = await axios.post<ApiResponse<{ access_token: string; refresh_token: string }>>(
          `${API_BASE}/auth/refresh`,
          { refresh_token: authStore.refreshToken }
        )
        const { access_token, refresh_token } = response.data.data!
        authStore.setTokens(access_token, refresh_token)
        return access_token
      } finally {
        this.refreshPromise = null
      }
    })()

    return this.refreshPromise
  }

  async get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    const response = await this.client.get<ApiResponse<T>>(url, { params })
    return response.data as T
  }

  async post<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.post<ApiResponse<T>>(url, data)
    return response.data as T
  }

  async put<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.put<ApiResponse<T>>(url, data)
    return response.data as T
  }

  async patch<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.patch<ApiResponse<T>>(url, data)
    return response.data as T
  }

  async delete<T>(url: string): Promise<T> {
    const response = await this.client.delete<ApiResponse<T>>(url)
    return response.data as T
  }
}

export const api = new ApiClient()

export function useApi() {
  return api
}