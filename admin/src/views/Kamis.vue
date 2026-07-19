<template>
  <div class="kamis-page">
    <section class="yz-admin-panel">
      <div class="yz-panel-header">
        <div class="yz-panel-title">
          <el-icon><Key /></el-icon>
          <span>卡密列表</span>
        </div>
        <div class="panel-actions">
          <el-button :icon="VideoPlay" :disabled="!queryParams.app_id" @click="openSdkTestScene">
            SDK 测试
          </el-button>
          <el-button :icon="Download" @click="handleExportKamis">导出</el-button>
          <el-button type="danger" plain :disabled="selectedKamis.length === 0" @click="handleDeleteSelected">
            删除选中
          </el-button>
          <el-button type="primary" :icon="Plus" @click="showGenerateDialog">生成卡密</el-button>
        </div>
      </div>

      <div class="quick-filter-band">
        <span class="quick-label">快捷筛选：</span>
        <el-button :type="!queryParams.status ? 'primary' : ''" @click="setStatusFilter('')">全部</el-button>
        <el-button :type="queryParams.status === 'unused' ? 'success' : ''" plain @click="setStatusFilter('unused')">
          未使用
        </el-button>
        <el-button :type="queryParams.status === 'active' ? 'warning' : ''" plain @click="setStatusFilter('active')">
          已使用
        </el-button>
        <el-button :type="queryParams.status === 'frozen' ? 'danger' : ''" plain @click="setStatusFilter('frozen')">
          已冻结
        </el-button>
        <span class="divider"></span>
        <el-button :type="quickDate === 'today' ? 'primary' : ''" plain @click="setDateFilter('today')">
          今日创建
        </el-button>
        <el-button :type="quickDate === 'week' ? 'primary' : ''" plain @click="setDateFilter('week')">
          本周创建
        </el-button>
      </div>

      <div class="yz-filter-strip">
        <el-select v-model="queryParams.app_id" placeholder="选择应用" class="filter-control" @change="handleAppChange">
          <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
        </el-select>
        <el-select v-model="queryParams.status" placeholder="全部状态" clearable class="filter-control" @change="loadKamis">
          <el-option label="未使用" value="unused" />
          <el-option label="已使用" value="active" />
          <el-option label="已冻结" value="frozen" />
        </el-select>
        <el-select v-model="queryParams.spec_id" placeholder="全部规格" clearable class="filter-control" @change="handleSpecChange">
          <el-option v-for="spec in specStats" :key="spec.id" :label="getSpecOptionLabel(spec)" :value="spec.id" />
        </el-select>
        <el-select v-model="queryParams.batch_no" placeholder="全部批次" clearable class="filter-control" @change="handleBatchChange">
          <el-option v-for="batch in batchStats" :key="batch.batch_no" :label="batch.batch_no" :value="batch.batch_no" />
        </el-select>
        <el-select v-model="queryParams.kami_type" placeholder="全部类型" clearable class="filter-control" @change="loadKamis">
          <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-input
          v-model="queryParams.keyword"
          placeholder="搜索卡密/用户/备注"
          clearable
          class="search-control"
          @keyup.enter="loadKamis"
        />
        <el-button type="primary" :icon="Search" @click="loadKamis" />
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>

      <div v-if="queryParams.app_id && batchStats.length === 0" class="batch-required-notice">
        当前应用暂无批次，卡密必须绑定批次后才能生成。
      </div>

      <div v-if="queryParams.batch_no" class="current-batch-bar">
        <span>当前批次：{{ queryParams.batch_no }}</span>
        <div>
          <el-button link type="primary" @click="goCurrentBatch">进入批次详情</el-button>
          <el-button link @click="clearBatchFilter">查看全部卡密</el-button>
        </div>
      </div>
      <div v-else-if="queryParams.spec_id && currentSpec" class="current-batch-bar">
        <span>当前规格：{{ currentSpec.spec_name }}</span>
        <div>
          <el-button link type="primary" @click="goCurrentSpec">进入规格详情</el-button>
          <el-button link @click="clearSpecFilter">查看全部卡密</el-button>
        </div>
      </div>

      <el-empty v-if="!queryParams.app_id" description="请先选择应用" />
      <el-table
        v-else
        :data="filteredKamis"
        v-loading="loading"
        row-key="kami_code"
        class="yz-clean-table"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column label="卡密" min-width="230">
          <template #default="{ row }">
            <div class="code-cell">
              <span class="mono-text">{{ row.kami_code }}</span>
              <el-tooltip content="复制卡密" placement="top">
                <el-button :icon="DocumentCopy" size="small" circle @click="copyToClipboard(row.kami_code)" />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag type="primary" round>{{ getTypeText(row.kami_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="批次" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.batch_no || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" round>{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="绑定关系" width="120">
          <template #default="{ row }">{{ row.binding_relation || '-' }}</template>
        </el-table-column>
        <el-table-column label="机器码绑定" width="150">
          <template #default="{ row }">
            {{ row.machine_bind_mode_text || getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices) }}
            <span v-if="row.device_bind_count">({{ row.device_bind_count }})</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ row.created_at ? formatBeijingTime(row.created_at) : '-' }}</template>
        </el-table-column>
        <el-table-column label="使用用户" min-width="130">
          <template #default="{ row }">{{ getKamiUserText(row) }}</template>
        </el-table-column>
        <el-table-column label="卡密额度" width="140">
          <template #default="{ row }">{{ getCardQuotaText(row) }}</template>
        </el-table-column>
        <el-table-column label="绑定设备" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ getBoundDeviceText(row) }}</template>
        </el-table-column>
        <el-table-column label="兑换时间" width="180">
          <template #default="{ row }">{{ formatOptionalTime(row.redeemed_at) }}</template>
        </el-table-column>
        <el-table-column label="备注" min-width="160">
          <template #default="{ row }">{{ row.remark || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-tooltip v-if="row.status !== 'frozen'" content="冻结卡密" placement="top">
              <el-button class="icon-action danger" :icon="CircleClose" @click="handleFreeze(row)" />
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <span>共 {{ filteredTotal }} 条</span>
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="sizes, prev, pager, next, jumper"
          @size-change="loadKamis"
          @current-change="loadKamis"
        />
      </div>
    </section>

    <el-dialog v-model="generateDialogVisible" title="生成卡密" width="640px">
      <el-alert
        v-if="generateForm.app_id && batchStats.length === 0"
        title="当前应用暂无批次，需先在批次管理中创建规格并生成批次。"
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
          :disabled="batchStats.length === 0 || !generateForm.batch_no"
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
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CircleClose,
  DocumentCopy,
  Download,
  Key,
  Plus,
  Refresh,
  Search,
  VideoPlay
} from '@element-plus/icons-vue'
import { batchCreateKamis, deleteKamis, exportKamis, freezeKami, getKamiBatches, getKamiSpecs, getKamis } from '../api/kami'
import { getApps } from '../api/admin'
import { copyTextToClipboard } from '../utils/clipboard'
import { formatBeijingTime } from '../utils/datetime'
import {
  TYPE_OPTIONS,
  getMachineBindModeText,
  getSpecBenefitText,
  getSpecPolicyText,
  getStatusText,
  getStatusType,
  getTypeText,
  getValidityText
} from '../utils/kamiDisplay'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const generating = ref(false)
const kamis = ref([])
const selectedKamis = ref([])
const batchStats = ref([])
const specStats = ref([])
const apps = ref([])
const total = ref(0)
const quickDate = ref('')
const generateDialogVisible = ref(false)

