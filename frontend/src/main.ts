import './utils/uni'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

// 全局样式
import './styles/global.css'
import './styles/tokens.css'
import './styles/app.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// 初始化 auth store
import { useAuthStore } from './stores/auth'
const authStore = useAuthStore()
authStore.loadFromStorage()

// 提供 toast
import { provideToast } from './composables/useToast'
// toast 实例将在 ToastContainer 挂载时提供

app.mount('#app')