<template>
  <div class="list-page">
    <div class="page-toolbar">
      <h2>发卡额度流水</h2>
      <el-button type="primary" :loading="loading" @click="loadTransactions">刷新</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="items" v-loading="loading" border stripe>
        <el-table-column prop="short_transaction_no" label="记录编号" width="130" />
        <el-table-column prop="display_scene" label="业务场景" min-width="130" />
        <el-table-column prop="display_direction" label="额度方向" width="110" />
        <el-table-column prop="display_quota_type" label="额度账户" width="120" />
        <el-table-column prop="amount" label="额度变动" width="110" />
        <el-table-column prop="balance_after" label="变动后" width="110" />
        <el-table-column prop="display_subject" label="关联对象" min-width="220" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openTransactionDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="流水详情" width="560px">
      <div v-if="selectedTransaction" class="transaction-detail">
        <div class="detail-row">
          <span>业务场景</span>
          <strong>{{ selectedTransaction.display_scene || '-' }}</strong>
        </div>
        <div class="detail-row">
          <span>额度方向</span>
          <strong>{{ selectedTransaction.display_direction || '-' }}</strong>
        </div>
        <div class="detail-row">
          <span>额度账户</span>
          <strong>{{ selectedTransaction.display_quota_type || '-' }}</strong>
        </div>
        <div class="detail-row">
          <span>关联对象</span>
          <strong>{{ selectedTransaction.display_subject || '-' }}</strong>
        </div>
        <div class="detail-row">
          <span>完整记录编号</span>
          <code>{{ selectedTransaction.transaction_id || '-' }}</code>
          <el-button size="small" link type="primary" @click="copyValue(selectedTransaction.transaction_id)">复制</el-button>
        </div>
        <div class="detail-row">
          <span>原始业务编号</span>
          <code>{{ selectedTransaction.biz_id || '-' }}</code>
          <el-button size="small" link type="primary" @click="copyValue(selectedTransaction.biz_id)">复制</el-button>
        </div>
        <div class="detail-row">
          <span>备注</span>
          <strong>{{ selectedTransaction.remark || '-' }}</strong>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getMerchantQuotaTransactions } from '../api/merchant'
import { copyTextToClipboard } from '../utils/clipboard'
import { formatBeijingTime } from '../utils/datetime'

const loading = ref(false)
const items = ref([])
const detailVisible = ref(false)
const selectedTransaction = ref(null)

async function loadTransactions() {
  loading.value = true
  try {
    const res = await getMerchantQuotaTransactions({ page: 1, page_size: 50 })
    items.value = res.data?.items || []
  } finally {
    loading.value = false
  }
}

function openTransactionDetail(row) {
  selectedTransaction.value = row
  detailVisible.value = true
}

async function copyValue(value) {
  if (!value) {
    ElMessage.warning('暂无可复制内容')
    return
  }
  await copyTextToClipboard(value)
  ElMessage.success('复制成功')
}

onMounted(loadTransactions)
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

.transaction-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-row {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
}

.detail-row span {
  color: #64748b;
}

.detail-row code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
