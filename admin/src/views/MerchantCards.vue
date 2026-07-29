<template>
  <div class="list-page merchant-cards-page">
    <div class="page-toolbar">
      <h2>我的卡密</h2>
      <div class="actions">
        <el-button type="primary" :icon="VideoPlay" @click="openSdkTest">SDK 测试</el-button>
        <el-button type="primary" :icon="Plus" @click="goGenerateKamis">生成卡密</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadCards">刷新</el-button>
      </div>
    </div>

    <div class="filter-strip">
      <el-select v-model="query.app_id" placeholder="全部应用" clearable class="filter-control" @change="handleAppChange">
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

    <el-dialog v-model="generateDialogVisible" title="生成卡密" width="640px">
      <el-alert
        v-if="generateForm.app_id && batchStats.length === 0"
        title="当前应用暂无可追加的批次，需先在批次管理中按规格生成批次。"
        type="warning"
        :closable="false"
        show-icon
        class="generate-alert"
      />
      <el-form :model="generateForm" label-width="112px">
        <el-form-item label="应用">
          <el-select v-model="generateForm.app_id" disabled style="width: 100%">
            <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择批次" required>
          <el-select v-model="generateForm.batch_no" placeholder="请选择批次" style="width: 100%">
            <el-option
              v-for="batch in batchStats"
              :key="batch.batch_no"
              :label="`${batch.batch_no} / ${getTypeText(batch.kami_type)} / ${getBatchConfigText(batch)}`"
              :value="batch.batch_no"
              :disabled="batch.can_append === false"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedBatch" label="批次配置">
          <div class="batch-summary">
            {{ getTypeText(selectedBatch.kami_type) }} /
            {{ getBatchConfigText(selectedBatch) }} /
            {{ getMachineBindModeText(selectedBatch.machine_bind_mode, selectedBatch.max_bind_devices) }}
          </div>
        </el-form-item>
        <el-form-item label="生成数量" required>
          <el-input-number v-model="generateForm.count" :min="1" :max="1000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="卡密前缀">
          <el-input v-model="generateForm.code_prefix" maxlength="32" placeholder="例如：VIP-" />
        </el-form-item>
        <el-form-item label="随机长度" required>
          <el-input-number v-model="generateForm.code_length" :min="4" :max="64" style="width: 100%" />
        </el-form-item>
        <el-form-item label="字符集" required>
          <el-select v-model="generateForm.charset" style="width: 100%">
            <el-option v-for="item in charsetOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="格式预览">
          <div class="code-preview">{{ codePreview }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="generating"
          :disabled="!selectedBatch || selectedBatch.can_append === false"
          @click="handleGenerate"
        >
          生成
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download, Plus, Refresh, Search, VideoPlay } from '@element-plus/icons-vue'
import {
  appendMerchantBatchKamis,
  exportMerchantKamis,
  getMerchantApps,
  getMerchantBatches,
  getMerchantKamis
} from '../api/merchant'
import { formatBeijingTime } from '../utils/datetime'
import { getMachineBindModeText, getTypeText, getValidityText } from '../utils/kamiDisplay'

const route = useRoute()
const loading = ref(false)
const exporting = ref(false)
const generating = ref(false)
const apps = ref([])
const batchStats = ref([])
const cards = ref([])
const total = ref(0)
const generateDialogVisible = ref(false)

const query = reactive({
  app_id: '',
  keyword: '',
  status: '',
  batch_no: '',
  page: 1,
  page_size: 20
})

const generateForm = reactive({
  app_id: '',
  batch_no: '',
  count: 10,
  code_prefix: '',
  code_length: 16,
  charset: 'upper_numeric'
})

const charsetOptions = [
  { label: '大写字母 + 数字', value: 'upper_numeric', sample: 'A1B2C3D4E5F6G7H8' },
  { label: '纯数字', value: 'numeric', sample: '1234567890123456' },
  { label: '大写字母', value: 'upper', sample: 'ABCDEFGHJKLMNPQR' },
  { label: '大小写字母 + 数字', value: 'lower_mixed', sample: 'aB3dE5fG7hJ9kLmN' }
]

