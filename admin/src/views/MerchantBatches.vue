<template>
  <div class="batch-page">
    <div class="page-toolbar">
      <div>
        <h2>批次管理</h2>
        <p>按应用规格生成、查看和导出自己的卡密</p>
      </div>
      <div class="toolbar-actions">
        <el-select v-model="queryParams.app_id" placeholder="选择应用" style="width: 260px" @change="handleAppChange">
          <el-option
            v-for="app in apps"
            :key="app.app_id"
            :label="`${app.name} / ${app.is_owned ? '自建应用' : '授权应用'}`"
            :value="app.app_id"
          />
        </el-select>
        <el-tag v-if="selectedApp" :type="selectedApp.is_owned ? 'success' : 'info'" effect="plain">
          {{ selectedApp.is_owned ? '自建应用' : '授权应用' }}
        </el-tag>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="lowBalanceWarning"
      class="quota-warning"
      type="warning"
      :closable="false"
      show-icon
      title="低额度提醒"
      :description="`当前发卡额度 ${issueCardQuota.balance}，低于预警值 ${issueCardQuota.warning_threshold}`"
    />

    <section class="spec-workbench">
      <el-card shadow="never" class="panel spec-panel">
        <template #header>
          <div class="panel-header">
            <span>规格信息</span>
            <el-button v-if="selectedApp?.is_owned" type="primary" @click="openSpecDialog()">新建规格</el-button>
          </div>
        </template>

        <el-table
          :data="specRows"
          v-loading="loading"
          border
          stripe
          highlight-current-row
          @row-click="selectSpec"
        >
          <el-table-column prop="spec_name" label="规格名称" min-width="150" show-overflow-tooltip />
          <el-table-column label="权益" min-width="160">
            <template #default="{ row }">{{ specValueText(row) }}</template>
          </el-table-column>
          <el-table-column prop="spec_group" label="分组" width="90" />
          <el-table-column prop="machine_bind_mode" label="绑定策略" width="150" />
          <el-table-column label="统计" min-width="210">
            <template #default="{ row }">
              <span>批次 {{ row.batch_count || 0 }}</span>
              <span class="stat-inline">总卡 {{ row.total_count || 0 }}</span>
              <span class="stat-inline">未用 {{ row.unused_count || 0 }}</span>
              <span class="stat-inline">激活 {{ row.active_count || 0 }}</span>
              <span class="stat-inline">冻结 {{ row.frozen_count || 0 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">{{ row.status === 1 ? '启用' : '停用' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="openGenerateDialog(row)">生成批次</el-button>
              <el-button v-if="row.is_editable" link type="primary" @click.stop="openSpecDialog(row)">编辑</el-button>
              <el-button v-if="row.is_editable" link type="danger" @click.stop="deleteSpec(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="panel detail-panel">
        <template #header>
          <div class="panel-header">
            <span>{{ selectedSpec?.spec_name || '规格详情' }}</span>
            <el-tag v-if="selectedSpec" effect="plain">单张成本 {{ issuePreview?.unit_cost || '-' }}</el-tag>
          </div>
        </template>

        <div v-if="selectedSpec" class="spec-summary">
          <div>
            <span>类型</span>
            <strong>{{ selectedSpec.kami_type }}</strong>
          </div>
          <div>
            <span>规则</span>
            <strong>{{ pricingLabel(issuePreview?.pricing_source) }}</strong>
          </div>
          <div>
            <span>当前额度</span>
            <strong>{{ issueCardQuota.balance }}</strong>
          </div>
        </div>
        <el-empty v-else description="请选择规格" />

        <el-tabs v-if="selectedSpec" v-model="activeTab" class="detail-tabs">
          <el-tab-pane label="批次列表" name="batches">
            <el-table :data="specBatches" border stripe>
              <el-table-column prop="batch_no" label="批次号" min-width="160" show-overflow-tooltip />
              <el-table-column prop="count" label="数量" width="80" />
              <el-table-column prop="stats.unused_count" label="未用" width="72" />
              <el-table-column prop="stats.active_count" label="激活" width="72" />
              <el-table-column prop="stats.frozen_count" label="冻结" width="72" />
              <el-table-column prop="stats.device_bound_count" label="绑定设备" width="96" />
              <el-table-column prop="total_issue_cost" label="消耗额度" width="96" />
              <el-table-column label="操作" width="110">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openBatchDrawer(row)">卡密</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="卡密列表" name="kamis">
            <el-table :data="specKamis.items" border stripe>
              <el-table-column prop="kami_code" label="卡密" min-width="180" show-overflow-tooltip />
              <el-table-column prop="batch_no" label="批次号" min-width="150" show-overflow-tooltip />
              <el-table-column prop="status" label="状态" width="90" />
              <el-table-column prop="created_at" label="创建时间" width="170" />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </section>

    <el-dialog v-model="specDialogVisible" :title="editingSpec ? '编辑规格' : '新建规格'" width="560px">
      <el-form :model="specForm" label-width="104px">
        <el-form-item label="卡密类型" required>
          <el-select v-model="specForm.kami_type" style="width: 100%">
            <el-option label="积分卡" value="points" />
            <el-option label="次数卡" value="times" />
            <el-option label="月卡" value="month" />
            <el-option label="永久卡" value="lifetime" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="specForm.kami_type === 'points'" label="积分面额" required>
          <el-input-number v-model="specForm.points_amount" :min="1" :max="100000000" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="specForm.kami_type === 'points'" label="有效天数">
          <el-input-number v-model="specForm.points_valid_days" :min="1" :max="36500" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="specForm.kami_type === 'times'" label="次数" required>
          <el-input-number v-model="specForm.times_total" :min="1" :max="100000000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="绑定策略">
          <el-select v-model="specForm.machine_bind_mode" style="width: 100%">
            <el-option label="一卡一机" value="one_card_one_device" />
            <el-option label="一卡多机" value="one_card_multi_device" />
            <el-option label="不限制" value="no_limit" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="specForm.machine_bind_mode === 'one_card_multi_device'" label="设备数量">
          <el-input-number v-model="specForm.max_bind_devices" :min="2" :max="1000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="specForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="specForm.remark" type="textarea" :rows="2" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="specDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingSpec" @click="saveSpec">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="generateDialogVisible" title="生成批次" width="520px">
      <div v-if="selectedSpec" class="issue-preview">
        <div>
          本次预计消耗 {{ issuePreview?.total_cost || 0 }} 发卡额度，生成后余额 {{ issuePreview?.balance_after ?? '-' }}
        </div>
        <div>单张消耗 {{ issuePreview?.unit_cost || '-' }}，规则 {{ pricingLabel(issuePreview?.pricing_source) }}</div>
        <el-tag :type="issuePreview?.can_issue ? 'success' : 'danger'">
          {{ issuePreview?.can_issue ? '额度充足' : '额度不足' }}
        </el-tag>
      </div>
      <el-form :model="generateForm" label-width="92px">
        <el-form-item label="批次号">
          <el-input v-model="generateForm.batch_no" placeholder="可留空自动生成" />
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="generateForm.count" :min="1" :max="1000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="前缀">
          <el-input v-model="generateForm.code_prefix" maxlength="32" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="issuing" :disabled="!canIssue" @click="handleIssue">生成卡密</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="batchDrawerVisible" title="批次卡密" size="720px">
      <el-table :data="batchKamis.items" border stripe>
        <el-table-column prop="kami_code" label="卡密" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="created_at" label="创建时间" width="170" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createMerchantAppSpec,
  deleteMerchantAppSpec,
  getMerchantAppSpecs,
  getMerchantApps,
  getMerchantBatchKamis,
  getMerchantQuotas,
  getMerchantSpecBatches,
  getMerchantSpecKamis,
  issueMerchantKamis,
  previewMerchantKamis,
  updateMerchantAppSpec
} from '../api/merchant'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const savingSpec = ref(false)
const issuing = ref(false)
const previewLoading = ref(false)
const apps = ref([])
const specRows = ref([])
const selectedSpec = ref(null)
const specBatches = ref([])
const specKamis = ref({ items: [], total: 0 })
const batchKamis = ref({ items: [], total: 0 })
const selectedBatch = ref(null)
const activeTab = ref('batches')
const specDialogVisible = ref(false)
const generateDialogVisible = ref(false)
const batchDrawerVisible = ref(false)
const editingSpec = ref(null)
const issuePreview = ref(null)
const issueCardQuota = ref({
  balance: 0,
  warning_threshold: 0,
  low_balance_warning: false
})

const queryParams = reactive({
  app_id: ''
})

const specForm = reactive({
  kami_type: 'points',
  points_amount: 100,
  points_valid_days: null,
  times_total: 10,
  machine_bind_mode: 'one_card_one_device',
  max_bind_devices: 2,
  authorization_owner: 'device',
  user_bind_mode: 'none',
  status: 1,
  sort_order: 0,
  remark: ''
})

const generateForm = reactive({
  batch_no: '',
  count: 10,
  code_prefix: '',
  code_length: 16,
  charset: 'upper_numeric'
})

const selectedApp = computed(() => apps.value.find((item) => item.app_id === queryParams.app_id))
const lowBalanceWarning = computed(() => issueCardQuota.value.low_balance_warning)
const canIssueInputs = computed(() => Boolean(selectedApp.value?.app_id && selectedSpec.value?.id && generateForm.count > 0))
const canIssue = computed(() => canIssueInputs.value && issuePreview.value?.can_issue !== false)

function responseItems(res) {
  if (Array.isArray(res.data)) return res.data
  return res.data?.items || res.items || []
}

function responsePayload(res) {
  return res.data?.items ? res.data : { items: res.items || [], total: res.total || 0 }
}

function specValueText(row) {
  if (!row) return '-'
  if (row.kami_type === 'points') return `${row.points_amount || 0} 积分`
  if (row.kami_type === 'times') return `${row.times_total || 0} 次`
  if (row.kami_type === 'lifetime') return '永久卡'
  return `${row.time_value || 1} ${row.time_unit || row.kami_type}`
}

function pricingLabel(value) {
  return {
    user_self_app: '用户自建专属',
    global_self_app: '自建应用默认',
    user_authorized_spec: '用户授权规格专属',
    authorized_spec: '授权规格默认',
    global_authorized_app: '授权应用默认',
    default: '系统默认'
  }[value] || value || '系统默认'
}

function resetSpecForm(row = null) {
  editingSpec.value = row
  specForm.kami_type = row?.kami_type || 'points'
  specForm.points_amount = row?.points_amount || 100
  specForm.points_valid_days = row?.points_valid_days || null
  specForm.times_total = row?.times_total || 10
  specForm.machine_bind_mode = row?.machine_bind_mode || 'one_card_one_device'
  specForm.max_bind_devices = row?.max_bind_devices || 2
  specForm.authorization_owner = row?.authorization_owner || 'device'
  specForm.user_bind_mode = row?.user_bind_mode || 'none'
  specForm.status = row?.status ?? 1
  specForm.sort_order = row?.sort_order || 0
  specForm.remark = row?.remark || ''
}

function specPayload() {
  const payload = {
    kami_type: specForm.kami_type,
    machine_bind_mode: specForm.machine_bind_mode,
    max_bind_devices: specForm.max_bind_devices,
    authorization_owner: specForm.authorization_owner,
    user_bind_mode: specForm.user_bind_mode,
    status: specForm.status,
    sort_order: specForm.sort_order,
    remark: specForm.remark || null
  }
  if (specForm.kami_type === 'points') {
    payload.points_amount = specForm.points_amount
    payload.points_valid_days = specForm.points_valid_days || null
  }
  if (specForm.kami_type === 'times') {
    payload.times_total = specForm.times_total
  }
  return payload
}

function buildIssuePayload() {
  return {
    spec_id: selectedSpec.value?.id,
    count: generateForm.count,
    batch_no: generateForm.batch_no || null,
    code_prefix: generateForm.code_prefix || null,
    code_length: generateForm.code_length,
    charset: generateForm.charset
  }
}

async function loadApps() {
  const res = await getMerchantApps()
  apps.value = res.data || []
  const routeAppId = route.query.app_id ? String(route.query.app_id) : ''
  if (routeAppId && apps.value.some((app) => app.app_id === routeAppId)) {
    queryParams.app_id = routeAppId
  } else if (!queryParams.app_id && apps.value.length) {
    queryParams.app_id = apps.value[0].app_id
  }
}

async function loadQuota() {
  const res = await getMerchantQuotas()
  issueCardQuota.value = res.data?.issue_card || {
    balance: res.data?.kami_issue_balance || 0,
    warning_threshold: 0,
    low_balance_warning: false
  }
}

async function loadSpecs() {
  specRows.value = []
  selectedSpec.value = null
  specBatches.value = []
  specKamis.value = { items: [], total: 0 }
  if (!queryParams.app_id) return
  const res = await getMerchantAppSpecs(queryParams.app_id)
  specRows.value = responseItems(res)
  if (specRows.value.length) {
    await selectSpec(specRows.value[0])
  }
}

async function loadSpecBatches() {
  if (!selectedSpec.value?.id) {
    specBatches.value = []
    return
  }
  const res = await getMerchantSpecBatches(selectedSpec.value.id)
  specBatches.value = responseItems(res)
}

async function loadSpecKamis() {
  if (!selectedSpec.value?.id) {
    specKamis.value = { items: [], total: 0 }
    return
  }
  const res = await getMerchantSpecKamis(selectedSpec.value.id)
  specKamis.value = responsePayload(res)
}

async function loadIssuePreview() {
  if (!canIssueInputs.value) {
    issuePreview.value = null
    return
  }
  previewLoading.value = true
  try {
    const res = await previewMerchantKamis(queryParams.app_id, buildIssuePayload())
    issuePreview.value = res.data || null
  } catch (error) {
    issuePreview.value = null
  } finally {
    previewLoading.value = false
  }
}

async function loadAll() {
  loading.value = true
  try {
    await loadQuota()
    await loadApps()
    await loadSpecs()
  } finally {
    loading.value = false
  }
}

async function handleAppChange() {
  router.replace({ path: '/merchant/batches', query: queryParams.app_id ? { app_id: queryParams.app_id } : {} })
  await loadSpecs()
}

async function selectSpec(row) {
  selectedSpec.value = row
  activeTab.value = 'batches'
  await Promise.all([loadSpecBatches(), loadSpecKamis(), loadIssuePreview()])
}

function openSpecDialog(row = null) {
  if (!selectedApp.value?.is_owned) return
  resetSpecForm(row)
  specDialogVisible.value = true
}

async function saveSpec() {
  if (!selectedApp.value?.app_id) return
  savingSpec.value = true
  try {
    if (editingSpec.value?.id) {
      await updateMerchantAppSpec(selectedApp.value.app_id, editingSpec.value.id, {
        status: specForm.status,
        sort_order: specForm.sort_order,
        remark: specForm.remark || null
      })
      ElMessage.success('规格已更新')
    } else {
      await createMerchantAppSpec(selectedApp.value.app_id, specPayload())
      ElMessage.success('规格已创建')
    }
    specDialogVisible.value = false
    await loadSpecs()
  } finally {
    savingSpec.value = false
  }
}

async function deleteSpec(row) {
  await ElMessageBox.confirm('确认删除该空规格？', '删除规格', { type: 'warning' })
  await deleteMerchantAppSpec(row.app_id, row.id)
  ElMessage.success('规格已删除')
  await loadSpecs()
}

async function openGenerateDialog(row) {
  await selectSpec(row)
  generateForm.batch_no = ''
  generateForm.count = 10
  generateForm.code_prefix = ''
  generateDialogVisible.value = true
  await loadIssuePreview()
}

async function handleIssue() {
  if (issuePreview.value?.can_issue === false) {
    ElMessage.error('发卡额度不足')
    return
  }
  issuing.value = true
  try {
    const res = await issueMerchantKamis(queryParams.app_id, buildIssuePayload())
    ElMessage.success(`已生成 ${res.data.count} 个卡密`)
    generateDialogVisible.value = false
    await Promise.all([loadQuota(), loadSpecs()])
  } finally {
    issuing.value = false
  }
}

async function openBatchDrawer(row) {
  selectedBatch.value = row
  const res = await getMerchantBatchKamis(row.id)
  batchKamis.value = responsePayload(res)
  batchDrawerVisible.value = true
}

watch(
  () => [generateForm.count, selectedSpec.value?.id],
  loadIssuePreview
)

onMounted(loadAll)
</script>

<style scoped>
.batch-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar,
.toolbar-actions,
.panel-header {
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

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
}

.quota-warning {
  border-radius: 8px;
}

.spec-workbench {
  display: grid;
  grid-template-columns: minmax(560px, 1fr) minmax(420px, 560px);
  gap: 16px;
  align-items: start;
}

.panel {
  border-radius: 8px;
}

.stat-inline {
  margin-left: 10px;
}

.spec-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.spec-summary > div {
  padding: 10px 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
}

.spec-summary span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.spec-summary strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
}

.detail-tabs {
  margin-top: 8px;
}

.issue-preview {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #334155;
  font-size: 13px;
}

@media (max-width: 1180px) {
  .spec-workbench {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .spec-summary {
    grid-template-columns: 1fr;
  }

  .issue-preview {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
