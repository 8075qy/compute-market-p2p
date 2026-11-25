<script setup lang="ts">
interface Props {
  modelValue: boolean
  disabled?: boolean
  size?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  size: 'md',
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

function toggle() {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
}
</script>

<template>
  <label class="switch" @click="toggle" :class="{ 'switch-disabled': disabled }">
    <input
      type="checkbox"
      class="switch-input"
      :checked="modelValue"
      :disabled="disabled"
      @change.stop
    />
    <span class="switch-track" :class="{ 'switch-track-checked': modelValue }" />
    <span class="switch-thumb" :class="{ 'switch-thumb-checked': modelValue }" />
  </label>
</template>

<style scoped>
.switch {
  position: relative;
  display: inline-flex;
  width: 48px;
  height: 28px;
  flex-shrink: 0;
  cursor: pointer;
}

.switch-disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.switch-input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}

.switch-track {
  position: absolute;
  inset: 0;
  background: var(--color-line);
  border-radius: var(--radius-pill);
  transition: background var(--transition-normal);
}

.switch-track-checked {
  background: var(--color-primary);
}

.switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 24px;
  height: 24px;
  background: white;
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
  transition: transform var(--transition-normal);
  display: flex;
  align-items: center;
  justify-content: center;
}

.switch-thumb-checked {
  transform: translateX(20px);
}
</style>