async function loadBatchStats() {
  if (!query.app_id) {
    batchStats.value = []
    generateForm.batch_no = ''
    return
  }
  const res = await getMerchantBatches(query.app_id)
  batchStats.value = Array.isArray(res.data) ? res.data : (res.data?.items || res.items || [])
  if (generateForm.batch_no && !batchStats.value.some((item) => item.batch_no === generateForm.batch_no)) {
    generateForm.batch_no = ''
  }
}

const selectedBatch = computed(() => batchStats.value.find((item) => item.batch_no === generateForm.batch_no))

const codePreview = computed(() => {
  const option = charsetOptions.find((item) => item.value === generateForm.charset) || charsetOptions[0]
  const suffix = option.sample.repeat(Math.ceil(generateForm.code_length / option.sample.length)).slice(0, generateForm.code_length)
  return `${generateForm.code_prefix || ''}${suffix}`
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

function applyRouteQuery() {
  const routeAppId = route.query.app_id ? String(route.query.app_id) : ''
  const routeBatchNo = route.query.batch_no ? String(route.query.batch_no) : ''
  if (routeAppId && apps.value.some((app) => app.app_id === routeAppId)) query.app_id = routeAppId
  if (routeBatchNo) query.batch_no = routeBatchNo
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

async function handleAppChange() {
  query.batch_no = ''
  query.page = 1
  generateForm.batch_no = ''
  await loadBatchStats()
  await loadCards()
}

function handleSearch() {
  query.page = 1
  loadCards()
}

async function handleReset() {
  query.app_id = ''
  query.keyword = ''
  query.status = ''
  query.batch_no = ''
  query.page = 1
  batchStats.value = []
  generateForm.batch_no = ''
  await loadCards()
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

function openSdkTest() {
  if (!query.app_id) {
    ElMessage.warning('请先选择应用')
    return
  }
  const url = new URL(`${import.meta.env.BASE_URL}sdk/js_example.html`, window.location.origin)
  url.searchParams.set('app_id', query.app_id)
  window.open(url.toString(), '_blank', 'noopener,noreferrer')
}

async function goGenerateKamis() {
  if (!query.app_id) {
    ElMessage.warning('请先选择应用')
    return
  }
  generateForm.app_id = query.app_id
  generateForm.batch_no = query.batch_no || ''
  generateForm.count = 10
  generateForm.code_prefix = ''
  generateForm.code_length = 16
  generateForm.charset = 'upper_numeric'
  await loadBatchStats()
  generateDialogVisible.value = true
}

async function handleGenerate() {
  if (!generateForm.app_id || !generateForm.batch_no || !selectedBatch.value) {
    ElMessage.warning('请选择批次')
    return
  }
  if (selectedBatch.value.can_append === false) {
    ElMessage.warning('该批次不可追加卡密')
    return
  }
  generating.value = true
  try {
    const res = await appendMerchantBatchKamis(selectedBatch.value.id, {
      count: generateForm.count,
      code_prefix: generateForm.code_prefix || null,
      code_length: generateForm.code_length,
      charset: generateForm.charset
    })
    ElMessage.success(`成功生成 ${res.data.count} 个卡密`)
    query.app_id = generateForm.app_id
    query.batch_no = generateForm.batch_no
    query.page = 1
    generateDialogVisible.value = false
    await Promise.all([loadBatchStats(), loadCards()])
  } finally {
    generating.value = false
  }
}

function getBatchConfigText(batch) {
  if (!batch) return '-'
  if (batch.kami_type === 'points') return `面额 ${batch.points_amount || 0} 积分`
  if (batch.kami_type === 'times') return `${batch.times_total || 0}次`
  return getValidityText(batch)
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
  applyRouteQuery()
  if (query.app_id) await loadBatchStats()
  await loadCards()
  if (route.query.action === 'generate') await goGenerateKamis()
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

.generate-alert {
  margin-bottom: 14px;
}

.batch-summary,
.code-preview {
  width: 100%;
  min-height: 32px;
  padding: 8px 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  line-height: 1.5;
}

.code-preview {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 700;
  word-break: break-all;
}

@media (max-width: 720px) {
  .filter-control,
  .search-control,
  .filter-strip :deep(.el-button) {
    width: 100%;
  }
}
</style>
