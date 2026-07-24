<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '72px' : '236px'" class="layout__aside">
      <div class="logo" :class="{ 'is-small': collapsed }">
        <img class="logo__img" :src="`${publicBase}static/brand-logo.png`" width="40" height="40" alt="" />
        <div v-show="!collapsed" class="logo__text">
          <span class="logo__name">{{ shellTitle }}</span>
          <span class="logo__hint">Lemon Kami</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="true"
        :router="true"
        :unique-opened="true"
        class="side-menu"
      >
        <template v-for="item in menuItems" :key="item.index">
          <el-sub-menu v-if="item.children" :index="item.index">
            <template #title>
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.index" :index="child.index">
              <el-icon><component :is="child.icon" /></el-icon>
              <span>{{ child.label }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.index">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container class="layout__main">
      <el-header class="layout__header" height="64px">
        <div class="layout__header-left">
          <el-button
            :icon="collapsed ? Expand : Fold"
            text
            class="btn-fold"
            :aria-label="collapsed ? '展开' : '收起'"
            @click="collapsed = !collapsed"
          />
          <h4 class="page-title">{{ currentTitle }}</h4>
        </div>
        <div class="layout__header-right">
          <el-tag effect="plain" round>{{ roleLabel }}</el-tag>
          <el-button
            class="yz-no-burst"
            :icon="isDark ? Sunny : Moon"
            text
            circle
            :aria-label="isDark ? '切到浅色' : '切到暗色'"
            @click="themeStore.toggle()"
          />
          <el-dropdown trigger="click" @command="handleCommand">
            <span class="user-pill">
              <el-avatar :size="32" class="user-avatar">
                <el-icon><User /></el-icon>
              </el-avatar>
              <span class="user-name">{{ userStore.userInfo?.username || roleLabel }}</span>
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view v-slot="{ Component, route: childRoute }">
          <transition name="yz-page-fade" mode="out-in">
            <component :is="Component" :key="childRoute.path" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  ArrowDown,
  Box,
  Coin,
  Connection,
  CreditCard,
  DataAnalysis,
  Document,
  Expand,
  Fold,
  Key,
  Monitor,
  Moon,
  Setting,
  SwitchButton,
  Sunny,
  Tickets,
  User,
  UserFilled,
  Wallet
} from '@element-plus/icons-vue'
import { useThemeStore } from '../stores/theme'
import { useUserStore } from '../stores/user'

const publicBase = import.meta.env.BASE_URL
const route = useRoute()
const userStore = useUserStore()
const themeStore = useThemeStore()
const collapsed = ref(false)

const isMerchant = computed(() => userStore.role === 'merchant' || route.path.startsWith('/merchant'))
const shellTitle = computed(() => (isMerchant.value ? '商户控制台' : '商业版后台'))
const roleLabel = computed(() => (isMerchant.value ? '商户账号' : '管理员账号'))
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || shellTitle.value)
const isDark = computed(() => themeStore.isDark)

const adminMenuItems = [
  { index: '/admin/dashboard', label: '运营总览', icon: DataAnalysis },
  { index: '/admin/commercial/merchants', label: '发卡用户管理', icon: UserFilled },
  { index: '/admin/commercial/recharge-orders', label: '充值订单审核', icon: Tickets },
  { index: '/admin/commercial/recharge-settings', label: '充值配置', icon: CreditCard },
  { index: '/admin/commercial/quota-transactions', label: '发卡额度流水', icon: Coin },
  {
    index: '/admin/apps',
    label: '应用管理',
    icon: Setting,
    children: [
      { index: '/admin/apps/info', label: '应用信息', icon: Setting },
      { index: '/admin/apps/notices', label: '公告管理', icon: Document },
      { index: '/admin/apps/versions', label: '版本更新', icon: Tickets }
    ]
  },
  {
    index: '/admin/kamis',
    label: '卡密管理',
    icon: Key,
    children: [
      { index: '/admin/kamis/batches', label: '批次管理', icon: Box },
      { index: '/admin/kamis/list', label: '卡密列表', icon: Key }
    ]
  },
  { index: '/admin/devices', label: '设备管理', icon: Monitor },
  { index: '/admin/end-users', label: '使用用户管理', icon: User },
  { index: '/admin/users', label: '管理员账号管理', icon: UserFilled },
  { index: '/admin/logs', label: '审计日志', icon: Document },
  {
    index: '/admin/interfaces',
    label: '接口管理',
    icon: Connection,
    children: [
      { index: '/admin/interfaces/new', label: '新增接口', icon: Setting },
      { index: '/admin/interfaces/list', label: '接口列表', icon: Document }
    ]
  },
  { index: '/docs/api', label: '接口文档', icon: Document }
]

