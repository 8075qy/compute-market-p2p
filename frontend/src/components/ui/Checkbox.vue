<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  modelValue: (string | number)[]
  value: string | number
  label: string
  description?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: (string | number)[]]
}>()

const checked = computed(() => props.modelValue.includes(props.value))

function handleClick() {
  if (props.disabled) return
  const newValue = checked.value
    ? props.modelValue.filter(v => v !== props.value)
    : [...props.modelValue, props.value]
  emit('update:modelValue', newValue)
}
</script>

<template>
  <label class="checkbox-item" @click="handleClick" :class="{ disabled: disabled, checked }">
    <input
      type="checkbox"
      class="checkbox-input"
      :checked="checked"
      :disabled="disabled"
      @change.stop
    />
    <div class="radio-content">
      <span class="radio-label">{{ label }}</span>
      <span v-if="description" class="radio-desc">{{ description }}</span>
    </div>
  </label>
</template>

<style scoped>
/* 样式在 app.css 中定义 */
</style>