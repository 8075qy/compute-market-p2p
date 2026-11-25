<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotificationSocket } from '@/composables/useNotificationSocket'
import Navbar from '@/components/layout/Navbar.vue'
import Tabbar from '@/components/layout/Tabbar.vue'
import ToastContainer from '@/components/ui/ToastContainer.vue'
import ActionSheet from '@/components/ui/ActionSheet.vue'

const router = useRouter()
const authStore = useAuthStore()

onMounted(() => {
  authStore.loadFromStorage()
})

useNotificationSocket()

function getCurrentRoute() {
  return router.currentRoute.value
}
</script>

<template>
  <div id="app">
    <Navbar v-if="!getCurrentRoute().meta.public" />
    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
    <Tabbar v-if="!getCurrentRoute().meta.public" />
    <ToastContainer />
    <ActionSheet />
  </div>
</template>

<style scoped>
#app {
  min-height: 100vh;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>