const merchantMenuItems = [
  { index: '/merchant/dashboard', label: '商户控制台', icon: DataAnalysis },
  { index: '/merchant/recharge', label: '充值发卡额度', icon: Wallet },
  { index: '/merchant/orders', label: '我的订单', icon: Tickets },
  { index: '/merchant/transactions', label: '发卡额度流水', icon: Coin },
  { index: '/merchant/apps', label: '我的应用', icon: Setting },
  { index: '/merchant/batches', label: '批次管理', icon: Box },
  { index: '/merchant/cards', label: '我的卡密', icon: Key },
  { index: '/merchant/devices', label: '设备记录', icon: Monitor },
  { index: '/merchant/account', label: '账号设置', icon: User }
]

const menuItems = computed(() => (isMerchant.value ? merchantMenuItems : adminMenuItems))

const handleCommand = (command) => {
  if (command === 'logout') userStore.logout()
}
</script>

<style scoped>
.layout {
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
}

.layout__aside {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.92);
  border-right: 1px solid #dbeafe;
  box-shadow: 10px 0 28px rgba(30, 64, 105, 0.08);
  transition: width 0.25s ease;
}

.logo {
  height: 64px;
  min-height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px 0 12px;
  border-bottom: 1px solid #dbeafe;
}

.logo.is-small {
  justify-content: center;
  padding: 0 6px;
}

.logo__img {
  border-radius: 12px;
  background: #fef9c3;
  box-shadow: 0 6px 16px rgba(202, 138, 4, 0.16);
  flex-shrink: 0;
}

.logo__text {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.logo__name {
  font-size: 17px;
  font-weight: 800;
  line-height: 1.2;
  color: #0f172a;
  white-space: nowrap;
}

.logo__hint {
  margin-top: 2px;
  font-size: 11px;
  color: #64748b;
}

:deep(.side-menu) {
  flex: 1;
  border-right: none;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #475569;
  --el-menu-active-color: #2f80ed;
  --el-menu-hover-bg-color: #eff6ff;
  padding: 8px 10px 24px;
}

:deep(.side-menu .el-menu-item),
:deep(.side-menu .el-sub-menu__title) {
  height: 44px;
  border-radius: 8px;
  margin: 3px 0;
}

:deep(.side-menu .el-menu-item.is-active) {
  background: #eaf4ff !important;
  color: #1d4ed8 !important;
  font-weight: 700;
  box-shadow: inset 3px 0 0 #2f80ed;
}

.layout__main {
  min-width: 0;
  height: 100%;
}

.layout__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px 0 8px;
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid #e2e8f0;
  backdrop-filter: blur(10px);
}

.layout__header-left,
.layout__header-right,
.user-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.btn-fold {
  font-size: 18px;
  border-radius: 8px;
}

.page-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-pill {
  padding: 6px 10px 6px 4px;
  border-radius: 8px;
  cursor: pointer;
  color: #0f172a;
  font-weight: 600;
}

.user-pill:hover {
  background: #f1f5f9;
}

.user-avatar {
  background: linear-gradient(135deg, #2f80ed, #38bdf8) !important;
}

.user-name {
  max-width: 128px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main-content {
  height: calc(100vh - 64px);
  overflow: auto;
  padding: 20px 24px 28px;
  background: linear-gradient(160deg, #eaf6ff 0%, #f8fbff 56%, #ffffff 100%);
}

html.dark .layout__aside,
html.dark .layout__header {
  background: #111827;
  border-color: #334155;
}

html.dark .main-content {
  background: #0f172a;
}

html.dark .logo__name,
html.dark .page-title,
html.dark .user-pill {
  color: #e5e7eb;
}
</style>
