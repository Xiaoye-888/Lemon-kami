<template>
  <div class="list-page">
    <div class="page-toolbar">
      <h2>我的卡密</h2>
      <div class="actions">
        <el-select v-model="selectedAppId" placeholder="选择应用" style="width: 260px" @change="loadCards">
          <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
        </el-select>
        <el-button :loading="loading" @click="loadCards">刷新</el-button>
      </div>
    </div>
    <el-card shadow="never">
      <el-table :data="cards" v-loading="loading" border stripe>
        <el-table-column prop="kami_code" label="卡密" min-width="220" show-overflow-tooltip />
        <el-table-column prop="batch_no" label="批次" min-width="150" show-overflow-tooltip />
        <el-table-column prop="kami_type" label="类型" width="100" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getMerchantApps, getMerchantKamis } from '../api/merchant'

const loading = ref(false)
const apps = ref([])
const cards = ref([])
const selectedAppId = ref('')

async function loadApps() {
  const res = await getMerchantApps()
  apps.value = res.data || []
  if (!selectedAppId.value && apps.value.length) selectedAppId.value = apps.value[0].app_id
}

async function loadCards() {
  if (!selectedAppId.value) {
    cards.value = []
    return
  }
  loading.value = true
  try {
    const res = await getMerchantKamis(selectedAppId.value)
    cards.value = res.data || []
  } finally {
    loading.value = false
  }
}

async function init() {
  await loadApps()
  await loadCards()
}

onMounted(init)
</script>

<style scoped>
.list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar,
.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}
</style>
