<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  variant?: 'primary' | 'success' | 'warning' | 'danger' | 'muted'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
})

const classes = computed(() => ['badge', `badge-${props.variant}`])
</script>

<template>
  <span :class="classes"><slot /></span>
</template>

<style scoped>
/* 样式在 app.css 中定义 */
</style>