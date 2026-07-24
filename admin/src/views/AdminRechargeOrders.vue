<template>
  <div class="orders-page">
    <div class="page-toolbar">
      <h2>充值订单</h2>
      <div class="toolbar-actions">
        <el-button :loading="cleanupLoading" @click="handleCleanupProofs">清理旧凭证</el-button>
        <el-button type="primary" :loading="loading" @click="loadOrders">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="panel">
      <div class="filters">
        <el-select v-model="query.status" clearable placeholder="全部状态" style="width: 180px" @change="loadOrders">
          <el-option label="待审核" value="pending_review" />
          <el-option label="已通过" value="approved" />
          <el-option label="已拒绝" value="rejected" />
          <el-option label="已取消" value="canceled" />
          <el-option label="已过期" value="expired" />
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
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <el-button size="small" plain @click="openDetail(row)">详情</el-button>
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
            <el-button
              size="small"
              type="warning"
              plain
              :disabled="row.status !== 'pending_review'"
              :loading="rowAction === `expire:${row.order_no}`"
              @click="handleExpire(row)"
            >
              过期
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

    <el-drawer v-model="detailVisible" title="订单详情" size="520px">
      <div v-if="selectedOrder" class="detail-body">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="订单号">{{ selectedOrder.order_no }}</el-descriptions-item>
          <el-descriptions-item label="用户">{{ selectedOrder.username }}</el-descriptions-item>
          <el-descriptions-item label="金额">{{ selectedOrder.amount }} 元</el-descriptions-item>
          <el-descriptions-item label="基础额度">{{ selectedOrder.base_quota }}</el-descriptions-item>
          <el-descriptions-item label="赠送额度">{{ selectedOrder.bonus_quota }}</el-descriptions-item>
          <el-descriptions-item label="到账额度">{{ selectedOrder.credit_quota }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusText(selectedOrder.status) }}</el-descriptions-item>
          <el-descriptions-item label="用户备注">{{ selectedOrder.user_remark || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核备注">{{ selectedOrder.admin_remark || '-' }}</el-descriptions-item>
          <el-descriptions-item label="拒绝原因">{{ selectedOrder.reject_reason || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核人">{{ selectedOrder.reviewer || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审核时间">{{ selectedOrder.reviewed_at || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div class="snapshot-block">
          <div class="snapshot-title">payment_snapshot</div>
          <pre>{{ formatSnapshot(selectedOrder.payment_snapshot) }}</pre>
        </div>
        <div class="snapshot-block">
          <div class="snapshot-title">preview_snapshot</div>
          <pre>{{ formatSnapshot(selectedOrder.preview_snapshot) }}</pre>
        </div>
        <div class="drawer-actions">
          <el-button type="primary" plain :disabled="!selectedOrder.has_proof" @click="openProof(selectedOrder)">查看凭证</el-button>
          <el-button
            type="success"
            plain
            :disabled="selectedOrder.status !== 'pending_review'"
            :loading="rowAction === `approve:${selectedOrder.order_no}`"
            @click="handleApprove(selectedOrder)"
          >
            通过
          </el-button>
          <el-button
            type="danger"
            plain
            :disabled="selectedOrder.status !== 'pending_review'"
            :loading="rowAction === `reject:${selectedOrder.order_no}`"
            @click="handleReject(selectedOrder)"
          >
            拒绝
          </el-button>
          <el-button
            type="warning"
            plain
            :disabled="selectedOrder.status !== 'pending_review'"
            :loading="rowAction === `expire:${selectedOrder.order_no}`"
            @click="handleExpire(selectedOrder)"
          >
            过期
          </el-button>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="proofVisible" title="支付凭证" width="520px">
      <img v-if="proofUrl" class="proof-image" :src="proofUrl" alt="支付凭证" />
      <el-empty v-else description="暂无支付凭证" />
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  approveRechargeOrder,
  cleanupRechargeProofs,
  expireRechargeOrder,
  getRechargeOrders,
  rejectRechargeOrder
} from '../api/commercial'

const loading = ref(false)
const cleanupLoading = ref(false)
const rowAction = ref('')
const orders = ref([])
const total = ref(0)
const proofVisible = ref(false)
const proofUrl = ref('')
const detailVisible = ref(false)
const selectedOrder = ref(null)
const CONFIRM_APPROVE_RECHARGE_ORDER = '确认审核入账'
const CONFIRM_REJECT_RECHARGE_ORDER = '确认驳回订单'
const CONFIRM_EXPIRE_RECHARGE_ORDER = '确认关闭订单'
const CONFIRM_CLEANUP_PROOF_FILES = '确认清理凭证'

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
  canceled: '已取消',
  expired: '已过期',
  abnormal: '异常'
}[status] || status)

const statusType = (status) => ({
  pending_review: 'warning',
  approved: 'success',
  rejected: 'danger',
  canceled: 'info',
  expired: 'info',
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

function openDetail(row) {
  selectedOrder.value = row
  detailVisible.value = true
}

function formatSnapshot(snapshot) {
  if (!snapshot || Object.keys(snapshot).length === 0) return '-'
  return JSON.stringify(snapshot, null, 2)
}

async function promptSensitiveConfirm(expected, title) {
  const { value } = await ElMessageBox.prompt(`请输入「${expected}」以确认`, title, {
    inputValue: '',
    inputValidator: (value) => value === expected || `请输入${expected}`,
    type: 'warning'
  })
  return value
}

async function handleApprove(row) {
  try {
    await ElMessageBox.confirm(`确认通过订单 ${row.order_no} 并自动入账 ${row.credit_quota} 发卡额度？`, '审核通过', {
      type: 'warning'
    })
    const confirmText = await promptSensitiveConfirm(CONFIRM_APPROVE_RECHARGE_ORDER, '审核通过')
    rowAction.value = `approve:${row.order_no}`
    await approveRechargeOrder(row.order_no, { remark: '后台审核通过', confirm_text: confirmText })
    ElMessage.success('订单已通过并入账')
    detailVisible.value = false
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
    const confirmText = await promptSensitiveConfirm(CONFIRM_REJECT_RECHARGE_ORDER, '驳回订单')
    rowAction.value = `reject:${row.order_no}`
    await rejectRechargeOrder(row.order_no, { reject_reason: value, remark: value, confirm_text: confirmText })
    ElMessage.success('订单已拒绝')
    detailVisible.value = false
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  } finally {
    rowAction.value = ''
  }
}

async function handleExpire(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入过期备注，可留空', `标记订单 ${row.order_no} 过期`, {
      inputValue: '人工确认超时未入账',
      type: 'warning'
    })
    const confirmText = await promptSensitiveConfirm(CONFIRM_EXPIRE_RECHARGE_ORDER, '标记过期')
    rowAction.value = `expire:${row.order_no}`
    await expireRechargeOrder(row.order_no, { remark: value || '人工确认超时未入账', confirm_text: confirmText })
    ElMessage.success('订单已标记过期')
    detailVisible.value = false
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  } finally {
    rowAction.value = ''
  }
}

async function handleCleanupProofs() {
  try {
    const { value } = await ElMessageBox.prompt('仅清理已审核/取消/过期/异常订单的旧凭证，请输入保留天数', '清理旧凭证', {
      inputValue: '90',
      inputPattern: /^[1-9]\d*$/,
      inputErrorMessage: '请输入大于 0 的整数',
      type: 'warning'
    })
    const olderThanDays = Number(value)
    cleanupLoading.value = true
    const preview = await cleanupRechargeProofs({ older_than_days: olderThanDays, dry_run: true })
    const matchedOrders = preview.data?.matched_orders || 0
    const deletedProofs = preview.data?.deleted_proofs || 0
    if (!matchedOrders) {
      ElMessage.success('没有需要清理的旧凭证')
      return
    }
    await ElMessageBox.confirm(
      `将清理 ${matchedOrders} 个订单中的 ${deletedProofs} 个凭证文件，订单记录会保留。确认继续？`,
      '确认清理旧凭证',
      { type: 'warning' }
    )
    const confirmText = await promptSensitiveConfirm(CONFIRM_CLEANUP_PROOF_FILES, '清理旧凭证')
    const res = await cleanupRechargeProofs({ older_than_days: olderThanDays, dry_run: false, confirm_text: confirmText })
    ElMessage.success(`已清理 ${res.data?.deleted_proofs || 0} 个凭证文件`)
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  } finally {
    cleanupLoading.value = false
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

.toolbar-actions,
.drawer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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

.detail-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.snapshot-block {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  overflow: hidden;
}

.snapshot-title {
  padding: 8px 10px;
  color: #475569;
  font-size: 13px;
  border-bottom: 1px solid #e2e8f0;
}

.snapshot-block pre {
  margin: 0;
  padding: 10px;
  max-height: 180px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
