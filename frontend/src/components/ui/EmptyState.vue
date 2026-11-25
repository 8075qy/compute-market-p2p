<script setup lang="ts">
import Icon from './Icon.vue'
import Button from './Button.vue'

interface Props {
  icon?: string
  title: string
  description?: string
  actionLabel?: string
  action?: () => void
}

const props = defineProps<Props>()
</script>

<template>
  <div class="empty-state">
    <Icon v-if="icon" :name="icon" class="empty-state-icon" aria-hidden="true" />
    <h3 class="empty-state-title">{{ title }}</h3>
    <p v-if="description" class="empty-state-desc">{{ description }}</p>
    <Button v-if="actionLabel && action" variant="primary" @click="action">{{ actionLabel }}</Button>
  </div>
</template>

<style scoped>
/* 样式在 app.css 中定义 */
</style>