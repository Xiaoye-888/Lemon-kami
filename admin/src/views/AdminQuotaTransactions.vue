<template>
  <div class="admin-page">
    <div class="page-toolbar">
      <div>
        <h2>发卡额度流水</h2>
        <p>仅展示发卡额度的入账和扣减记录</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column prop="username" label="发卡用户" min-width="130" />
        <el-table-column prop="short_transaction_no" label="记录编号" width="130" />
        <el-table-column prop="display_scene" label="业务场景" min-width="130" />
        <el-table-column prop="display_direction" label="额度方向" width="110" />
        <el-table-column prop="amount" label="额度变动" width="110" />
        <el-table-column prop="balance_after" label="变动后" width="110" />
        <el-table-column prop="display_subject" label="关联对象" min-width="220" show-overflow-tooltip />
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openTransactionDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pager"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>

    <el-dialog v-model="detailVisible" title="流水详情" width="560px">
      <div v-if="selectedTransaction" class="transaction-detail">
        <div class="detail-row">
          <span>发卡用户</span>
          <strong>{{ selectedTransaction.username || '-' }}</strong>
        </div>
        <div class="detail-row">
          <span>业务场景</span>
          <strong>{{ selectedTransaction.display_scene || '-' }}</strong>
        </div>
        <div class="detail-row">
          <span>额度方向</span>
          <strong>{{ selectedTransaction.display_direction || '-' }}</strong>
        </div>
        <div class="detail-row">
          <span>完整记录编号</span>
          <code>{{ selectedTransaction.transaction_id || '-' }}</code>
        </div>
        <div class="detail-row">
          <span>原始业务编号</span>
          <code>{{ selectedTransaction.biz_id || '-' }}</code>
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
import { onMounted, reactive, ref } from 'vue'
import { getCommercialQuotaTransactions } from '../api/commercial'
import { formatBeijingTime } from '../utils/datetime'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const detailVisible = ref(false)
const selectedTransaction = ref(null)
const query = reactive({
  page: 1,
  page_size: 20
})

async function loadData() {
  loading.value = true
  try {
    const res = await getCommercialQuotaTransactions({
      ...query,
      quota_type: 'kami_issue'
    })
    rows.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function openTransactionDetail(row) {
  selectedTransaction.value = row
  detailVisible.value = true
}

onMounted(loadData)
</script>

<style scoped>
.admin-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
}

.transaction-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-row {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
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

.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
