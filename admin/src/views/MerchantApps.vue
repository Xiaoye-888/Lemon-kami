<template>
  <div class="list-page">
    <div class="page-toolbar">
      <h2>我的应用</h2>
      <div class="actions">
        <el-input v-model="newAppName" placeholder="应用名称" style="width: 220px" />
        <el-button type="primary" :loading="creating" @click="handleCreateApp">新建应用</el-button>
        <el-button :loading="loading" @click="loadApps">刷新</el-button>
      </div>
    </div>
    <el-card shadow="never">
      <el-table :data="apps" v-loading="loading" border stripe>
        <el-table-column prop="name" label="应用名称" min-width="160" />
        <el-table-column prop="app_id" label="App ID" min-width="190" show-overflow-tooltip />
        <el-table-column label="来源" width="120">
          <template #default="{ row }">{{ row.is_owned ? '自建应用' : '授权应用' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">{{ row.status === 1 ? '启用' : '停用' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createMerchantApp, getMerchantApps } from '../api/merchant'

const loading = ref(false)
const creating = ref(false)
const apps = ref([])
const newAppName = ref('')

async function loadApps() {
  loading.value = true
  try {
    const res = await getMerchantApps()
    apps.value = res.data || []
  } finally {
    loading.value = false
  }
}

async function handleCreateApp() {
  if (!newAppName.value.trim()) {
    ElMessage.warning('请输入应用名称')
    return
  }
  creating.value = true
  try {
    await createMerchantApp({ name: newAppName.value.trim() })
    ElMessage.success('应用已创建')
    newAppName.value = ''
    await loadApps()
  } finally {
    creating.value = false
  }
}

onMounted(loadApps)
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
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}
</style>
