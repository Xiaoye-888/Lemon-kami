<template>
  <div class="list-page">
    <div class="page-toolbar">
      <h2>我的卡密</h2>
      <div class="actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadCards">刷新</el-button>
      </div>
    </div>

    <div class="filter-strip">
      <el-select v-model="query.app_id" placeholder="全部应用" clearable class="filter-control" @change="handleSearch">
        <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
      </el-select>
      <el-input
        v-model="query.keyword"
        placeholder="搜索卡密/应用/批次号"
        clearable
        class="search-control"
        @keyup.enter="handleSearch"
      />
      <el-select v-model="query.status" placeholder="全部状态" clearable class="filter-control" @change="handleSearch">
        <el-option label="未使用" value="unused" />
        <el-option label="已激活" value="active" />
        <el-option label="已冻结" value="frozen" />
        <el-option label="已过期" value="expired" />
      </el-select>
      <el-input
        v-model="query.batch_no"
        placeholder="批次号"
        clearable
        class="filter-control"
        @keyup.enter="handleSearch"
      />
      <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
      <el-button @click="handleReset">重置</el-button>
      <el-button :icon="Download" :loading="exporting" @click="handleExport">导出</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="cards" v-loading="loading" border stripe>
        <el-table-column prop="kami_code" label="卡密" min-width="220" show-overflow-tooltip />
        <el-table-column prop="app_name" label="应用" min-width="140" show-overflow-tooltip />
        <el-table-column prop="batch_no" label="批次号" min-width="150" show-overflow-tooltip />
        <el-table-column prop="kami_type" label="类型" width="100" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="bound_device_count" label="绑定设备" width="100" />
        <el-table-column prop="activate_time" label="激活时间" width="170">
          <template #default="{ row }">{{ formatOptionalTime(row.activate_time) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pager"
        @size-change="loadCards"
        @current-change="loadCards"
      />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Download, Refresh, Search } from '@element-plus/icons-vue'
import { exportMerchantKamis, getMerchantApps, getMerchantKamis } from '../api/merchant'
import { formatBeijingTime } from '../utils/datetime'

const loading = ref(false)
const exporting = ref(false)
const apps = ref([])
const cards = ref([])
const total = ref(0)
const query = reactive({
  app_id: '',
  keyword: '',
  status: '',
  batch_no: '',
  page: 1,
  page_size: 20
})

const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

function normalizedParams(includePage = true) {
  const params = {}
  for (const key of ['app_id', 'keyword', 'status', 'batch_no']) {
    if (query[key]) params[key] = query[key]
  }
  if (includePage) {
    params.page = query.page
    params.page_size = query.page_size
  }
  return params
}

async function loadApps() {
  const res = await getMerchantApps()
  apps.value = res.data || []
}

async function loadCards() {
  loading.value = true
  try {
    const res = await getMerchantKamis(normalizedParams())
    cards.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  loadCards()
}

function handleReset() {
  query.app_id = ''
  query.keyword = ''
  query.status = ''
  query.batch_no = ''
  query.page = 1
  loadCards()
}

async function handleExport() {
  exporting.value = true
  try {
    const response = await exportMerchantKamis(normalizedParams(false))
    downloadBlob(response.data, 'merchant-kamis.csv')
  } finally {
    exporting.value = false
  }
}

function downloadBlob(data, filename) {
  const blob = new Blob([data], { type: 'text/csv;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
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
.actions,
.filter-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.page-toolbar {
  justify-content: space-between;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}

.filter-control {
  width: 160px;
}

.search-control {
  width: 240px;
}

.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

@media (max-width: 720px) {
  .filter-control,
  .search-control,
  .filter-strip :deep(.el-button) {
    width: 100%;
  }
}
</style>
