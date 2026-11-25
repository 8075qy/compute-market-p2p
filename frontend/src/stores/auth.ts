import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, AuthTokens, UserRole } from '@/types'
import { api } from '@/composables/useApi'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const isLoading = ref(false)
  const needSetup = ref(false)
  const setupChecked = ref(false)

  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const isUser = computed(() => user.value?.roles?.includes('user') ?? false)
  const isAdmin = computed(() => user.value?.roles?.includes('admin') ?? false)

  function setTokens(newAccessToken: string, newRefreshToken: string) {
    accessToken.value = newAccessToken
    refreshToken.value = newRefreshToken
    uni.setStorageSync('access_token', newAccessToken)
    uni.setStorageSync('refresh_token', newRefreshToken)
  }

  function clearTokens() {
    accessToken.value = null
    refreshToken.value = null
    uni.removeStorageSync('access_token')
    uni.removeStorageSync('refresh_token')
  }

  function setUser(newUser: User) {
    user.value = newUser
    uni.setStorageSync('user', JSON.stringify(newUser))
  }

  function clearUser() {
    user.value = null
    uni.removeStorageSync('user')
  }

  async function loadFromStorage() {
    const storedAccessToken = uni.getStorageSync('access_token')
    const storedRefreshToken = uni.getStorageSync('refresh_token')
    const storedUser = uni.getStorageSync('user')

    if (storedAccessToken && storedRefreshToken && storedUser) {
      accessToken.value = storedAccessToken
      refreshToken.value = storedRefreshToken
      try {
        user.value = JSON.parse(storedUser)
        await fetchCurrentUser()
      } catch {
        logout()
      }
    }
  }

  async function login(contact: string, password: string) {
    isLoading.value = true
    try {
      const response = await api.post<{ user: User; access_token: string; refresh_token: string }>('/auth/login', {
        contact,
        password,
      })
      setTokens(response.access_token, response.refresh_token)
      setUser(response.user)
      return response.user
    } finally {
      isLoading.value = false
    }
  }

  async function setupAdmin(username: string, password: string, nickname?: string) {
    isLoading.value = true
    try {
      const response = await api.post<{ user: User; access_token: string; refresh_token: string }>('/auth/setup', {
        username,
        password,
        nickname: nickname || undefined,
      })
      setTokens(response.access_token, response.refresh_token)
      setUser(response.user)
      needSetup.value = false
      setupChecked.value = true
      return response.user
    } finally {
      isLoading.value = false
    }
  }

  async function register(data: {
    username: string
    password: string
    nickname?: string
  }) {
    isLoading.value = true
    try {
      const response = await api.post<{ user: User; access_token: string; refresh_token: string }>('/auth/register', data)
      setTokens(response.access_token, response.refresh_token)
      setUser(response.user)
      return response.user
    } finally {
      isLoading.value = false
    }
  }

  async function fetchCurrentUser() {
    if (!accessToken.value) return
    try {
      const response = await api.get<{ user: User; account: User['account']; roles: UserRole[] }>('/auth/me')
      setUser(response.user)
      return response.user
    } catch {
      logout()
    }
  }

  async function refreshAccessToken() {
    if (!refreshToken.value) throw new Error('No refresh token')
    const response = await api.post<{ access_token: string; refresh_token: string }>('/auth/refresh', {
      refresh_token: refreshToken.value,
    })
    setTokens(response.access_token, response.refresh_token)
    return response.access_token
  }

  async function updateProfile(nickname?: string, avatar_url?: string) {
    if (!user.value) return
    isLoading.value = true
    try {
      const updated = await api.put<User>('/auth/me', { nickname, avatar_url })
      setUser(updated)
      return updated
    } finally {
      isLoading.value = false
    }
  }

  function logout() {
    clearTokens()
    clearUser()
    user.value = null
  }

  async function sendCode(phone: string, type: 'register' | 'login' | 'reset' = 'register') {
    await api.post('/auth/send-code', { phone, type })
  }

  async function checkSetupStatus(force = false) {
    if (setupChecked.value && !force) return needSetup.value
    try {
      const response = await api.get<{ need_setup: boolean }>('/auth/setup-status')
      needSetup.value = response.need_setup
      setupChecked.value = true
      return needSetup.value
    } catch {
      return false
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    isLoading,
    needSetup,
    setupChecked,
    isAuthenticated,
    isUser,
    isAdmin,
    setTokens,
    clearTokens,
    setUser,
    clearUser,
    loadFromStorage,
    login,
    setupAdmin,
    register,
    fetchCurrentUser,
    refreshAccessToken,
    updateProfile,
    logout,
    sendCode,
    checkSetupStatus,
  }
})