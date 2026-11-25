<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Button, Input, Card, Icon } from '@/components/ui'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const authStore = useAuthStore()
const { success, danger } = useToast()

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  nickname: '',
})

const isLoading = ref(false)

const usernameError = computed(() => {
  if (!form.username) return ''
  if (form.username.length < 3) return '用户名至少3位'
  return ''
})

const passwordError = computed(() => {
  if (!form.password) return ''
  if (form.password.length < 8) return '密码至少8位'
  return ''
})

const confirmPasswordError = computed(() => {
  if (!form.confirmPassword) return ''
  if (form.confirmPassword !== form.password) return '两次输入不一致'
  return ''
})

const canSubmit = computed(() => {
  return form.username && form.password && form.confirmPassword &&
    !usernameError.value && !passwordError.value && !confirmPasswordError.value
})

async function handleSubmit() {
  if (!canSubmit.value || isLoading.value) return
  isLoading.value = true
  try {
    await authStore.setupAdmin(form.username, form.password, form.nickname || undefined)
    success('管理员初始化成功')
    router.replace('/')
  } catch (error: any) {
    danger(error.response?.data?.message || '初始化失败')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="auth">
    <div class="auth-bg" aria-hidden="true"></div>

    <div class="auth-inner">
      <header class="brand">
        <div class="brand-logo">
          <Icon name="lock" class="brand-icon" />
        </div>
        <h1 class="brand-title">初始化管理员</h1>
        <p class="brand-sub">FIRST-RUN SETUP · ADMIN ACCOUNT</p>
        <p class="brand-desc">首次部署需设置管理员用户名与密码，完成后即可进入平台管理</p>
      </header>

      <Card class="auth-card" :hoverable="false">
        <form @submit.prevent="handleSubmit">
          <div class="form">
            <Input
              v-model="form.username"
              label="管理员用户名"
              placeholder="设置登录用户名"
              :error="usernameError"
              clearable
            />

            <Input
              v-model="form.password"
              type="password"
              label="密码"
              placeholder="至少8位字符"
              :error="passwordError"
              :clearable="true"
            />

            <Input
              v-model="form.confirmPassword"
              type="password"
              label="确认密码"
              placeholder="再次输入密码"
              :error="confirmPasswordError"
              :clearable="true"
            />

            <Input
              v-model="form.nickname"
              label="昵称（可选）"
              placeholder="设置你的昵称"
            />

            <Button variant="primary" block :loading="isLoading" type="submit" :disabled="!canSubmit">
              完成初始化
            </Button>
          </div>
        </form>
      </Card>

      <p class="footer">算力共享中心 · P2P 去中心化网络</p>
    </div>
  </div>
</template>

<style scoped>
.auth {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-24) var(--space-16) calc(var(--space-24) + env(safe-area-inset-bottom));
  overflow: hidden;
}

.auth-bg {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(rgba(34, 211, 238, 0.10) 1px, transparent 1px),
    radial-gradient(rgba(139, 92, 246, 0.08) 1px, transparent 1px);
  background-size: 24px 24px, 48px 48px;
  background-position: 0 0, 12px 12px;
  -webkit-mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 30%, transparent 78%);
  mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 30%, transparent 78%);
  pointer-events: none;
}

.auth-inner {
  position: relative;
  width: 100%;
  max-width: 380px;
  display: flex;
  flex-direction: column;
  gap: var(--space-24);
}

.brand {
  text-align: center;
}

.brand-logo {
  width: 72px;
  height: 72px;
  margin: 0 auto var(--space-16);
  border-radius: var(--radius-2xl);
  background: var(--gradient-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-glow-mixed);
}

.brand-icon {
  font-size: 36px;
  color: var(--color-primary-ink);
}

.brand-title {
  font-size: var(--text-3xl);
  font-weight: 700;
  letter-spacing: 0.01em;
  color: var(--color-text);
}

.brand-sub {
  margin-top: var(--space-8);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  letter-spacing: 0.12em;
}

.brand-desc {
  margin-top: var(--space-12);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.auth-card.card {
  background: var(--gradient-surface);
  border: 1px solid var(--color-line);
  box-shadow: var(--shadow-xl);
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-16);
  padding: var(--space-4);
}

.footer {
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
</style>