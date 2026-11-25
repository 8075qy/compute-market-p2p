<script setup lang="ts">
import { ref, computed } from 'vue'
import Icon from './Icon.vue'

interface ActionSheetItem {
  label: string
  action: () => void
  danger?: boolean
  disabled?: boolean
}

const visible = ref(false)
const title = ref('')
const items = ref<ActionSheetItem[]>([])
const cancelText = ref('取消')

function open(options: { title: string; items: ActionSheetItem[]; cancelText?: string }) {
  title.value = options.title
  items.value = options.items
  cancelText.value = options.cancelText || '取消'
  visible.value = true
}

function close() {
  visible.value = false
}

function handleItem(item: ActionSheetItem) {
  if (item.disabled) return
  item.action()
  close()
}
</script>

<template>
  <Transition name="fade">
    <div v-if="visible" class="action-sheet-overlay" @click="close" aria-hidden="true" />
  </Transition>

  <Transition name="slide-up">
    <div v-if="visible" class="action-sheet" role="dialog" aria-modal="true" aria-labelledby="action-sheet-title">
      <div class="action-sheet-handle" />
      <h2 id="action-sheet-title" class="action-sheet-title">{{ title }}</h2>
      <div class="action-sheet-content">
        <button
          v-for="(item, index) in items"
          :key="index"
          class="action-sheet-item"
          :class="{ danger: item.danger, disabled: item.disabled }"
          @click="handleItem(item)"
          :disabled="item.disabled"
        >
          <span>{{ item.label }}</span>
          <Icon v-if="item.danger" name="alert-circle" class="icon-sm" />
        </button>
      </div>
      <button class="action-sheet-cancel" @click="close">{{ cancelText }}</button>
    </div>
  </Transition>
</template>

<style scoped>
.action-sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 200;
  animation: fade-in 150ms ease-out forwards;
}

.action-sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--color-surface);
  border-top-left-radius: var(--radius-panel);
  border-top-right-radius: var(--radius-panel);
  box-shadow: var(--shadow-md);
  z-index: 201;
  animation: slide-up 200ms ease-out forwards;
  max-height: 80vh;
  overflow-y: auto;
}

.action-sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--color-line);
  border-radius: 2px;
  margin: var(--space-12) auto;
}

.action-sheet-title {
  padding: 0 var(--space-16) var(--space-12);
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-line);
}

.action-sheet-content {
  padding: var(--space-8) 0;
}

.action-sheet-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: var(--space-12) var(--space-16);
  font-size: var(--text-base);
  color: var(--color-text);
  border-bottom: 1px solid var(--color-line);
  text-align: left;
  transition: background var(--transition-fast);
}

.action-sheet-item:last-child {
  border-bottom: none;
}

.action-sheet-item:active:not(.disabled) {
  background: var(--color-surface-hover);
}

.action-sheet-item.danger {
  color: var(--color-danger);
}

.action-sheet-item.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.action-sheet-cancel {
  margin: var(--space-8) var(--space-16) var(--space-16);
  padding: var(--space-16);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--color-text);
  background: var(--color-bg);
  border-radius: var(--radius-card);
  width: 100%;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 150ms ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 200ms ease-out;
}

.slide-up-enter-from {
  transform: translateY(100%);
}

.slide-up-leave-to {
  transform: translateY(100%);
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slide-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
</style>