<template>
  <div class="commercial-page">
    <div class="page-toolbar">
      <div>
        <h2>商业版后台</h2>
        <p>{{ refreshedAt }}</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <section class="metric-grid">
      <el-card v-for="item in metrics" :key="item.label" shadow="never" class="metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </el-card>
    </section>

    <section class="action-grid">
      <el-card shadow="never">
        <template #header>待审核充值</template>
        <div class="focus-number">{{ overview.orders_pending_review || 0 }}</div>
        <el-button type="primary" plain @click="router.push('/admin/commercial/recharge-orders')">处理订单</el-button>
      </el-card>
      <el-card shadow="never">
        <template #header>充值配置</template>
        <div class="focus-number">{{ overview.credited_issue_quota || 0 }}</div>
        <el-button type="primary" plain @click="router.push('/admin/commercial/recharge-settings')">管理额度</el-button>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getCommercialOverview } from '../api/commercial'

const router = useRouter()
const loading = ref(false)
const overview = ref({})
const refreshedAt = ref('')

const numberText = (value) => Number(value || 0).toLocaleString('zh-CN')

const metrics = computed(() => [
  { label: '充值订单', value: numberText(overview.value.orders_total) },
  { label: '待审核', value: numberText(overview.value.orders_pending_review) },
  { label: '已通过', value: numberText(overview.value.orders_approved) },
  { label: '已入账额度', value: numberText(overview.value.credited_issue_quota) }
])

async function loadData() {
  loading.value = true
  try {
    const res = await getCommercialOverview()
    overview.value = res.data || {}
    refreshedAt.value = `最近刷新：${new Date().toLocaleString('zh-CN', { hour12: false })}`
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.commercial-page {
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
  color: #0f172a;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.metric-grid,
.action-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.action-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric-card {
  min-height: 116px;
  border-radius: 8px;
  border-color: #dbeafe;
}

.metric-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-card span {
  color: #64748b;
}

.metric-card strong,
.focus-number {
  font-size: 32px;
  line-height: 1;
  color: #0f172a;
}

.focus-number {
  margin-bottom: 16px;
  font-weight: 800;
}

@media (max-width: 1000px) {
  .metric-grid,
  .action-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .metric-grid,
  .action-grid {
    grid-template-columns: 1fr;
  }
}
</style>
