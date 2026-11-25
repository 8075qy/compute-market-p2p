<script setup lang="ts">
import { ref, computed } from 'vue'
import Icon from './Icon.vue'
import { provideToast } from '@/composables/useToast'

interface Toast {
  id: number
  type: 'success' | 'warning' | 'danger' | 'info'
  message: string
  duration?: number
}

const toasts = ref<Toast[]>([])
let toastId = 0

function show(message: string, type: Toast['type'] = 'info', duration = 3000) {
  const id = ++toastId
  toasts.value.push({ id, type, message, duration })

  if (duration > 0) {
    setTimeout(() => remove(id), duration)
  }

  return id
}

function remove(id: number) {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index !== -1) {
    toasts.value.splice(index, 1)
  }
}

function success(message: string, duration?: number) {
  return show(message, 'success', duration)
}

function warning(message: string, duration?: number) {
  return show(message, 'warning', duration)
}

function danger(message: string, duration?: number) {
  return show(message, 'danger', duration)
}

function info(message: string, duration?: number) {
  return show(message, 'info', duration)
}

const icons = computed(() => ({
  success: 'circle-check',
  warning: 'alert-triangle',
  danger: 'alert-circle',
  info: 'info',
}))

provideToast({ success, warning, danger, info })
</script>

<template>
  <div class="toast-container" aria-live="polite" aria-atomic="true">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      class="toast"
      :class="toast.type"
    >
      <Icon :name="icons[toast.type]" class="toast-icon" />
      <span class="toast-message">{{ toast.message }}</span>
    </div>
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: calc(var(--header-height) + var(--space-16));
  left: var(--space-16);
  right: var(--space-16);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  padding: var(--space-12) var(--space-16);
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-md);
  animation: toast-in 180ms ease-out forwards;
  pointer-events: auto;
}

.toast.success .toast-icon { color: var(--color-success); }
.toast.warning .toast-icon { color: var(--color-warning); }
.toast.danger .toast-icon { color: var(--color-danger); }
.toast.info .toast-icon { color: var(--color-primary); }

.toast-message {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--color-text);
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateY(-100%);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>