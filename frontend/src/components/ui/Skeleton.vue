<script setup lang="ts">
interface Props {
  type?: 'text' | 'avatar' | 'card' | 'rect'
  width?: string | number
  height?: string | number
  lines?: number
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  width: '100%',
  height: 'auto',
  lines: 1,
})
</script>

<template>
  <div
    v-if="type === 'text'"
    class="skeleton skeleton-text"
    :style="{ width, height: height === 'auto' ? '16px' : height }"
    :aria-hidden="true"
  />
  <div
    v-else-if="type === 'avatar'"
    class="skeleton skeleton-avatar"
    :style="{ width, height }"
    :aria-hidden="true"
  />
  <div
    v-else-if="type === 'card'"
    class="skeleton skeleton-card"
    :style="{ width, height }"
    :aria-hidden="true"
  >
    <div class="skeleton skeleton-text" style="width: 60%; height: 20px; margin-bottom: 12px;" />
    <div class="skeleton skeleton-text" style="width: 40%; height: 14px; margin-bottom: 8px;" />
    <div class="skeleton skeleton-text" style="width: 80%; height: 14px;" />
  </div>
  <div
    v-else
    class="skeleton"
    :style="{ width, height }"
    :aria-hidden="true"
  />
</template>

<style scoped>
/* 样式在 app.css 中定义 */
</style>