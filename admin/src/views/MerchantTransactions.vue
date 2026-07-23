<template>
  <div class="list-page">
    <div class="page-toolbar">
      <h2>发卡额度流水</h2>
      <el-button type="primary" :loading="loading" @click="loadTransactions">刷新</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="items" v-loading="loading" border stripe>
        <el-table-column prop="transaction_id" label="流水号" min-width="220" show-overflow-tooltip />
        <el-table-column prop="transaction_type" label="类型" width="110" />
        <el-table-column prop="quota_type" label="额度类型" width="120" />
        <el-table-column prop="amount" label="变动" width="100" />
        <el-table-column prop="balance_after" label="变动后" width="110" />
        <el-table-column prop="biz_id" label="业务单号" min-width="180" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getMerchantQuotaTransactions } from '../api/merchant'

const loading = ref(false)
const items = ref([])

async function loadTransactions() {
  loading.value = true
  try {
    const res = await getMerchantQuotaTransactions({ page: 1, page_size: 50 })
    items.value = res.data?.items || []
  } finally {
    loading.value = false
  }
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
</style>
