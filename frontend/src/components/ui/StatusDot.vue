<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  status: 'online' | 'offline' | 'maintenance'
  label?: string
}

const props = defineProps<Props>()

const classes = computed(() => ['status-dot', props.status])
</script>

<template>
  <span :class="classes">
    <span v-if="label">{{ label }}</span>
    <span v-else>
      <span v-if="status === 'online'">在线</span>
      <span v-else-if="status === 'offline'">离线</span>
      <span v-else>维护中</span>
    </span>
  </span>
</template>

<style scoped>
/* 样式在 app.css 中定义 */
</style>