import { createRouter, createWebHistory } from 'vue-router'

const adminChildren = [
  { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '运营总览' } },
  { path: 'commercial', name: 'AdminCommercialOverview', component: () => import('../views/AdminCommercialOverview.vue'), meta: { title: '商业版后台' } },
  { path: 'commercial/recharge-orders', name: 'AdminRechargeOrders', component: () => import('../views/AdminRechargeOrders.vue'), meta: { title: '充值订单' } },
  { path: 'commercial/recharge-settings', name: 'AdminRechargeSettings', component: () => import('../views/AdminRechargeSettings.vue'), meta: { title: '充值配置' } },
  { path: 'commercial/merchants', name: 'AdminMerchants', component: () => import('../views/AdminMerchants.vue'), meta: { title: '发卡用户管理' } },
  { path: 'commercial/quota-transactions', name: 'AdminQuotaTransactions', component: () => import('../views/AdminQuotaTransactions.vue'), meta: { title: '发卡额度流水' } },
  { path: 'apps', redirect: '/admin/apps/info' },
  { path: 'apps/info', name: 'Apps', component: () => import('../views/Apps.vue'), meta: { title: '应用信息' } },
  { path: 'apps/notices', name: 'AppNotices', component: () => import('../views/AppNotices.vue'), meta: { title: '公告管理' } },
  { path: 'apps/versions', name: 'AppVersions', component: () => import('../views/AppVersions.vue'), meta: { title: '版本更新' } },
  { path: 'apps/:app_id/interfaces', name: 'AppInterfaces', component: () => import('../views/AppInterfaces.vue'), meta: { title: '应用接口列表' } },
  { path: 'kamis', redirect: '/admin/kamis/batches' },
  { path: 'kamis/batches', name: 'KamiBatches', component: () => import('../views/KamiBatches.vue'), meta: { title: '批次管理' } },
  { path: 'kamis/list', name: 'Kamis', component: () => import('../views/Kamis.vue'), meta: { title: '卡密列表' } },
  { path: 'devices', name: 'Devices', component: () => import('../views/Devices.vue'), meta: { title: '设备管理' } },
  { path: 'logs', name: 'Logs', component: () => import('../views/EventLogs.vue'), meta: { title: '事件日志' } },
  { path: 'users', name: 'Users', component: () => import('../views/Users.vue'), meta: { title: '账号管理' } },
  { path: 'end-users', name: 'EndUsers', component: () => import('../views/EndUsers.vue'), meta: { title: '用户管理' } },
  { path: 'interfaces/new', name: 'InterfaceCreate', component: () => import('../views/InterfaceCreate.vue'), meta: { title: '新增接口' } },
  { path: 'interfaces/list', name: 'InterfaceList', component: () => import('../views/InterfaceList.vue'), meta: { title: '接口列表' } }
]

const merchantChildren = [
  { path: 'dashboard', name: 'MerchantDashboard', component: () => import('../views/MerchantDashboard.vue'), meta: { title: '商户控制台' } },
  { path: 'recharge', name: 'MerchantRecharge', component: () => import('../views/MerchantRecharge.vue'), meta: { title: '充值发卡额度' } },
  { path: 'orders', name: 'MerchantOrders', component: () => import('../views/MerchantOrders.vue'), meta: { title: '我的订单' } },
  { path: 'transactions', name: 'MerchantTransactions', component: () => import('../views/MerchantTransactions.vue'), meta: { title: '发卡额度流水' } },
  { path: 'apps', name: 'MerchantApps', component: () => import('../views/MerchantApps.vue'), meta: { title: '我的应用' } },
  { path: 'batches', name: 'MerchantBatches', component: () => import('../views/MerchantBatches.vue'), meta: { title: '批次管理' } },
  { path: 'cards', name: 'MerchantCards', component: () => import('../views/MerchantCards.vue'), meta: { title: '我的卡密' } },
  { path: 'devices', name: 'MerchantDevices', component: () => import('../views/Devices.vue'), meta: { title: '设备记录' } },
  { path: 'account', name: 'MerchantAccount', component: () => import('../views/MerchantDashboard.vue'), meta: { title: '账号设置' } }
]

const legacyAdminRedirects = [
  'dashboard',
  'apps/info',
  'apps/notices',
  'apps/versions',
  'kamis/batches',
  'kamis/list',
  'devices',
  'logs',
  'users',
  'end-users',
  'interfaces/new',
  'interfaces/list'
].map((path) => ({
  path: `/${path}`,
  redirect: `/admin/${path}`
}))

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
    redirect: () => (localStorage.getItem('role') === 'merchant' ? '/merchant/dashboard' : '/admin/dashboard')
  },
  {
    path: '/admin',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/admin/dashboard',
    meta: { requiresAuth: true, role: 'admin' },
    children: adminChildren
  },
  {
    path: '/merchant',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/merchant/dashboard',
    meta: { requiresAuth: true, role: 'merchant' },
    children: merchantChildren
  },
  ...legacyAdminRedirects,
  { path: '/apps', redirect: '/admin/apps/info' },
  { path: '/kamis', redirect: '/admin/kamis/batches' },
  { path: '/:pathMatch(.*)*', redirect: '/404' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role') || 'admin'

  if (to.meta.requiresAuth && !token) {
    return '/login'
  }
  if (to.path === '/login' && token) {
    return role === 'merchant' ? '/merchant/dashboard' : '/admin/dashboard'
  }
  if (to.path.startsWith('/admin') && role === 'merchant') {
    return '/merchant/dashboard'
  }
  if (to.path.startsWith('/merchant') && role !== 'merchant') {
    return '/admin/dashboard'
  }
  return true
})

export default router
