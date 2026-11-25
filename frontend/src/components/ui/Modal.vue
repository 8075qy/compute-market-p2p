<script setup lang="ts">
import Icon from './Icon.vue'

interface Props {
  visible: boolean
  title?: string
  closeOnOverlay?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  closeOnOverlay: true,
})

const emit = defineEmits<{
  close: []
}>()

function handleOverlay() {
  if (props.closeOnOverlay) emit('close')
}
</script>

<template>
  <Transition name="fade">
    <div v-if="visible" class="modal-overlay" @click.self="handleOverlay">
      <div class="modal" role="dialog" aria-modal="true" :aria-label="title">
        <div class="modal-head">
          <h2 class="modal-title">{{ title }}</h2>
          <button type="button" class="modal-close" aria-label="关闭" @click="emit('close')">
            <Icon name="x" class="icon-md" />
          </button>
        </div>
        <div class="modal-body">
          <slot />
        </div>
        <div v-if="$slots.footer" class="modal-footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  z-index: var(--z-modal-backdrop);
  animation: fade-in 150ms ease-out forwards;
}

.modal {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: 85vh;
  background: var(--color-surface);
  border-top-left-radius: var(--radius-panel);
  border-top-right-radius: var(--radius-panel);
  box-shadow: var(--shadow-lg);
  z-index: var(--z-modal);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  padding: var(--space-16) var(--space-16) var(--space-12);
  border-bottom: 1px solid var(--color-line);
}

.modal-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}

.modal-close {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  color: var(--color-text-muted);
  background: transparent;
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast);
}

.modal-close:hover {
  color: var(--color-text);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-16);
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
}

.modal-footer {
  display: flex;
  gap: var(--space-8);
  padding: var(--space-12) var(--space-16) var(--space-16);
  border-top: 1px solid var(--color-line);
}

.modal-footer > * {
  flex: 1;
}

@media (min-width: 768px) {
  .modal-overlay {
    align-items: center;
  }

  .modal {
    width: 480px;
    max-width: calc(100% - var(--space-32));
    border-radius: var(--radius-panel);
  }
}
</style>