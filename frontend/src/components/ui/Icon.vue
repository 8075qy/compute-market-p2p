<script setup lang="ts">
interface Props {
  name: string
}

defineProps<Props>()
</script>

<template>
  <svg class="icon" aria-hidden="true" focusable="false">
    <use :href="`/src/assets/icons.svg#${name}`" />
  </svg>
</template>

<style scoped>
.icon {
  display: inline-flex;
  width: 1em;
  height: 1em;
  fill: currentColor;
}
</style>