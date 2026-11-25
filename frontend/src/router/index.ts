import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/pages/login/index.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/setup',
      name: 'setup',
      component: () => import('@/pages/setup/index.vue'),
      meta: { public: true, title: '初始化管理员' },
    },
    {
      path: '/',
      name: 'home',
      component: () => import('@/pages/home/index.vue'),
      meta: { requiresAuth: true, title: '首页' },
    },
    {
      path: '/supplier/nodes',
      name: 'supplier-nodes',
      component: () => import('@/pages/supplier-nodes/index.vue'),
      meta: { requiresAuth: true, title: '我的节点' },
    },
    {
      path: '/supplier/nodes/add',
      name: 'supplier-nodes-add',
      component: () => import('@/pages/supplier-nodes-add/index.vue'),
      meta: { requiresAuth: true, title: '添加节点' },
    },
    {
      path: '/supplier/nodes/:id',
      name: 'supplier-node-detail',
      component: () => import('@/pages/supplier-node-detail/index.vue'),
      meta: { requiresAuth: true, title: '节点详情' },
    },
    {
      path: '/supplier/nodes/:id/edit',
      name: 'supplier-node-edit',
      component: () => import('@/pages/supplier-node-edit/index.vue'),
      meta: { requiresAuth: true, title: '编辑节点' },
    },
    {
      path: '/supplier/nodes/:id/executions',
      name: 'supplier-node-executions',
      component: () => import('@/pages/supplier-node-executions/index.vue'),
      meta: { requiresAuth: true, title: '执行记录' },
    },
    {
      path: '/supplier/earnings',
      name: 'supplier-earnings',
      component: () => import('@/pages/supplier-earnings/index.vue'),
      meta: { requiresAuth: true, title: '收益明细' },
    },
    {
      path: '/demand/publish',
      name: 'demand-publish',
      component: () => import('@/pages/demand-publish/index.vue'),
      meta: { requiresAuth: true, title: '发布任务' },
    },
    {
      path: '/demand/tasks',
      name: 'demand-tasks',
      component: () => import('@/pages/demand-tasks/index.vue'),
      meta: { requiresAuth: true, title: '我的任务' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/pages/admin/index.vue'),
      meta: { requiresAuth: true, role: 'admin', title: '平台管理' },
    },
    {
      path: '/admin/nodes',
      name: 'admin-nodes',
      component: () => import('@/pages/admin/nodes/index.vue'),
      meta: { requiresAuth: true, role: 'admin', title: '节点管理' },
    },
    {
      path: '/admin/tasks',
      name: 'admin-tasks',
      component: () => import('@/pages/admin/tasks/index.vue'),
      meta: { requiresAuth: true, role: 'admin', title: '任务管理' },
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('@/pages/admin/users/index.vue'),
      meta: { requiresAuth: true, role: 'admin', title: '用户管理' },
    },
    {
      path: '/admin/audit',
      name: 'admin-audit',
      component: () => import('@/pages/admin/audit/index.vue'),
      meta: { requiresAuth: true, role: 'admin', title: '审计日志' },
    },
    {
      path: '/admin/config',
      name: 'admin-config',
      component: () => import('@/pages/admin/config/index.vue'),
      meta: { requiresAuth: true, role: 'admin', title: '平台配置' },
    },
    {
      path: '/task/:id',
      name: 'task-detail',
      component: () => import('@/pages/task-detail/index.vue'),
      meta: { requiresAuth: true, title: '任务详情' },
    },
    {
      path: '/settlement',
      name: 'settlement',
      component: () => import('@/pages/settlement/index.vue'),
      meta: { requiresAuth: true, title: '结算明细' },
    },
    {
      path: '/reserve-bank',
      name: 'reserve-bank',
      component: () => import('@/pages/reserve-bank/index.vue'),
      meta: { requiresAuth: true, title: '算力时间银行' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/pages/settings/index.vue'),
      meta: { requiresAuth: true, title: '设置' },
    },
    {
      path: '/notifications',
      name: 'notifications',
      component: () => import('@/pages/notifications/index.vue'),
      meta: { requiresAuth: true, title: '消息通知' },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // 首次部署：尚无管理员时强制进入初始化流程
  const needSetup = await authStore.checkSetupStatus()

  if (needSetup) {
    if (to.name === 'setup') {
      next()
    } else {
      next('/setup')
    }
    return
  }

  if (to.name === 'setup') {
    next('/login')
    return
  }

  if (!authStore.isAuthenticated) {
    await authStore.loadFromStorage()
  }

  if (to.meta.public) {
    if (authStore.isAuthenticated) {
      next('/')
    } else {
      next()
    }
    return
  }

  if (!authStore.isAuthenticated) {
    next('/login')
    return
  }

  if (to.meta.role === 'admin' && !authStore.isAdmin) {
    next('/')
    return
  }

  next()
})

export default router