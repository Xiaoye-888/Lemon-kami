import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/docs/api',
    name: 'StandaloneApiDocs',
    component: () => import('../views/ApiDocs.vue'),
    meta: { requiresAuth: false, title: '接口文档' }
  },
  {
    path: '/interface-docs',
    redirect: (to) => ({
      path: '/docs/api',
      query: to.query,
      hash: to.hash
    })
  },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/apps',
    meta: { requiresAuth: true },
    children: [
      { path: 'apps', name: 'Apps', component: () => import('../views/Apps.vue'), meta: { title: '应用管理' } },
      {
        path: 'apps/:app_id/interfaces',
        name: 'AppInterfaces',
        component: () => import('../views/AppInterfaces.vue'),
        meta: { title: '应用接口列表' }
      },
      { path: 'kamis', redirect: '/kamis/batches' },
      {
        path: 'kamis/batches',
        name: 'KamiBatches',
        component: () => import('../views/KamiBatches.vue'),
        meta: { title: '批次管理' }
      },
      {
        path: 'kamis/list',
        name: 'Kamis',
        component: () => import('../views/Kamis.vue'),
        meta: { title: '卡密列表' }
      },
      { path: 'devices', name: 'Devices', component: () => import('../views/Devices.vue'), meta: { title: '设备管理' } },
      { path: 'logs', name: 'Logs', component: () => import('../views/EventLogs.vue'), meta: { title: '事件日志' } },
      { path: 'users', name: 'Users', component: () => import('../views/Users.vue'), meta: { title: '账号管理' } },
      { path: 'end-users', name: 'EndUsers', component: () => import('../views/EndUsers.vue'), meta: { title: '用户授权' } },
      {
        path: 'interfaces/new',
        name: 'InterfaceCreate',
        component: () => import('../views/InterfaceCreate.vue'),
        meta: { title: '新增接口' }
      },
      {
        path: 'interfaces/list',
        name: 'InterfaceList',
        component: () => import('../views/InterfaceList.vue'),
        meta: { title: '接口列表' }
      },
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/404' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')

  if (to.meta.requiresAuth && !token) {
    return '/login'
  }
  if (to.path === '/login' && token) {
    return '/'
  }
  return true
})

export default router
