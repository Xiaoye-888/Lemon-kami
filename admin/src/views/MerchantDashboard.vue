<template>
  <div class="merchant-dashboard">
    <div class="page-toolbar">
      <div>
        <h2>发卡工作台</h2>
        <p>{{ userStore.userInfo?.username || '发卡用户' }}</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <section class="metric-grid">
      <el-card v-for="item in metrics" :key="item.label" shadow="never" class="metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.hint }}</small>
      </el-card>
    </section>

    <section class="workbench-grid">
      <el-card shadow="never" class="workbench-panel notice-panel">
        <template #header>
          <div class="panel-header">
            <span>待办与通知</span>
            <el-tag v-if="lowBalanceWarning" type="warning" effect="plain">额度偏低</el-tag>
          </div>
        </template>

        <div class="todo-list">
          <div v-if="lowBalanceWarning" class="todo-item todo-item--warning">
            <strong>发卡额度不足</strong>
            <span>当前余额 {{ quota.balance || 0 }}，低于预警值 {{ quota.warning_threshold || 0 }}</span>
          </div>
          <div v-if="dashboard.orders?.pending_review" class="todo-item">
            <strong>充值订单待审核</strong>
            <span>{{ dashboard.orders.pending_review }} 笔订单正在等待管理员审核</span>
          </div>
          <div v-if="!lowBalanceWarning && !dashboard.orders?.pending_review" class="todo-item todo-item--quiet">
            <strong>暂无待办</strong>
            <span>当前账户状态正常，可以继续发卡或管理批次</span>
          </div>
        </div>

        <el-divider />

        <div class="notice-list">
          <div v-for="notice in notifications" :key="notice.id" class="notice-item">
            <div>
              <strong>{{ notice.title }}</strong>
              <span>{{ notice.app_name || notice.app_id }}</span>
            </div>
            <p>{{ notice.content }}</p>
          </div>
          <el-empty v-if="!notifications.length" description="暂无应用通知" />
        </div>
      </el-card>

      <el-card shadow="never" class="workbench-panel action-panel">
        <template #header>快捷操作</template>
        <div class="quick-actions">
          <el-button type="primary" @click="router.push('/merchant/recharge')">充值额度</el-button>
          <el-button @click="router.push('/merchant/apps')">新建应用</el-button>
          <el-button @click="router.push('/merchant/batches')">生成批次</el-button>
          <el-button @click="router.push('/merchant/cards')">导出卡密</el-button>
        </div>
      </el-card>
    </section>

    <section class="recent-grid">
      <el-card shadow="never" class="workbench-panel">
        <template #header>最近批次</template>
        <el-table :data="recentBatches" border stripe>
          <el-table-column prop="batch_no" label="批次号" min-width="160" show-overflow-tooltip />
          <el-table-column prop="count" label="数量" width="90" />
          <el-table-column prop="kami_type" label="类型" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="170" />
        </el-table>
      </el-card>

      <el-card shadow="never" class="workbench-panel">
        <template #header>最近订单</template>
        <el-table :data="recentOrders" border stripe>
          <el-table-column prop="order_no" label="订单号" min-width="170" show-overflow-tooltip />
          <el-table-column prop="amount" label="金额" width="100" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="created_at" label="创建时间" width="170" />
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMerchantDashboard } from '../api/merchant'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const dashboard = ref({
  quota: {},
  apps: {},
  orders: {},
  cards: {},
  notifications: [],
  recent_batches: [],
  recent_orders: []
})

const quota = computed(() => dashboard.value.quota || {})
const lowBalanceWarning = computed(() => Boolean(quota.value.low_balance_warning))
const notifications = computed(() => dashboard.value.notifications || [])
const recentBatches = computed(() => dashboard.value.recent_batches || [])
const recentOrders = computed(() => dashboard.value.recent_orders || [])

const numberText = (value) => Number(value || 0).toLocaleString('zh-CN')

const metrics = computed(() => [
  {
    label: '可用发卡额度',
    value: numberText(quota.value.balance),
    hint: `累计获得 ${numberText(quota.value.total_granted)}`
  },
  {
    label: '我的应用',
    value: numberText(dashboard.value.apps?.total),
    hint: `自建 ${numberText(dashboard.value.apps?.self_owned)} / 授权 ${numberText(dashboard.value.apps?.authorized)}`
  },
  {
    label: '已生成卡密',
    value: numberText(dashboard.value.cards?.total),
    hint: '仅统计当前账号生成'
  },
  {
    label: '待审核订单',
    value: numberText(dashboard.value.orders?.pending_review),
    hint: '管理员审核后自动入账'
  }
])

async function loadData() {
  loading.value = true
  try {
    const res = await getMerchantDashboard()
    dashboard.value = res.data || dashboard.value
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.merchant-dashboard {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 26px;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.metric-card {
  min-height: 126px;
  border-radius: 8px;
}

.metric-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.metric-card span,
.metric-card small {
  color: #64748b;
}

.metric-card strong {
  font-size: 28px;
  color: #0f172a;
}

.workbench-grid {
  display: grid;
  grid-template-columns: minmax(520px, 1fr) minmax(260px, 340px);
  gap: 16px;
  align-items: start;
}

.recent-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.workbench-panel {
  border-radius: 8px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.todo-list,
.notice-list,
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.todo-item,
.notice-item {
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
}

.todo-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #334155;
}

.todo-item--warning {
  border-color: #fde68a;
  background: #fffbeb;
}

.todo-item--quiet {
  border-style: dashed;
}

.notice-item strong,
.todo-item strong {
  color: #0f172a;
}

.notice-item span {
  margin-left: 8px;
  color: #64748b;
  font-size: 13px;
}

.notice-item p {
  margin: 8px 0 0;
  color: #475569;
  line-height: 1.6;
}

.quick-actions .el-button {
  width: 100%;
  height: 42px;
  margin: 0;
}

@media (max-width: 1100px) {
  .metric-grid,
  .recent-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .workbench-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .metric-grid,
  .recent-grid {
    grid-template-columns: 1fr;
  }

  .todo-item {
    flex-direction: column;
  }
}
</style>
