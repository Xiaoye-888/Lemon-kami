<template>
  <div class="merchant-page">
    <div class="page-toolbar">
      <div>
        <h2>商户控制台</h2>
        <p>{{ userStore.userInfo?.username || 'merchant' }}</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <section class="metric-grid">
      <el-card v-for="item in metrics" :key="item.label" shadow="never" class="metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </el-card>
    </section>

    <section class="quick-grid">
      <el-button type="primary" @click="router.push('/merchant/recharge')">充值发卡额度</el-button>
      <el-button @click="router.push('/merchant/orders')">我的订单</el-button>
      <el-button @click="router.push('/merchant/batches')">批次管理</el-button>
      <el-button @click="router.push('/merchant/cards')">我的卡密</el-button>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMerchantQuotas } from '../api/merchant'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const quotas = ref({})

const numberText = (value) => Number(value || 0).toLocaleString('zh-CN')

const metrics = computed(() => [
  { label: '发卡额度', value: numberText(quotas.value.kami_issue_balance) },
  { label: '建站额度', value: numberText(quotas.value.app_create_balance) },
  { label: '累计发卡额度', value: numberText(quotas.value.total_kami_issue_granted) },
  { label: '账户状态', value: quotas.value.status === 0 ? '停用' : '正常' }
])

async function loadData() {
  loading.value = true
  try {
    const res = await getMerchantQuotas()
    quotas.value = res.data || {}
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.merchant-page {
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

.metric-grid,
.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.metric-card {
  min-height: 118px;
  border-radius: 8px;
}

.metric-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-card span {
  color: #64748b;
}

.metric-card strong {
  font-size: 30px;
  color: #0f172a;
}

.quick-grid .el-button {
  height: 48px;
  margin: 0;
}

@media (max-width: 960px) {
  .metric-grid,
  .quick-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
