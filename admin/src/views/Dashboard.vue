<template>
  <div class="dashboard">
    <div class="toolbar">
      <div>
        <h2>运营总览</h2>
        <p>{{ nowText }}</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadDashboard">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <section class="metric-grid metric-grid--a">
      <el-card
        v-for="item in overviewCards"
        :key="item.key"
        shadow="never"
        class="metric-card"
        :class="`metric-card--${item.tone}`"
      >
        <span class="metric-card__accent"></span>
        <div class="metric-card__label">{{ item.label }}</div>
        <div class="metric-card__value">{{ item.value }}</div>
        <div class="metric-card__hint">{{ item.hint }}</div>
      </el-card>
    </section>

    <section class="dashboard-board dashboard-board--top">
      <el-card shadow="never" class="panel panel--usage">
        <template #header>
          <div class="panel-header">
            <span>今日生成与消耗</span>
            <el-tag type="info" effect="plain">北京时间</el-tag>
          </div>
        </template>
        <div class="today-grid">
          <div v-for="item in usageCards" :key="item.key" class="today-item">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="panel panel--users">
        <template #header>
          <div class="panel-header">
            <span>用户授权概览</span>
            <el-button class="panel-link" link type="primary" @click="router.push('/end-users')">查看用户</el-button>
          </div>
        </template>
        <div class="today-grid today-grid--compact">
          <div v-for="item in userOverviewCards" :key="item.key" class="today-item">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </el-card>
    </section>

    <section class="dashboard-board dashboard-board--bottom">
      <el-card shadow="never" class="panel panel--ops-check">
        <template #header>
          <div class="panel-header">
            <span>接入健康概览</span>
            <el-button class="panel-link" link type="primary" @click="router.push('/logs')">查看日志</el-button>
          </div>
        </template>
        <div class="risk-list">
          <div v-for="item in integrationHealthRows" :key="item.key" class="risk-row">
            <span class="risk-dot" :class="item.tone"></span>
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="panel panel--quick">
        <template #header>
          <div class="panel-header">
            <span>快捷入口</span>
          </div>
        </template>
        <div class="quick-actions">
          <el-button :icon="Plus" @click="router.push('/apps')">创建应用</el-button>
          <el-button :icon="Key" @click="router.push('/kamis/batches')">生成批次</el-button>
          <el-button :icon="Key" @click="router.push({ path: '/kamis/list', query: { action: 'generate' } })">生成卡密</el-button>
          <el-button :icon="User" @click="router.push('/end-users')">分配授权</el-button>
        </div>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Key, Plus, Refresh, User } from '@element-plus/icons-vue'
import { getDashboard } from '../api/admin'

const router = useRouter()
const loading = ref(false)
const dashboard = ref({
  overview: {},
  today: {},
  risk: {},
  integration_health: {}
})
const nowText = ref('')

const numberText = (value) => Number(value || 0).toLocaleString('zh-CN')
const percentText = (value) => {
  if (value === null || value === undefined) return '-'
  return `${Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}%`
}
const latestCallText = (value) => {
  if (!value) return '暂无'
  const date = new Date(value)
  if (!Number.isNaN(date.getTime())) {
    return date.toLocaleTimeString('zh-CN', { hour12: false })
  }
  return String(value).replace('T', ' ').slice(11, 19) || String(value)
}

const overview = computed(() => dashboard.value.overview || {})
const today = computed(() => dashboard.value.today || {})
const risk = computed(() => dashboard.value.risk || {})
const integrationHealth = computed(() => dashboard.value.integration_health || {})

const overviewCards = computed(() => [
  { key: 'kamis', label: '总卡密', value: numberText(overview.value.kamis_total), hint: '库存总量', tone: 'blue' },
  { key: 'unused', label: '未使用', value: numberText(overview.value.kamis_unused), hint: '可发放卡密', tone: 'green' },
  { key: 'active', label: '已激活', value: numberText(overview.value.kamis_active), hint: '正在使用', tone: 'amber' },
  { key: 'frozen', label: '冻结', value: numberText(overview.value.kamis_frozen), hint: '需处理卡密', tone: 'purple' }
])

const usageCards = computed(() => [
  { key: 'new_kamis', label: '新卡密', value: numberText(today.value.new_kamis) },
  { key: 'verify_events', label: '验证', value: numberText(today.value.verify_events) },
  { key: 'points_consumed', label: '积分消耗', value: numberText(today.value.points_consumed) },
  { key: 'times_consumed', label: '次数核销', value: numberText(today.value.times_consumed) }
])

const userOverviewCards = computed(() => [
  { key: 'end_users', label: '注册用户', value: numberText(overview.value.end_users_total) },
  { key: 'authorized', label: '已授权用户', value: numberText(overview.value.authorization_accounts_total) },
  { key: 'devices', label: '设备授权', value: numberText(overview.value.devices_total) },
  { key: 'new_users', label: '今日新用户', value: numberText(today.value.new_end_users) }
])

