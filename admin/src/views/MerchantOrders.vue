<template>
  <div class="list-page">
    <div class="page-toolbar">
      <h2>我的订单</h2>
      <el-button type="primary" :loading="loading" @click="loadOrders">刷新</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="orders" v-loading="loading" border stripe>
        <el-table-column prop="order_no" label="订单号" min-width="190" show-overflow-tooltip />
        <el-table-column label="金额" width="100">
          <template #default="{ row }">{{ row.amount }} 元</template>
        </el-table-column>
        <el-table-column prop="credit_quota" label="到账额度" width="110" />
        <el-table-column prop="bonus_quota" label="赠送额度" width="110" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">{{ statusText(row.status) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="180" />
        <el-table-column prop="reviewed_at" label="审核时间" width="180" />
        <el-table-column prop="reject_reason" label="拒绝原因" min-width="160" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getMerchantRechargeOrders } from '../api/merchant'

const loading = ref(false)
const orders = ref([])

const statusText = (status) => ({
  pending_review: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
  abnormal: '异常'
}[status] || status)

async function loadOrders() {
  loading.value = true
  try {
    const res = await getMerchantRechargeOrders({ page: 1, page_size: 50 })
    orders.value = res.data?.items || []
  } finally {
    loading.value = false
  }
}

onMounted(loadOrders)
</script>

<style scoped>
.list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}
</style>
