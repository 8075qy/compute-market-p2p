<script setup lang="ts">
interface Props {
  hoverable?: boolean
  padded?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  hoverable: true,
  padded: true,
})
</script>

<template>
  <div class="card" :class="{ 'card-hoverable': hoverable, 'card-padded': padded }">
    <slot />
  </div>
</template>

<style scoped>
.card-padded {
  padding: var(--space-16);
}

.card-hoverable:hover {
  border-color: var(--color-line-hover);
  box-shadow: var(--shadow-sm);
}

.card-hoverable:active {
  transform: scale(0.995);
  background: var(--color-surface-hover);
}
</style>