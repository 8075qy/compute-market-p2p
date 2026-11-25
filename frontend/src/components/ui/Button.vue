<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  variant?: 'primary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  block?: boolean
  loading?: boolean
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  block: false,
  loading: false,
  disabled: false,
  type: 'button',
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const classes = computed(() => [
  'btn',
  `btn-${props.variant}`,
  `btn-${props.size}`,
  { 'btn-block': props.block, 'btn-loading': props.loading },
])
</script>

<template>
  <button
    :class="classes"
    :type="type"
    :disabled="disabled || loading"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>

<style scoped>
/* 样式在 app.css 中定义 */
</style>