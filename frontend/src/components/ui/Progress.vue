<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  value: number
  max?: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  variant?: 'default' | 'success' | 'warning' | 'danger'
}

const props = withDefaults(defineProps<Props>(), {
  max: 100,
  size: 'md',
  showLabel: false,
  variant: 'default',
})

const percentage = computed(() => Math.min(Math.max((props.value / props.max) * 100, 0), 100))

const barClasses = computed(() => ['progress-bar', { [`progress-bar-${props.variant}`]: props.variant !== 'default' }])
</script>

<template>
  <div class="progress" :class="{ 'progress-lg': size === 'lg' }" role="progressbar" :aria-valuenow="value" :aria-valuemin="0" :aria-valuemax="max">
    <div :class="barClasses" :style="{ width: `${percentage}%` }" />
  </div>
  <span v-if="showLabel" class="text-xs" style="margin-top: 4px; color: var(--color-text-muted);">
    {{ Math.round(percentage) }}%
  </span>
</template>

<style scoped>
/* 样式在 app.css 中定义 */
</style>