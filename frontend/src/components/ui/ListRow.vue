<script setup lang="ts">
import Badge from './Badge.vue'
import Icon from './Icon.vue'

interface Props {
  title: string
  subtitle?: string
  meta?: string
  metaLabel?: string
  status?: 'online' | 'offline' | 'maintenance'
  badge?: string
  badgeVariant?: 'primary' | 'success' | 'warning' | 'danger' | 'muted'
  rightIcon?: string
  onClick?: () => void
}

const props = defineProps<Props>()
</script>

<template>
  <div
    class="list-row"
    :class="{ clickable: onClick }"
    @click="onClick"
    role="button"
    tabindex="0"
    @keydown.enter="onClick"
    @keydown.space.prevent="onClick"
  >
    <div class="list-row-content">
      <div class="list-row-header">
        <h4 class="list-row-title">{{ title }}</h4>
        <Badge v-if="badge" :variant="badgeVariant">{{ badge }}</Badge>
      </div>
      <p v-if="subtitle" class="list-row-subtitle">{{ subtitle }}</p>
    </div>
    <div class="list-row-meta">
      <StatusDot v-if="status" :status="status" />
      <span v-else-if="meta" class="list-row-stat">{{ meta }}</span>
      <span v-if="metaLabel" class="list-row-time">{{ metaLabel }}</span>
    </div>
    <Icon v-if="rightIcon" :name="rightIcon" class="icon-md" style="margin-left: var(--space-12); color: var(--color-text-muted);" />
  </div>
</template>

<style scoped>
.list-row.clickable {
  cursor: pointer;
}

.list-row-header {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}
</style>