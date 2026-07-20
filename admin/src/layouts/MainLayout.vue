<template>
  <el-container class="layout">
    <el-aside
      :width="collapsed ? '72px' : '228px'"
      :class="['layout__aside', { 'is-collapsed': collapsed }]"
    >
      <div :class="['logo', { 'is-small': collapsed }]">
        <img class="logo__img" :src="`${publicBase}static/brand-logo.png`" width="40" height="40" alt="" />
        <div v-show="!collapsed" class="logo__text">
          <span class="logo__name">小柠檬网络验证</span>
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
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>运营总览</span>
        </el-menu-item>
        <el-sub-menu index="/apps">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>应用管理</span>
          </template>
          <el-menu-item index="/apps/info">
            <el-icon><Setting /></el-icon>
            <span>应用信息</span>
          </el-menu-item>
          <el-menu-item index="/apps/notices">
            <el-icon><Document /></el-icon>
            <span>公告管理</span>
          </el-menu-item>
          <el-menu-item index="/apps/versions">
            <el-icon><UploadFilled /></el-icon>
            <span>版本更新</span>
          </el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="/kamis">
          <template #title>
            <el-icon><Key /></el-icon>
            <span>卡密管理</span>
          </template>
          <el-menu-item index="/kamis/batches">
            <el-icon><Document /></el-icon>
            <span>批次管理</span>
          </el-menu-item>
          <el-menu-item index="/kamis/list">
            <el-icon><Key /></el-icon>
            <span>卡密列表</span>
          </el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/devices">
          <el-icon><Monitor /></el-icon>
          <span>设备管理</span>
        </el-menu-item>
        <el-menu-item index="/logs">
          <el-icon><Document /></el-icon>
          <span>事件日志</span>
        </el-menu-item>
        <el-menu-item index="/users">
          <el-icon><UserFilled /></el-icon>
          <span>账号管理</span>
        </el-menu-item>
        <el-menu-item index="/end-users">
          <el-icon><User /></el-icon>
          <span>用户授权</span>
        </el-menu-item>
        <el-menu-item index="/docs/api">
          <el-icon><Document /></el-icon>
          <span>接口文档</span>
        </el-menu-item>
        <el-sub-menu index="/interfaces">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>接口管理</span>
          </template>
          <el-menu-item index="/interfaces/new">
            <el-icon><Setting /></el-icon>
            <span>新增接口</span>
          </el-menu-item>
          <el-menu-item index="/interfaces/list">
            <el-icon><Document /></el-icon>
            <span>接口列表</span>
          </el-menu-item>
        </el-sub-menu>
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
              <span class="user-name">{{ userStore.userInfo?.username || '管理员' }}</span>
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
  Setting,
  Key,
  Monitor,
  Document,
  User,
  UserFilled,
  ArrowDown,
  SwitchButton,
  Fold,
  Expand,
  Moon,
  Sunny,
  Connection,
  DataAnalysis,
  UploadFilled
} from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { useThemeStore } from '../stores/theme'

const publicBase = import.meta.env.BASE_URL
const route = useRoute()
const userStore = useUserStore()
const themeStore = useThemeStore()

const collapsed = ref(false)
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || '')
const isDark = computed(() => themeStore.isDark)

const handleCommand = (command) => {
  if (command === 'logout') {
    userStore.logout()
  }
}
</script>

<style scoped>
.layout {
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
}

.layout__aside {
  position: relative;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(160deg, rgba(255, 255, 255, 0.88), rgba(242, 248, 255, 0.72)),
    rgba(255, 255, 255, 0.76);
  border-right: 1px solid rgba(188, 214, 242, 0.66);
  box-shadow: 10px 0 28px rgba(30, 64, 105, 0.08);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  flex-shrink: 0;
}

.layout__aside::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(255, 255, 255, 0.22) 42%, rgba(235, 246, 255, 0.34)),
    radial-gradient(circle at 22px 22px, rgba(47, 128, 237, 0.08), transparent 120px);
}

.layout__aside > * {
  position: relative;
  z-index: 1;
}

:deep(.side-menu) {
  flex: 1;
  border-right: none;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #475569;
  --el-menu-active-color: #2f80ed;
  --el-menu-hover-bg-color: rgba(241, 247, 255, 0.76);
  padding: 8px 10px 24px;
}

:deep(.side-menu.el-menu--collapse) {
  padding: 8px 6px;
}

:deep(.side-menu .el-menu-item) {
  border-radius: 10px;
  margin: 4px 0;
  transition: background 0.35s, transform 0.3s, color 0.3s;
  height: 46px;
}