const integrationHealthRows = computed(() => [
  {
    key: 'active_apps_today',
    label: '今日活跃应用',
    value: `${numberText(integrationHealth.value.active_apps_today)} 个`,
    tone: Number(integrationHealth.value.active_apps_today || 0) > 0 ? 'is-normal' : 'is-warning'
  },
  {
    key: 'verify_success_rate',
    label: '验证成功率',
    value: percentText(integrationHealth.value.verify_success_rate),
    tone: Number(integrationHealth.value.verify_success_rate || 0) >= 90 ? 'is-normal' : 'is-warning'
  },
  {
    key: 'latest_sdk_call_at',
    label: '最近调用',
    value: latestCallText(integrationHealth.value.latest_sdk_call_at),
    tone: integrationHealth.value.latest_sdk_call_at ? 'is-normal' : 'is-warning'
  },
  {
    key: 'abnormal_calls_today',
    label: '异常调用',
    value: numberText(integrationHealth.value.abnormal_calls_today),
    tone: Number(integrationHealth.value.abnormal_calls_today || 0) > 0 ? 'is-danger' : 'is-normal'
  }
])

const loadDashboard = async () => {
  loading.value = true
  try {
    const res = await getDashboard()
    dashboard.value = res.data || dashboard.value
    nowText.value = `最近刷新：${new Date().toLocaleString('zh-CN', { hour12: false })}`
  } catch (error) {
    console.error('加载仪表盘失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 2px 0 4px;
}

.toolbar h2 {
  margin: 0;
  font-size: 26px;
  color: #0f172a;
}

.toolbar p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.metric-grid {
  display: grid;
  gap: 16px;
}

.metric-grid--a {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-card {
  position: relative;
  min-height: 126px;
  border-radius: 8px;
  border: 1px solid #dbeafe;
  overflow: hidden;
}

.metric-card :deep(.el-card__body) {
  height: 100%;
  padding: 18px 20px;
}

.metric-card__accent {
  display: block;
  width: 36px;
  height: 4px;
  margin-bottom: 16px;
  border-radius: 999px;
  background: #2f80ed;
}

.metric-card__label {
  color: #64748b;
  font-size: 14px;
}

.metric-card__value {
  margin-top: 12px;
  font-size: 34px;
  line-height: 1;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: 0;
}

.metric-card__hint {
  margin-top: 10px;
  color: #64748b;
  font-size: 13px;
}

.metric-card--blue {
  background: linear-gradient(135deg, #eff6ff, #ffffff);
}

.metric-card--blue .metric-card__accent {
  background: #2f80ed;
}

.metric-card--green {
  background: linear-gradient(135deg, #f0fdf4, #ffffff);
}

.metric-card--green .metric-card__accent {
  background: #16a34a;
}

.metric-card--amber {
  background: linear-gradient(135deg, #fffbeb, #ffffff);
}

.metric-card--amber .metric-card__accent {
  background: #f59e0b;
}

.metric-card--purple {
  background: linear-gradient(135deg, #f5f3ff, #ffffff);
}

.metric-card--purple .metric-card__accent {
  background: #8b5cf6;
}

.dashboard-board {
  display: grid;
  gap: 16px;
  align-items: stretch;
}

.dashboard-board--top {
  grid-template-columns: minmax(0, 1.3fr) minmax(360px, 1fr);
}

.dashboard-board--bottom {
  grid-template-columns: minmax(360px, 1fr) minmax(360px, 1fr);
}

.panel {
  border-radius: 8px;
  border: 1px solid #dbeafe;
  min-width: 0;
  overflow: hidden;
}

.panel :deep(.el-card__header) {
  padding: 0 18px;
  min-height: 54px;
  display: flex;
  align-items: center;
  border-bottom-color: #e6f0fb;
}

.panel :deep(.el-card__body) {
  padding: 16px 18px 18px;
}

.panel-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 700;
  color: #1e3a5f;
}

.panel-link {
  color: #1d4ed8 !important;
  background: transparent !important;
  border: none !important;
  padding: 2px 0;
  font-weight: 700;
}

.panel-link:hover {
  color: #0f62cc !important;
  background: transparent !important;
}

.today-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.today-grid--compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.today-item {
  min-height: 78px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.today-item span {
  color: #64748b;
  font-size: 13px;
}

.today-item strong {
  color: #0f172a;
  font-size: 22px;
  line-height: 1;
}

.risk-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.risk-row {
  display: grid;
  grid-template-columns: 16px 1fr auto;
  align-items: center;
  gap: 10px;
  min-height: 50px;
  padding: 9px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.risk-row strong {
  font-size: 18px;
  color: #0f172a;
}

.risk-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.risk-dot.is-normal {
  background: #16a34a;
}

.risk-dot.is-warning {
  background: #f59e0b;
}

.risk-dot.is-danger {
  background: #ef4444;
}

.quick-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.quick-actions .el-button {
  margin: 0;
  justify-content: flex-start;
  height: 44px;
  color: #334155;
  background: #ffffff;
  border-color: #dbeafe;
}

.quick-actions .el-button:hover {
  color: #1d4ed8;
  border-color: #9fc8fb;
  background: #f8fbff;
}

html.dark .toolbar h2,
html.dark .metric-card__value,
html.dark .today-item strong,
html.dark .risk-row strong {
  color: #e5e7eb;
}

html.dark .panel,
html.dark .metric-card,
html.dark .risk-row,
html.dark .today-item {
  background: #111827;
  border-color: #334155;
}

html.dark .quick-actions .el-button {
  color: #e5e7eb;
  background: #111827;
  border-color: #334155;
}

@media (max-width: 1280px) {
  .metric-grid--a,
  .dashboard-board--top,
  .dashboard-board--bottom {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .today-grid {
    grid-template-columns: repeat(auto-fit, minmax(136px, 1fr));
  }
}

@media (max-width: 860px) {
  .toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .metric-grid--a,
  .dashboard-board--top,
  .dashboard-board--bottom {
    grid-template-columns: 1fr;
  }
}
</style>
