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
        <el-table-column prop="transaction_id" label="流水号" min-width="180" show-overflow-tooltip />
        <el-table-column prop="username" label="发卡用户" min-width="130" />
        <el-table-column prop="transaction_type" label="类型" width="100" />
        <el-table-column prop="amount" label="变动额度" width="110" />
        <el-table-column prop="balance_after" label="变动后" width="110" />
        <el-table-column prop="biz_id" label="业务单号" min-width="180" show-overflow-tooltip />
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column prop="created_at" label="时间" width="180" />
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
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getCommercialQuotaTransactions } from '../api/commercial'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
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

.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