:deep(.side-menu .el-menu-item:hover) {
  background: rgba(241, 247, 255, 0.78) !important;
}

:deep(.side-menu .el-menu-item.is-active) {
  background: rgba(234, 244, 255, 0.92) !important;
  color: #2f80ed !important;
  font-weight: 600;
  box-shadow: inset 3px 0 0 #2f80ed, 0 10px 22px rgba(47, 128, 237, 0.1);
}

.logo {
  height: 64px;
  min-height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px 0 12px;
  color: #0f172a;
  background: rgba(255, 255, 255, 0.54);
  border-bottom: 1px solid rgba(188, 214, 242, 0.56);
  flex-shrink: 0;
}

.logo.is-small {
  justify-content: center;
  padding: 0 6px;
}

.logo__img {
  border-radius: 12px;
  flex-shrink: 0;
  background: #fef9c3;
  box-shadow: 0 6px 16px rgba(202, 138, 4, 0.16);
}

.logo__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.logo__name {
  font-size: 17px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0;
  white-space: nowrap;
  text-shadow: none;
}

.logo__hint {
  font-size: 11px;
  opacity: 0.8;
  margin-top: 2px;
}

html.dark .layout__aside {
  background:
    linear-gradient(160deg, rgba(15, 23, 42, 0.88), rgba(30, 41, 59, 0.78)),
    rgba(15, 23, 42, 0.76);
  border-right-color: rgba(71, 85, 105, 0.72);
  box-shadow: 10px 0 28px rgba(0, 0, 0, 0.18);
}

html.dark .layout__aside::before {
  background:
    linear-gradient(180deg, rgba(30, 41, 59, 0.58), rgba(15, 23, 42, 0.26)),
    radial-gradient(circle at 22px 22px, rgba(56, 189, 248, 0.1), transparent 120px);
}

html.dark .logo {
  color: #e5e7eb;
  background: rgba(15, 23, 42, 0.52);
  border-bottom-color: rgba(71, 85, 105, 0.72);
}

html.dark :deep(.side-menu) {
  --el-menu-text-color: #cbd5e1;
  --el-menu-active-color: #60a5fa;
  --el-menu-hover-bg-color: rgba(51, 65, 85, 0.78);
}

html.dark :deep(.side-menu .el-menu-item:hover) {
  background: rgba(51, 65, 85, 0.78) !important;
}

html.dark :deep(.side-menu .el-menu-item.is-active) {
  background: rgba(30, 64, 105, 0.78) !important;
  color: #93c5fd !important;
  box-shadow: inset 3px 0 0 #60a5fa, 0 10px 22px rgba(15, 23, 42, 0.22);
}

.layout__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.layout__header {
  background: rgba(255, 255, 255, 0.86);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px 0 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  z-index: 2;
  flex-shrink: 0;
}

html.dark .layout__header {
  background: var(--el-bg-color-overlay, #1e293b);
  border-color: #334155;
}

.layout__header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.btn-fold {
  font-size: 18px;
  color: var(--el-text-color-regular);
  padding: 8px 10px;
  border-radius: 10px;
  transition: background 0.3s;
}
.btn-fold:hover {
  background: var(--el-fill-color-light, #f3f4f6);
}

html.dark .btn-fold:hover {
  background: #334155;
}

.page-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--el-text-color-primary, #1f2937);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.layout__header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.user-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px 6px 4px;
  border-radius: 12px;
  cursor: pointer;
  color: var(--el-text-color-primary);
  font-weight: 500;
  font-size: 14px;
  transition: background 0.3s, box-shadow 0.3s;
}
.user-pill:hover {
  background: var(--el-fill-color-light, #f3f4f6);
}
html.dark .user-pill:hover {
  background: #334155;
}

.user-avatar {
  background: linear-gradient(135deg, #2f80ed, #38bdf8) !important;
  color: #fff !important;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.user-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main-content {
  padding: 20px 24px 28px;
  overflow: auto;
  flex: 1;
  min-height: 0;
  background: linear-gradient(
    160deg,
    #eaf6ff 0%,
    #f4faff 28%,
    #f8fbff 62%,
    #ffffff 100%
  );
  background-attachment: local;
}
html.dark .main-content {
  background: linear-gradient(180deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
  background-attachment: local;
}

:deep(.main-content .el-button--primary:not(.is-link)) {
  background: linear-gradient(135deg, #2f80ed, #38bdf8) !important;
  border: none;
}
:deep(.main-content .el-button--primary.is-plain:not(.is-link)) {
  background: var(--el-color-primary-light-8) !important;
  color: #1d4ed8;
  border: 1px solid #9fc8fb;
}
</style>
