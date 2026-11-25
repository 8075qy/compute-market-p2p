<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Button, Input, Card, Icon } from '@/components/ui'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const authStore = useAuthStore()
const { success, danger } = useToast()

const loginForm = reactive({
  account: '',
  password: '',
})

const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  nickname: '',
})

const isRegister = ref(false)
const isLoading = ref(false)
const showPassword = ref(false)

const usernameError = computed(() => {
  if (!isRegister.value) return ''
  const username = registerForm.username
  if (!username) return ''
  if (username.length < 3) return '用户名至少3位'
  return ''
})

const passwordError = computed(() => {
  const password = isRegister.value ? registerForm.password : loginForm.password
  if (isRegister.value && password && password.length < 8) return '密码至少8位'
  return ''
})

const confirmPasswordError = computed(() => {
  if (!isRegister.value) return ''
  if (registerForm.confirmPassword && registerForm.confirmPassword !== registerForm.password) return '两次输入不一致'
  return ''
})

const canSubmit = computed(() => {
  if (isRegister.value) {
    return registerForm.username && registerForm.password && registerForm.confirmPassword && !usernameError.value && !passwordError.value && !confirmPasswordError.value
  }
  return loginForm.account && loginForm.password && !passwordError.value
})

async function handleLogin() {
  if (!canSubmit.value || isLoading.value) return
  isLoading.value = true
  try {
    await authStore.login(loginForm.account, loginForm.password)
    success('登录成功')
    router.replace('/')
  } catch (error: any) {
    danger(error.response?.data?.message || '登录失败')
  } finally {
    isLoading.value = false
  }
}

async function handleRegister() {
  if (!canSubmit.value || isLoading.value) return
  isLoading.value = true
  try {
    await authStore.register({
      username: registerForm.username,
      password: registerForm.password,
      nickname: registerForm.nickname || undefined,
    })
    success('注册成功')
    router.replace('/')
  } catch (error: any) {
    danger(error.response?.data?.message || '注册失败')
  } finally {
    isLoading.value = false
  }
}

function toggleMode() {
  isRegister.value = !isRegister.value
  loginForm.account = ''
  loginForm.password = ''
  registerForm.username = ''
  registerForm.password = ''
  registerForm.confirmPassword = ''
  registerForm.nickname = ''
}
</script>

<template>
  <div class="auth">
    <div class="auth-bg" aria-hidden="true"></div>

    <div class="auth-inner">
      <header class="brand">
        <div class="brand-logo">
          <Icon name="network" class="brand-icon" />
        </div>
        <h1 class="brand-title">算力共享中心</h1>
        <p class="brand-sub">P2P · DECENTRALIZED GPU NETWORK</p>
        <div class="brand-tags">
          <span class="tag"><Icon name="zap" class="tag-icon" />闲置算力共享</span>
          <span class="tag"><Icon name="cpu" class="tag-icon" />按需调度</span>
          <span class="tag"><Icon name="globe" class="tag-icon" />去中心化</span>
        </div>
      </header>

      <Card class="auth-card" :hoverable="false">
        <div class="seg" role="tablist">
          <button
            type="button"
            class="seg-btn"
            :class="{ active: !isRegister }"
            role="tab"
            :aria-selected="!isRegister"
            @click="isRegister && toggleMode()"
          >
            登录
          </button>
          <button
            type="button"
            class="seg-btn"
            :class="{ active: isRegister }"
            role="tab"
            :aria-selected="isRegister"
            @click="!isRegister && toggleMode()"
          >
            注册
          </button>
        </div>

        <form @submit.prevent="isRegister ? handleRegister() : handleLogin()">
          <div v-if="!isRegister" class="form">
            <Input
              v-model="loginForm.account"
              label="用户名 / 手机号 / 邮箱"
              placeholder="请输入用户名、手机号或邮箱"
              clearable
            />
            <Input
              v-model="loginForm.password"
              type="password"
              label="密码"
              placeholder="请输入密码"
              :error="passwordError"
              :clearable="true"
            />
            <div class="form-meta">
              <a href="#" class="link">忘记密码？</a>
            </div>
            <Button variant="primary" block :loading="isLoading" type="submit" :disabled="!canSubmit">
              进入算力网络
            </Button>
          </div>

          <div v-else class="form">
            <Input
              v-model="registerForm.nickname"
              label="昵称（可选）"
              placeholder="设置你的昵称"
            />

            <Input
              v-model="registerForm.username"
              label="用户名"
              placeholder="请输入用户名"
              :error="usernameError"
              clearable
            />

            <Input
              v-model="registerForm.password"
              type="password"
              label="密码"
              placeholder="至少8位字符"
              :error="passwordError"
              :clearable="true"
            />

            <Input
              v-model="registerForm.confirmPassword"
              type="password"
              label="确认密码"
              placeholder="再次输入密码"
              :error="confirmPasswordError"
              :clearable="true"
            />

            <Button variant="primary" block :loading="isLoading" type="submit" :disabled="!canSubmit">
              创建账户
            </Button>
          </div>
        </form>

        <p class="terms">注册/登录即表示同意《用户协议》和《隐私政策》</p>
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

/* 点阵网格背景，营造节点网络感 */
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

.brand-tags {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: var(--space-8);
  margin-top: var(--space-16);
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-10);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-pill);
}

.tag-icon {
  font-size: 12px;
  color: var(--color-primary);
}

.auth-card.card {
  background: var(--gradient-surface);
  border: 1px solid var(--color-line);
  box-shadow: var(--shadow-xl);
}

.seg {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  padding: var(--space-4);
  margin-bottom: var(--space-20);
  background: var(--color-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-lg);
}

.seg-btn {
  height: var(--btn-height-sm);
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: var(--text-sm);
  font-weight: 600;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.seg-btn.active {
  background: var(--gradient-primary);
  color: var(--color-primary-ink);
  box-shadow: var(--shadow-glow);
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-16);
}

.form-meta {
  display: flex;
  justify-content: flex-end;
  margin-top: calc(-1 * var(--space-8));
}

.link {
  font-size: var(--text-sm);
  color: var(--color-primary);
}

.terms {
  margin-top: var(--space-16);
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.footer {
  text-align: center;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}
</style>