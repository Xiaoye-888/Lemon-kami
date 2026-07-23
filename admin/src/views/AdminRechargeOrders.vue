<template>
  <div class="orders-page">
    <div class="page-toolbar">
      <h2>充值订单</h2>
      <el-button type="primary" :loading="loading" @click="loadOrders">刷新</el-button>
    </div>

    <el-card shadow="never" class="panel">
      <div class="filters">
        <el-select v-model="query.status" clearable placeholder="全部状态" style="width: 180px" @change="loadOrders">
          <el-option label="待审核" value="pending_review" />
          <el-option label="已通过" value="approved" />
          <el-option label="已拒绝" value="rejected" />
          <el-option label="异常" value="abnormal" />
        </el-select>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <el-table :data="orders" v-loading="loading" border stripe>
        <el-table-column prop="order_no" label="订单号" min-width="190" show-overflow-tooltip />
        <el-table-column prop="username" label="用户" min-width="120" />
        <el-table-column label="金额" width="100">
          <template #default="{ row }">{{ row.amount }} 元</template>
        </el-table-column>
        <el-table-column prop="credit_quota" label="到账额度" width="110" />
        <el-table-column prop="bonus_quota" label="赠送额度" width="110" />
        <el-table-column label="支付渠道" width="110">
          <template #default="{ row }">{{ channelText(row.channel) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="180" />
        <el-table-column label="支付凭证" width="110">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="!row.has_proof" @click="openProof(row)">查看</el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="success"
              plain
              :disabled="row.status !== 'pending_review'"
              :loading="rowAction === `approve:${row.order_no}`"
              @click="handleApprove(row)"
            >
              通过
            </el-button>
            <el-button
              size="small"
              type="danger"
              plain
              :disabled="row.status !== 'pending_review'"
              :loading="rowAction === `reject:${row.order_no}`"
              @click="handleReject(row)"
            >
              拒绝
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <span>共 {{ total }} 条</span>
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="sizes, prev, pager, next"
          @size-change="loadOrders"
          @current-change="loadOrders"
        />
      </div>
    </el-card>

    <el-dialog v-model="proofVisible" title="支付凭证" width="520px">
      <img v-if="proofUrl" class="proof-image" :src="proofUrl" alt="支付凭证" />
      <el-empty v-else description="暂无支付凭证" />
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { approveRechargeOrder, getRechargeOrders, rejectRechargeOrder } from '../api/commercial'

const loading = ref(false)
const rowAction = ref('')
const orders = ref([])
const total = ref(0)
const proofVisible = ref(false)
const proofUrl = ref('')

const query = reactive({
  status: '',
  page: 1,
  page_size: 20
})

const normalizeParams = () => {
  const params = { ...query }
  if (!params.status) delete params.status
  return params
}

const statusText = (status) => ({
  pending_review: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
  abnormal: '异常'
}[status] || status)

const statusType = (status) => ({
  pending_review: 'warning',
  approved: 'success',
  rejected: 'danger',
  abnormal: 'info'
}[status] || 'info')

const channelText = (channel) => ({
  wechat: '微信',
  alipay: '支付宝',
  bank: '银行卡',
  other: '其他'
}[channel] || channel)

async function loadOrders() {
  loading.value = true
  try {
    const res = await getRechargeOrders(normalizeParams())
    orders.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  query.status = ''
  query.page = 1
  loadOrders()
}

function openProof(row) {
  if (!row.has_proof) return
  const token = localStorage.getItem('token')
  proofUrl.value = `/api/v1/admin/commercial/recharge-orders/${row.order_no}/proof?token=${encodeURIComponent(token || '')}`
  proofVisible.value = true
}

async function handleApprove(row) {
  try {
    await ElMessageBox.confirm(`确认通过订单 ${row.order_no} 并自动入账 ${row.credit_quota} 发卡额度？`, '审核通过', {
      type: 'warning'
    })
    rowAction.value = `approve:${row.order_no}`
    await approveRechargeOrder(row.order_no, { remark: '后台审核通过' })
    ElMessage.success('订单已通过并入账')
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  } finally {
    rowAction.value = ''
  }
}

async function handleReject(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝订单', {
      inputValue: '',
      inputValidator: (value) => Boolean(value?.trim()) || '请填写拒绝原因',
      type: 'warning'
    })
    rowAction.value = `reject:${row.order_no}`
    await rejectRechargeOrder(row.order_no, { reject_reason: value, remark: value })
    ElMessage.success('订单已拒绝')
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
.orders-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar,
.filters,
.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}

.panel {
  border-radius: 8px;
}

.filters {
  justify-content: flex-start;
  margin-bottom: 14px;
}

.table-footer {
  min-height: 64px;
  padding-top: 16px;
}

.proof-image {
  display: block;
  width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 8px;
}
</style>