const typeOptions = TYPE_OPTIONS

const charsetOptions = [
  { label: '大写字母 + 数字', value: 'upper_numeric', sample: 'A1B2C3D4E5F6G7H8' },
  { label: '纯数字', value: 'numeric', sample: '1234567890123456' },
  { label: '大写字母', value: 'upper', sample: 'ABCDEFGHJKLMNPQR' },
  { label: '大小写字母 + 数字', value: 'lower_mixed', sample: 'aB3dE5fG7hJ9kLmN' }
]

const queryParams = reactive({
  app_id: '',
  status: '',
  kami_type: '',
  keyword: '',
  spec_id: '',
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

const selectedBatch = computed(() => batchStats.value.find((item) => item.batch_no === generateForm.batch_no))
const currentSpec = computed(() => specStats.value.find((item) => String(item.id) === String(queryParams.spec_id)))

const codePreview = computed(() => {
  const option = charsetOptions.find((item) => item.value === generateForm.charset) || charsetOptions[0]
  const suffix = option.sample.repeat(Math.ceil(generateForm.code_length / option.sample.length)).slice(0, generateForm.code_length)
  return `${generateForm.code_prefix || ''}${suffix}`
})

const filteredKamis = computed(() => {
  if (!quickDate.value) return kamis.value
  const now = new Date()
  const start = new Date(now)
  if (quickDate.value === 'today') {
    start.setHours(0, 0, 0, 0)
  } else {
    const day = start.getDay() || 7
    start.setDate(start.getDate() - day + 1)
    start.setHours(0, 0, 0, 0)
  }
  return kamis.value.filter((item) => item.created_at && new Date(item.created_at) >= start)
})

const filteredTotal = computed(() => (quickDate.value ? filteredKamis.value.length : total.value))

const loadApps = async () => {
  try {
    const res = await getApps()
    apps.value = res.data || []
    if (route.query.app_id) queryParams.app_id = String(route.query.app_id)
    if (route.query.spec_id) queryParams.spec_id = Number(route.query.spec_id)
    if (route.query.batch_no) queryParams.batch_no = String(route.query.batch_no)
    if (!queryParams.app_id && apps.value.length > 0) queryParams.app_id = apps.value[0].app_id
    await loadKamis()
    openGenerateDialogFromRoute()
  } catch (error) {
    console.error('加载应用失败:', error)
    ElMessage.error('加载应用失败')
  }
}

const handleAppChange = () => {
  queryParams.spec_id = ''
  queryParams.batch_no = ''
  queryParams.page = 1
  selectedKamis.value = []
  loadKamis()
}

const handleSpecChange = () => {
  if (queryParams.spec_id) queryParams.batch_no = ''
  queryParams.page = 1
  selectedKamis.value = []
  loadKamis()
}

const handleBatchChange = () => {
  if (queryParams.batch_no) queryParams.spec_id = ''
  queryParams.page = 1
  selectedKamis.value = []
  loadKamis()
}

const clearBatchFilter = () => {
  queryParams.batch_no = ''
  queryParams.page = 1
  selectedKamis.value = []
  loadKamis()
}

const clearSpecFilter = () => {
  queryParams.spec_id = ''
  queryParams.page = 1
  selectedKamis.value = []
  loadKamis()
}

const setStatusFilter = (status) => {
  queryParams.status = status
  queryParams.page = 1
  selectedKamis.value = []
  loadKamis()
}

const setDateFilter = (value) => {
  quickDate.value = quickDate.value === value ? '' : value
}

const resetFilters = () => {
  queryParams.status = ''
  queryParams.kami_type = ''
  queryParams.keyword = ''
  queryParams.spec_id = ''
  queryParams.batch_no = ''
  queryParams.page = 1
  quickDate.value = ''
  selectedKamis.value = []
  loadKamis()
}

const normalizeKamiParams = () => {
  const params = { ...queryParams }
  if (!params.status) delete params.status
  if (!params.kami_type) delete params.kami_type
  if (!params.keyword) delete params.keyword
  if (!params.spec_id) delete params.spec_id
  if (!params.batch_no) delete params.batch_no
  if (params.batch_no) delete params.spec_id
  return params
}

const loadSpecs = async () => {
  if (!queryParams.app_id) {
    specStats.value = []
    return
  }
  const params = { app_id: queryParams.app_id }
  if (queryParams.kami_type) params.kami_type = queryParams.kami_type
  const res = await getKamiSpecs(params)
  specStats.value = res.data?.items || []
  if (queryParams.spec_id && !currentSpec.value) queryParams.spec_id = ''
}

const loadBatches = async () => {
  if (!queryParams.app_id) {
    batchStats.value = []
    return
  }
  const res = await getKamiBatches({ app_id: queryParams.app_id })
  batchStats.value = res.data || []
}

const loadKamis = async () => {
  if (!queryParams.app_id) {
    kamis.value = []
    total.value = 0
    batchStats.value = []
    specStats.value = []
    return
  }

  loading.value = true
  try {
    await loadSpecs()
    await loadBatches()
    const res = await getKamis(normalizeKamiParams())
    kamis.value = res.data.items || []
    total.value = res.data.total || 0
    selectedKamis.value = []
  } catch (error) {
    console.error('加载卡密失败:', error)
    ElMessage.error('加载卡密失败')
  } finally {
    loading.value = false
  }
}

const showGenerateDialog = () => {
  if (!queryParams.app_id) {
    ElMessage.warning('请先选择应用')
    return
  }
  generateForm.app_id = queryParams.app_id
  generateForm.batch_no = queryParams.batch_no || ''
  generateForm.count = 10
  generateForm.code_prefix = ''
  generateForm.code_length = 16
  generateForm.charset = 'upper_numeric'
  generateDialogVisible.value = true
}

const openGenerateDialogFromRoute = () => {
  if (route.query.action !== 'generate') return
  showGenerateDialog()
  const { action, ...query } = route.query
  router.replace({ path: route.path, query })
}

const openSdkTestScene = () => {
  if (!queryParams.app_id) {
    ElMessage.warning('请先选择应用')
    return
  }
  const url = new URL(`${import.meta.env.BASE_URL}sdk/js_example.html`, window.location.origin)
  url.searchParams.set('app_id', queryParams.app_id)
  window.open(url.toString(), '_blank', 'noopener,noreferrer')
}

const handleGenerate = async () => {
  if (!generateForm.app_id || !generateForm.batch_no) {
    ElMessage.warning('请选择批次')
    return
  }
  generating.value = true
  try {
    const res = await batchCreateKamis({
      app_id: generateForm.app_id,
      batch_no: generateForm.batch_no,
      count: generateForm.count,
      code_prefix: generateForm.code_prefix,
      code_length: generateForm.code_length,
      charset: generateForm.charset
    })
    ElMessage.success(`成功生成 ${res.data.count} 个卡密`)
    queryParams.batch_no = generateForm.batch_no
    queryParams.page = 1
    generateDialogVisible.value = false
    await loadKamis()
  } catch (error) {
    console.error('生成卡密失败:', error)
  } finally {
    generating.value = false
  }
}

const handleExportKamis = async () => {
  if (!queryParams.app_id) {
    ElMessage.warning('请先选择应用')
    return
  }
  const params = { app_id: queryParams.app_id }
  if (queryParams.status) params.status = queryParams.status
  if (queryParams.spec_id && !queryParams.batch_no) params.spec_id = queryParams.spec_id
  if (queryParams.batch_no) params.batch_no = queryParams.batch_no
  if (queryParams.kami_type) params.kami_type = queryParams.kami_type
  const response = await exportKamis(params)
  downloadBlob(response, `kamis_${queryParams.app_id}_${queryParams.batch_no || (queryParams.spec_id ? `spec_${queryParams.spec_id}` : 'all')}.csv`)
}

const downloadBlob = (response, filename) => {
  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

const handleSelectionChange = (selection) => {
  selectedKamis.value = selection
}

const handleDeleteSelected = async () => {
  if (!queryParams.app_id || selectedKamis.value.length === 0) return
  const count = selectedKamis.value.length
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${count} 个卡密吗？请先确认这些卡密的授权、积分、次数或使用记录已经迁移，删除后不可恢复。`,
      '确认删除卡密',
      {
        type: 'warning',
        confirmButtonText: '已迁移并确认删除',
        cancelButtonText: '取消'
      }
    )
    const payload = {
      app_id: queryParams.app_id,
      kami_codes: selectedKamis.value.map((item) => item.kami_code)
    }
    if (queryParams.spec_id && !queryParams.batch_no) payload.spec_id = queryParams.spec_id
    if (queryParams.batch_no) payload.batch_no = queryParams.batch_no
    const res = await deleteKamis(payload)
    const data = res.data
    ElMessage.success(`已删除 ${data.deleted_count} 个，未处理 ${data.skipped_count} 个`)
    await loadKamis()
  } catch (error) {
    if (error !== 'cancel') console.error('删除卡密失败:', error)
  }
}

const handleFreeze = async (row) => {
  try {
    await ElMessageBox.confirm('确定要冻结该卡密吗？', '冻结卡密', { type: 'warning' })
    await freezeKami(row.kami_code)
    ElMessage.success('冻结成功')
    await loadKamis()
  } catch (error) {
    if (error !== 'cancel') console.error('冻结失败:', error)
  }
}

const goCurrentBatch = () => {
  router.push({ path: '/kamis/batches', query: { app_id: queryParams.app_id, batch_no: queryParams.batch_no } })
}

const goCurrentSpec = () => {
  router.push({ path: '/kamis/batches', query: { app_id: queryParams.app_id, spec_id: queryParams.spec_id } })
}

const copyToClipboard = async (text) => {
  try {
    await copyTextToClipboard(text)
    ElMessage.success('复制成功')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const getBatchConfigText = (batch) => {
  if (!batch) return '-'
  if (batch.kami_type === 'points') return `面额 ${batch.points_amount || 0} 积分`
  if (batch.kami_type === 'times') return `${batch.times_total || 0}次`
  return getValidityText(batch)
}

const getSpecOptionLabel = (spec) => {
  const policy = getSpecPolicyText(spec)
  return `${spec.spec_name} / ${getTypeText(spec.kami_type)} / ${getSpecBenefitText(spec)} / ${policy}`
}

const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

const getKamiUserText = (row) => (
  row?.redeemed_user?.username ||
  row?.redeemed_user?.email ||
  row?.redeemed_by_user_id ||
  '-'
)

const getCardQuotaText = (row) => {
  if (row.kami_type === 'points') return `${row.points_amount || 0}积分`
  if (row.kami_type === 'times') return `${row.times_total || 0}次`
  return getValidityText(row)
}

const getBoundDeviceText = (row) => {
  if (row?.authorization_owner === 'user' || row?.binding_relation === '用户授权') return '-'
  if (row?.bind_uuid) return row.bind_uuid
  if (row?.device_bind_count) return `${row.device_bind_count} 台设备`
  return '-'
}

onMounted(loadApps)
</script>

<style scoped>
.kamis-page {
  min-height: 100%;
}

.kamis-page :deep(.el-button--primary:not(.is-plain)) {
  background: #2f80ed !important;
  border-color: #2f80ed !important;
}

.kamis-page :deep(.el-button--primary:not(.is-plain):hover) {
  background: #1d4ed8 !important;
  border-color: #1d4ed8 !important;
}

.yz-admin-panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.yz-panel-header {
  min-height: 94px;
  padding: 24px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.yz-panel-title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #0f172a;
  font-size: 24px;
  font-weight: 700;
}

.panel-actions,
.quick-filter-band,
.yz-filter-strip,
.current-batch-bar,
.code-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.quick-filter-band {
  min-height: 86px;
  padding: 18px 28px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.quick-label {
  color: #334155;
  font-weight: 600;
}

.divider {
  width: 1px;
  height: 28px;
  background: #94a3b8;
  margin: 0 6px;
}

.yz-filter-strip {
  padding: 18px 28px;
  background: #f8fafc;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.filter-control {
  width: 170px;
}

.search-control {
  width: 270px;
}

.batch-required-notice,
.current-batch-bar {
  margin: 14px 28px 0;
  padding: 12px 14px;
  border-radius: 8px;
  background: #eef7ff;
  color: #1d4ed8;
}

.current-batch-bar {
  justify-content: space-between;
  background: #eff6ff;
  color: #1e40af;
}

.yz-clean-table {
  width: 100%;
  margin-top: 14px;
}

.yz-clean-table :deep(.el-table__header th) {
  height: 54px;
  background: #f8fafc;
  color: #58708c;
  font-size: 15px;
  font-weight: 700;
}

.yz-clean-table :deep(.el-table__row) {
  height: 74px;
}

.mono-text,
.code-preview {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  word-break: break-all;
}

.code-preview {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #0f172a;
}

.usage-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  line-height: 1.45;
}

.icon-action {
  width: 36px;
  height: 36px;
  padding: 0;
}

.icon-action.danger {
  border-color: #ef4444;
  color: #ef4444;
}

.table-footer {
  min-height: 72px;
  padding: 16px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  color: #475569;
}

.batch-summary {
  width: 100%;
  color: #475569;
  line-height: 1.5;
}

.generate-alert {
  margin-bottom: 16px;
}

html.dark .yz-panel-title {
  color: #e5e7eb;
}

html.dark .yz-filter-strip,
html.dark .yz-clean-table :deep(.el-table__header th),
html.dark .code-preview {
  background: #111827;
}

@media (max-width: 780px) {
  .yz-panel-header,
  .table-footer,
  .current-batch-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .filter-control,
  .search-control {
    width: 100%;
  }
}
</style>
