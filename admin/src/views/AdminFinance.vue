<template>
  <div class="finance-page">
    <div class="page-toolbar">
      <div>
        <h2>财务运营</h2>
        <p>审核通过时间 reviewed_at</p>
      </div>
      <div class="toolbar-actions">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          unlink-panels
        />
        <el-input
          v-model="filters.username"
          placeholder="发卡用户"
          clearable
          class="user-filter"
          @keyup.enter="loadData"
        />
        <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <section class="metric-grid">
      <el-card v-for="item in metrics" :key="item.label" shadow="never" class="metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </el-card>
    </section>

    <section class="finance-actions">
      <el-select v-model="filters.status" clearable placeholder="订单状态" class="status-filter">
        <el-option label="已通过" value="approved" />
        <el-option label="待审核" value="pending_review" />
        <el-option label="已驳回" value="rejected" />
        <el-option label="已关闭" value="expired" />
        <el-option label="异常" value="abnormal" />
      </el-select>
      <el-select v-model="filters.transaction_type" clearable placeholder="额度流水类型" class="status-filter">
        <el-option label="发放" value="grant" />
        <el-option label="消耗" value="consume" />
        <el-option label="调整" value="adjust" />
        <el-option label="过期" value="expire" />
      </el-select>
      <el-button type="primary" :icon="Download" :loading="exportingOrders" @click="downloadOrders">
        导出订单流水
      </el-button>
      <el-button :icon="Download" :loading="exportingTransactions" @click="downloadTransactions">
        导出额度流水
      </el-button>
    </section>

    <section class="data-grid">
      <el-card shadow="never">
        <template #header>每日收入统计</template>
        <el-table :data="summary.daily || []" v-loading="loading" border stripe>
          <el-table-column prop="date" label="日期" width="130" />
          <el-table-column prop="approved_order_count" label="通过订单" width="110" />
          <el-table-column prop="approved_amount" label="收入金额" width="120" />
          <el-table-column prop="credited_issue_quota" label="到账额度" width="120" />
          <el-table-column prop="bonus_issue_quota" label="赠送额度" width="120" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>用户充值排行</template>
        <el-table :data="ranking" v-loading="loading" border stripe>
          <el-table-column prop="username" label="发卡用户" min-width="130" />
          <el-table-column prop="approved_order_count" label="通过订单" width="110" />
          <el-table-column prop="approved_amount" label="收入金额" width="120" />
          <el-table-column prop="credited_issue_quota" label="到账额度" width="120" />
          <el-table-column prop="bonus_issue_quota" label="赠送额度" width="120" />
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Download, Refresh } from '@element-plus/icons-vue'
import {
  exportQuotaTransactions,
  exportRechargeOrders,
  getFinanceSummary,
  getMerchantRechargeRanking
} from '../api/finance'

const loading = ref(false)
const exportingOrders = ref(false)
const exportingTransactions = ref(false)
const summary = ref({})
const ranking = ref([])
const dateRange = ref([])
const filters = reactive({
  username: '',
  status: 'approved',
  transaction_type: ''
})

const numberText = (value) => Number(value || 0).toLocaleString('zh-CN')

const metrics = computed(() => [
  { label: '已审收入', value: numberText(summary.value.approved_amount) },
  { label: '已到账发卡额度', value: numberText(summary.value.credited_issue_quota) },
  { label: '赠送额度', value: numberText(summary.value.bonus_issue_quota) },
  { label: '待审核订单', value: numberText(summary.value.pending_review_count) },
  { label: '异常订单', value: numberText(summary.value.abnormal_count) }
])

function queryParams() {
  const [start_date, end_date] = dateRange.value || []
  return {
    start_date,
    end_date
  }
}

async function loadData() {
  loading.value = true
  try {
    const params = queryParams()
    const [summaryRes, rankingRes] = await Promise.all([
      getFinanceSummary(params),
      getMerchantRechargeRanking(params)
    ])
    summary.value = summaryRes.data || {}
    ranking.value = rankingRes.data?.items || []
  } finally {
    loading.value = false
  }
}

async function downloadOrders() {
  exportingOrders.value = true
  try {
    const response = await exportRechargeOrders({
      ...queryParams(),
      status: filters.status || undefined,
      username: filters.username || undefined
    })
    saveBlob(response.data, 'recharge-orders.csv')
  } finally {
    exportingOrders.value = false
  }
}

async function downloadTransactions() {
  exportingTransactions.value = true
  try {
    const response = await exportQuotaTransactions({
      ...queryParams(),
      username: filters.username || undefined,
      transaction_type: filters.transaction_type || undefined
    })
    saveBlob(response.data, 'quota-transactions.csv')
  } finally {
    exportingTransactions.value = false
  }
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

onMounted(loadData)
</script>

<style scoped>
.finance-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
  color: #0f172a;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.toolbar-actions,
.finance-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.user-filter {
  width: 180px;
}

.status-filter {
  width: 150px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  min-height: 104px;
  border-radius: 8px;
}

.metric-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-card span {
  color: #64748b;
  font-size: 13px;
}

.metric-card strong {
  color: #0f172a;
  font-size: 28px;
  line-height: 1;
}

.data-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 1100px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .data-grid {
    grid-template-columns: 1fr;
  }

  .page-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .toolbar-actions,
  .finance-actions,
  .user-filter,
  .status-filter {
    width: 100%;
  }
}
</style>
