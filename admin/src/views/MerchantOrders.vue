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
        <el-table-column prop="created_at" label="提交时间" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="reviewed_at" label="审核时间" width="180">
          <template #default="{ row }">{{ formatOptionalTime(row.reviewed_at) }}</template>
        </el-table-column>
        <el-table-column prop="reject_reason" label="拒绝原因" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="danger"
              :disabled="row.status !== 'pending_review'"
              :loading="rowAction === `cancel:${row.order_no}`"
              @click="handleCancelOrder(row)"
            >
              取消
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cancelMerchantRechargeOrder, getMerchantRechargeOrders } from '../api/merchant'
import { formatBeijingTime } from '../utils/datetime'

const loading = ref(false)
const rowAction = ref('')
const orders = ref([])
const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

const statusText = (status) => ({
  pending_review: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
  canceled: '已取消',
  expired: '已过期',
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

async function handleCancelOrder(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入取消备注，可留空', `取消订单 ${row.order_no}`, {
      inputValue: '用户取消充值',
      type: 'warning'
    })
    rowAction.value = `cancel:${row.order_no}`
    await cancelMerchantRechargeOrder(row.order_no, { remark: value || '用户取消充值' })
    ElMessage.success('订单已取消')
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  } finally {
    rowAction.value = ''
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
