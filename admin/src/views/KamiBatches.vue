<template>
  <div class="kami-batches-page">
    <template v-if="!detailVisible">
      <section class="yz-admin-panel">
        <div class="yz-panel-header">
          <div class="yz-panel-title">
            <el-icon><Box /></el-icon>
            <span>批次管理</span>
          </div>
          <el-button type="primary" size="large" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建批次
          </el-button>
        </div>

        <div class="yz-filter-strip">
          <el-select v-model="queryParams.app_id" placeholder="选择应用" class="filter-control" @change="handleAppChange">
            <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
          </el-select>
          <el-select v-model="queryParams.kami_type" placeholder="全部类型" clearable class="filter-control" @change="loadBatches">
            <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-button :icon="Refresh" @click="loadBatches">刷新</el-button>
        </div>

        <el-empty v-if="!queryParams.app_id" description="请先选择应用" />
        <el-table v-else :data="batchStats" v-loading="loading" class="yz-clean-table" row-key="id">
          <el-table-column label="批次名称" min-width="180">
            <template #default="{ row }">
              <button type="button" class="batch-title-link" @click="openBatchDetail(row)">
                {{ row.batch_no }}
              </button>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="130">
            <template #default="{ row }">
              <span :class="['type-badge', getTypeBadgeClass(row.kami_type)]">
                {{ getTypeText(row.kami_type) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="机器码限制" width="190">
            <template #default="{ row }">
              <el-tag :type="getMachineTagType(row.machine_bind_mode)" effect="dark" round>
                {{ getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="总数/已用/剩余" min-width="190">
            <template #default="{ row }">
              <div class="count-pills">
                <span class="count-pill is-total">{{ row.total_count || 0 }}</span>
                <span>/</span>
                <span class="count-pill is-used">{{ usedCount(row) }}</span>
                <span>/</span>
                <span class="count-pill is-left">{{ row.unused_count || 0 }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'info'" effect="dark" round>
                {{ row.status === 1 ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="180">
            <template #default="{ row }">{{ row.created_at ? formatBeijingTime(row.created_at) : '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <div class="icon-actions">
                <el-tooltip content="编辑批次" placement="top">
                  <el-button class="icon-action" :icon="EditPen" @click="handleEditBatch(row)" />
                </el-tooltip>
                <el-tooltip content="查看卡密" placement="top">
                  <el-button class="icon-action info" :icon="View" @click="openBatchDetail(row)" />
                </el-tooltip>
                <el-tooltip content="删除空批次" placement="top">
                  <el-button class="icon-action danger" :icon="Delete" @click="handleDeleteBatch(row)" />
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </template>

    <template v-else>
      <div class="batch-detail-shell">
        <section class="batch-overview-card">
          <div class="batch-overview-main">
            <h2>{{ currentBatch?.batch_no || '-' }}</h2>
            <div class="hero-tags">
              <el-tag type="primary" effect="dark" round>{{ getTypeText(currentBatch?.kami_type) }}</el-tag>
              <el-tag type="info" effect="dark" round>{{ getValidityText(currentBatch) }}</el-tag>
              <el-tag v-if="userAuthorizationEnabled" type="warning" effect="dark" round>
                {{ getAuthorizationOwnerText(currentBatch?.authorization_owner) }}
              </el-tag>
              <el-tag v-if="userAuthorizationEnabled" type="success" effect="dark" round>
                {{ getUserBindModeText(currentBatch?.user_bind_mode) }}
              </el-tag>
              <el-tag :type="currentBatch?.status === 1 ? 'success' : 'info'" effect="dark" round>
                {{ currentBatch?.status === 1 ? '启用' : '停用' }}
              </el-tag>
            </div>
          </div>
          <div class="hero-actions">
            <el-button :icon="ArrowLeft" @click="backToBatches">返回批次管理</el-button>
            <el-button :icon="EditPen" @click="handleEditBatch(currentBatch)">编辑批次</el-button>
            <el-button type="danger" plain :icon="Delete" @click="handleDeleteBatch(currentBatch)">删除批次</el-button>
          </div>
        </section>

        <section class="summary-metric-card">
          <div class="metric-item">
            <strong class="metric-value is-primary">{{ currentBatch?.total_count || 0 }}</strong>
            <span>总数</span>
          </div>
          <div class="metric-item">
            <strong class="metric-value is-green">{{ currentBatch?.unused_count || 0 }}</strong>
            <span>未使用</span>
          </div>
          <div class="metric-item">
            <strong class="metric-value is-amber">{{ usedCount(currentBatch) }}</strong>
            <span>已使用</span>
          </div>
        </section>
      </div>

      <section class="yz-admin-panel cards-panel">
        <div class="yz-panel-header">
          <div class="yz-panel-title">
            <el-icon><Key /></el-icon>
            <span>卡密列表</span>
          </div>
          <div class="panel-actions">
            <el-button :icon="Download" @click="handleDetailExport">导出</el-button>
            <el-button type="danger" plain :disabled="selectedDetailKamis.length === 0" @click="handleDeleteSelectedDetail">
              删除选中
            </el-button>
            <el-button type="primary" :icon="Plus" :disabled="!kamiGenerateEnabled" @click="showAppendDialog">追加卡密</el-button>
          </div>
        </div>

        <div class="yz-filter-strip">
          <el-select v-model="detailQuery.status" placeholder="全部状态" clearable class="filter-control" @change="loadDetailKamis">
            <el-option label="未使用" value="unused" />
            <el-option label="已使用" value="active" />
            <el-option label="已冻结" value="frozen" />
          </el-select>
          <el-input v-model="detailQuery.keyword" placeholder="搜索卡密/用户" clearable class="search-control" @keyup.enter="loadDetailKamis" />
          <el-button type="primary" :icon="Search" @click="loadDetailKamis" />
          <el-button :icon="Refresh" @click="resetDetailFilters">重置</el-button>
        </div>

        <el-table
          :data="detailKamis"
          v-loading="detailLoading"
          row-key="kami_code"
          class="yz-clean-table detail-table"
          @selection-change="selectedDetailKamis = $event"
        >
          <el-table-column type="selection" width="48" />
          <el-table-column label="卡密" min-width="220">
            <template #default="{ row }">
              <div class="code-cell">
                <span class="mono-text">{{ row.kami_code }}</span>
                <el-tooltip content="复制卡密" placement="top">
                  <el-button :icon="DocumentCopy" size="small" circle @click="copyToClipboard(row.kami_code)" />
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)" round>{{ getStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="180">
            <template #default="{ row }">{{ row.created_at ? formatBeijingTime(row.created_at) : '-' }}</template>
          </el-table-column>
          <template v-if="currentBatchType === 'points'">
            <el-table-column label="使用用户" min-width="130">
              <template #default="{ row }">{{ getKamiUserText(row) }}</template>
            </el-table-column>
            <el-table-column label="积分面额" width="120">
              <template #default="{ row }">{{ row.points_amount || 0 }}</template>
            </el-table-column>
            <el-table-column label="已兑换积分" width="130">
              <template #default="{ row }">{{ getPointsRedeemed(row) }}</template>
            </el-table-column>
            <el-table-column label="剩余积分" width="120">
              <template #default="{ row }">{{ getPointsRemaining(row) }}</template>
            </el-table-column>
            <el-table-column label="兑换时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.redeemed_at) }}</template>
            </el-table-column>
            <el-table-column label="有效期" width="120">
              <template #default="{ row }">{{ row.points_valid_days ? `${row.points_valid_days}天` : '永久' }}</template>
            </el-table-column>
          </template>
          <template v-else-if="currentBatchType === 'times'">
            <el-table-column label="使用用户" min-width="130">
              <template #default="{ row }">{{ getKamiUserText(row) }}</template>
            </el-table-column>
            <el-table-column label="绑定设备" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ getBoundDeviceText(row) }}</template>
            </el-table-column>
            <el-table-column label="每卡次数" width="120">
              <template #default="{ row }">{{ row.times_total || 0 }}</template>
            </el-table-column>
            <el-table-column label="已核销次数" width="130">
              <template #default="{ row }">{{ getTimesConsumed(row) }}</template>
            </el-table-column>
            <el-table-column label="剩余次数" width="120">
              <template #default="{ row }">{{ row.times_remaining ?? 0 }}</template>
            </el-table-column>
            <el-table-column label="最近核销时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.last_consume_at) }}</template>
            </el-table-column>
            <el-table-column label="最近验证时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.last_verify_at) }}</template>
            </el-table-column>
          </template>
          <template v-else>
            <el-table-column label="使用用户" min-width="130">
              <template #default="{ row }">{{ getKamiUserText(row) }}</template>
            </el-table-column>
            <el-table-column label="有效期" width="180">
              <template #default="{ row }">{{ getTimeCardValidity(row) }}</template>
            </el-table-column>
            <el-table-column label="机器码限制" width="170">
              <template #default="{ row }">
                {{ getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices) }}
              </template>
            </el-table-column>
            <el-table-column label="绑定设备" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ getBoundDeviceText(row) }}</template>
            </el-table-column>
            <el-table-column label="最近验证时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.last_verify_at) }}</template>
            </el-table-column>
          </template>
          <el-table-column label="备注" min-width="160">
            <template #default="{ row }">{{ row.remark || '-' }}</template>
          </el-table-column>
        </el-table>

        <div class="table-footer">
          <span>共 {{ detailTotal }} 条</span>
          <el-pagination
            v-model:current-page="detailQuery.page"
            v-model:page-size="detailQuery.page_size"
            :total="detailTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="sizes, prev, pager, next"
            @size-change="loadDetailKamis"
            @current-change="loadDetailKamis"
          />
        </div>
      </section>
    </template>

    <el-dialog v-model="batchDialogVisible" :title="isEditing ? '编辑批次' : '新建批次'" width="680px">
      <el-form :model="batchForm" label-width="128px" class="batch-form">
        <el-form-item label="应用" required>
          <el-select v-model="batchForm.app_id" placeholder="选择应用" style="width: 100%" :disabled="isEditing">
            <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次名称" required>
          <el-input v-model="batchForm.batch_no" maxlength="64" placeholder="例如：points-500-202607" />
        </el-form-item>
        <el-form-item label="卡密类型" required>
          <el-select v-model="batchForm.kami_type" style="width: 100%" :disabled="isEditing && editingBatchHasCards">
            <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="deviceLimitEnabled" label="机器码绑定" required>
          <el-select v-model="batchForm.machine_bind_mode" style="width: 100%">
            <el-option label="不限制" value="no_limit" />
            <el-option label="一机一码（一个卡密只能绑定一台设备）" value="one_card_one_device" />
            <el-option label="一卡多机（一个卡密可绑定多台设备）" value="one_card_multi_device" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="deviceLimitEnabled && batchForm.machine_bind_mode === 'one_card_multi_device'" label="绑定设备数" required>
          <el-input-number v-model="batchForm.max_bind_devices" :min="2" :max="1000" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="userAuthorizationEnabled" label="授权归属" required>
          <el-select v-model="batchForm.authorization_owner" style="width: 100%">
            <el-option v-for="item in authorizationOwnerOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="userAuthorizationEnabled" label="用户绑定" required>
          <el-select v-model="batchForm.user_bind_mode" style="width: 100%">
            <el-option v-for="item in userBindModeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <div class="form-help">{{ authorizationPolicyHelp }}</div>
        </el-form-item>
        <el-form-item v-if="isFixedTimeCard(batchForm.kami_type)" label="有效期">
          <el-input :model-value="fixedValidityText(batchForm.kami_type)" disabled />
        </el-form-item>
        <el-form-item v-if="batchForm.kami_type === 'points'" label="积分面额" required>
          <el-input-number v-model="batchForm.points_amount" :min="1" :max="100000000" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="batchForm.kami_type === 'points'" label="积分有效天数">
          <el-input-number v-model="batchForm.points_valid_days" :min="1" :max="36500" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="batchForm.kami_type === 'times'" label="可用次数" required>
          <el-input-number v-model="batchForm.times_total" :min="1" :max="1000000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="batchForm.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="batchForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingBatch" @click="handleSaveBatch">保存批次</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="appendDialogVisible" title="追加卡密" width="620px">
      <el-form :model="appendForm" label-width="110px">
        <el-form-item label="批次">
          <el-input :model-value="currentBatch?.batch_no" disabled />
        </el-form-item>
        <el-form-item label="批次配置">
          <div class="batch-summary">
            {{ currentBatchSummaryText }}
          </div>
        </el-form-item>
        <el-form-item label="追加数量" required>
          <el-input-number v-model="appendForm.count" :min="1" :max="1000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="卡密前缀">
          <el-input v-model="appendForm.code_prefix" maxlength="32" placeholder="例如：VIP-" />
        </el-form-item>
        <el-form-item label="随机长度" required>
          <el-input-number v-model="appendForm.code_length" :min="4" :max="64" style="width: 100%" />
        </el-form-item>
        <el-form-item label="字符集" required>
          <el-select v-model="appendForm.charset" style="width: 100%">
            <el-option v-for="item in charsetOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="格式预览">
          <div class="code-preview">{{ appendCodePreview }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="appendDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="appending" @click="handleAppendKamis">追加卡密</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Box,
  Delete,
  DocumentCopy,
  Download,
  EditPen,
  Key,
  Plus,
  Refresh,
  Search,
  View
} from '@element-plus/icons-vue'
import { getApps } from '../api/admin'
import { getAppInterfaces } from '../api/interfaces'
import {
  batchCreateKamis,
  createKamiBatch,
  deleteKamiBatch,
  deleteKamis,
  exportKamis,
  getKamiBatches,
  getKamis,
  updateKamiBatch
} from '../api/kami'
import { formatBeijingTime } from '../utils/datetime'
import {
  AUTHORIZATION_OWNER_OPTIONS,
  TYPE_OPTIONS,
  USER_BIND_MODE_OPTIONS,
  getAuthorizationOwnerText,
  getMachineBindModeText,
  getMachineTagType,
  getStatusText,
  getStatusType,
  getTypeText,
  getUserBindModeText,
  getValidityText,
  isFixedTimeCard
} from '../utils/kamiDisplay'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const detailLoading = ref(false)
const savingBatch = ref(false)
const appending = ref(false)
const apps = ref([])
const batchStats = ref([])
const detailKamis = ref([])
const selectedDetailKamis = ref([])
const detailTotal = ref(0)
const detailVisible = ref(false)
const selectedBatch = ref(null)
const batchDialogVisible = ref(false)
const appendDialogVisible = ref(false)
const isEditing = ref(false)
const editingBatchHasCards = ref(false)
const appInterfaceFlags = ref({})
const appInterfaceConfigs = ref({})

const interfaceEnabled = (key, defaultValue = true) => {
  const value = appInterfaceFlags.value[key]
  return typeof value === 'boolean' ? value : defaultValue
}

const deviceLimitEnabled = computed(() => interfaceEnabled('sdk.device_limit', true))
const userAuthorizationEnabled = computed(() => (
  interfaceEnabled('sdk.verify', true) &&
  Boolean(appInterfaceConfigs.value['sdk.verify']?.enable_user_authorization)
))
const pointsFeatureEnabled = computed(() => (
  interfaceEnabled('points.balance', true) ||
  interfaceEnabled('points.redeem', true) ||
  interfaceEnabled('points.consume', true) ||
  interfaceEnabled('points.transactions', true)
))
const kamiGenerateEnabled = computed(() => interfaceEnabled('admin.kamis.batch', true))

const baseTypeOptions = TYPE_OPTIONS
const authorizationOwnerOptions = AUTHORIZATION_OWNER_OPTIONS
const userBindModeOptions = USER_BIND_MODE_OPTIONS

const typeOptions = computed(() => (
  baseTypeOptions.filter((item) => item.value !== 'points' || pointsFeatureEnabled.value)
))

const charsetOptions = [
  { label: '大写字母 + 数字', value: 'upper_numeric', sample: 'A1B2C3D4E5F6G7H8' },
  { label: '纯数字', value: 'numeric', sample: '1234567890123456' },
  { label: '大写字母', value: 'upper', sample: 'ABCDEFGHJKLMNPQR' },
  { label: '大小写字母 + 数字', value: 'lower_mixed', sample: 'aB3dE5fG7hJ9kLmN' }
]

const fixedValidityMap = {
  hour: '小时卡：1小时',
  day: '天卡：1天',
  week: '周卡：7天',
  month: '月卡：30天',
  quarter: '季卡：90天',
  year: '年卡：365天',
  lifetime: '永久卡：永久'
}

const queryParams = reactive({
  app_id: '',
  kami_type: ''
})

const detailQuery = reactive({
  status: '',
  keyword: '',
  page: 1,
  page_size: 20
})

const batchForm = reactive({
  id: null,
  app_id: '',
  batch_no: '',
  kami_type: 'day',
  machine_bind_mode: 'one_card_one_device',
  max_bind_devices: 3,
  points_amount: 100,
  points_valid_days: undefined,
  times_total: 1,
  authorization_owner: 'device',
  user_bind_mode: 'none',
  status: 1,
  remark: ''
})

const appendForm = reactive({
  count: 10,
  code_prefix: '',
  code_length: 16,
  charset: 'upper_numeric'
})

const currentBatch = computed(() => {
  if (!selectedBatch.value) return null
  return (
    batchStats.value.find((item) => item.id === selectedBatch.value.id) ||
    batchStats.value.find((item) => item.batch_no === selectedBatch.value.batch_no) ||
    selectedBatch.value
  )
})
const currentBatchType = computed(() => currentBatch.value?.kami_type || '')

const appendCodePreview = computed(() => codePreview(appendForm))
const authorizationPolicyHelp = computed(() => {
  const ownerHelp = {
    device: '设备授权：权益归属到设备，适合不方便注册账号的软件。',
    user: '用户授权：权益归属到用户，必须传入有效用户信息。',
    auto: '自动识别：SDK 请求带有效 user_id/username 时按用户授权，未传用户时按设备授权。'
  }[batchForm.authorization_owner] || '设备授权：权益归属到设备。'
  const bindHelp = {
    none: '不绑定用户：不读取用户信息。',
    auto: '自动识别绑定：首次使用传入有效用户时绑定用户；未传用户时按设备授权。',
    optional: '自动识别绑定：首次使用传入有效用户时绑定用户；未传用户时按设备授权。',
    required: '必须绑定用户：verify 和 consume 都必须传 user_id 或 username。'
  }[batchForm.user_bind_mode] || '不绑定用户：不读取用户信息。'
  return `${ownerHelp} ${bindHelp}`
})
const currentBatchSummaryText = computed(() => {
  const parts = [
    getTypeText(currentBatch.value?.kami_type),
    getValidityText(currentBatch.value)
  ]
  if (deviceLimitEnabled.value) {
    parts.push(getMachineBindModeText(currentBatch.value?.machine_bind_mode, currentBatch.value?.max_bind_devices))
  }
  if (userAuthorizationEnabled.value) {
    parts.push(getAuthorizationOwnerText(currentBatch.value?.authorization_owner))
    parts.push(getUserBindModeText(currentBatch.value?.user_bind_mode))
  }
  return parts.filter(Boolean).join(' / ')
})

const syncTypeWithInterfaceFlags = () => {
  if (queryParams.kami_type && !typeOptions.value.some((item) => item.value === queryParams.kami_type)) {
    queryParams.kami_type = ''
  }
  if (!typeOptions.value.some((item) => item.value === batchForm.kami_type)) {
    batchForm.kami_type = typeOptions.value[0]?.value || 'day'
  }
}

const loadAppInterfaceFlags = async () => {
  if (!queryParams.app_id) {
    appInterfaceFlags.value = {}
    appInterfaceConfigs.value = {}
    return
  }
  try {
    const res = await getAppInterfaces(queryParams.app_id)
    const flags = {}
    const configs = {}
    ;(res.data || []).forEach((item) => {
      flags[item.interface_key] = Boolean(item.enabled)
      configs[item.interface_key] = item.config || {}
    })
    appInterfaceFlags.value = flags
    appInterfaceConfigs.value = configs
  } catch (error) {
    console.error('加载应用接口开关失败:', error)
    appInterfaceFlags.value = {}
    appInterfaceConfigs.value = {}
  }
  syncTypeWithInterfaceFlags()
}

const loadApps = async () => {
  const res = await getApps()
  apps.value = res.data || []
  if (route.query.app_id) queryParams.app_id = String(route.query.app_id)
  if (!queryParams.app_id && apps.value.length > 0) queryParams.app_id = apps.value[0].app_id
  batchForm.app_id = queryParams.app_id
  await loadAppInterfaceFlags()
  await loadBatches()

  if (route.query.batch_no) {
    const batch = batchStats.value.find((item) => item.batch_no === String(route.query.batch_no))
    if (batch) await openBatchDetail(batch)
  }
}

const handleAppChange = async () => {
  detailVisible.value = false
  selectedBatch.value = null
  batchForm.app_id = queryParams.app_id
  await loadAppInterfaceFlags()
  await loadBatches()
}

const loadBatches = async () => {
  if (!queryParams.app_id) {
    batchStats.value = []
    return
  }
  loading.value = true
  try {
    const params = { app_id: queryParams.app_id }
    if (queryParams.kami_type) params.kami_type = queryParams.kami_type
    const res = await getKamiBatches(params)
    batchStats.value = res.data || []
    if (detailVisible.value && currentBatch.value) selectedBatch.value = currentBatch.value
  } finally {
    loading.value = false
  }
}

const openBatchDetail = async (row) => {
  selectedBatch.value = row
  detailVisible.value = true
  detailQuery.status = ''
  detailQuery.keyword = ''
  detailQuery.page = 1
  selectedDetailKamis.value = []
  router.replace({ path: '/kamis/batches', query: { app_id: queryParams.app_id, batch_no: row.batch_no } })
  await loadDetailKamis()
}

const backToBatches = () => {
  detailVisible.value = false
  selectedBatch.value = null
  selectedDetailKamis.value = []
  router.replace({ path: '/kamis/batches', query: { app_id: queryParams.app_id } })
}

const loadDetailKamis = async () => {
  if (!currentBatch.value) return
  detailLoading.value = true
  try {
    const params = {
      app_id: currentBatch.value.app_id,
      batch_no: currentBatch.value.batch_no,
      page: detailQuery.page,
      page_size: detailQuery.page_size
    }
    if (detailQuery.status) params.status = detailQuery.status
    if (detailQuery.keyword) params.keyword = detailQuery.keyword.trim()
    const res = await getKamis(params)
    detailKamis.value = res.data.items || []
    detailTotal.value = res.data.total || 0
    selectedDetailKamis.value = []
    await loadBatches()
  } finally {
    detailLoading.value = false
  }
}

const resetDetailFilters = () => {
  detailQuery.status = ''
  detailQuery.keyword = ''
  detailQuery.page = 1
  loadDetailKamis()
}

const resetBatchForm = () => {
  Object.assign(batchForm, {
    id: null,
    app_id: queryParams.app_id || apps.value[0]?.app_id || '',
    batch_no: '',
    kami_type: typeOptions.value[0]?.value || 'day',
    machine_bind_mode: deviceLimitEnabled.value ? 'one_card_one_device' : 'no_limit',
    max_bind_devices: deviceLimitEnabled.value ? 3 : 0,
    points_amount: 100,
    points_valid_days: undefined,
    times_total: 1,
    authorization_owner: userAuthorizationEnabled.value ? 'auto' : 'device',
    user_bind_mode: userAuthorizationEnabled.value ? 'auto' : 'none',
    status: 1,
    remark: ''
  })
}

const showCreateDialog = () => {
  isEditing.value = false
  editingBatchHasCards.value = false
  resetBatchForm()
  batchDialogVisible.value = true
}

const handleEditBatch = (row) => {
  if (!row) return
  isEditing.value = true
  editingBatchHasCards.value = (row.total_count || 0) > 0
  Object.assign(batchForm, {
    id: row.id,
    app_id: row.app_id || queryParams.app_id,
    batch_no: row.batch_no || '',
    kami_type: row.kami_type || 'day',
    machine_bind_mode: deviceLimitEnabled.value ? (row.machine_bind_mode || 'one_card_one_device') : 'no_limit',
    max_bind_devices: deviceLimitEnabled.value ? (row.max_bind_devices || 3) : 0,
    points_amount: row.points_amount || 100,
    points_valid_days: row.points_valid_days || undefined,
    times_total: row.times_total || 1,
    authorization_owner: row.authorization_owner || 'device',
    user_bind_mode: row.user_bind_mode || 'none',
    status: Number(row.status ?? 1),
    remark: row.remark || ''
  })
  batchDialogVisible.value = true
}

const normalizeBatchPayload = () => {
  const machineBindMode = deviceLimitEnabled.value ? batchForm.machine_bind_mode : 'no_limit'
  const fallbackBatch = currentBatch.value
  const payload = {
    app_id: batchForm.app_id,
    batch_no: batchForm.batch_no.trim(),
    kami_type: batchForm.kami_type,
    machine_bind_mode: machineBindMode,
    max_bind_devices:
      machineBindMode === 'one_card_multi_device'
        ? batchForm.max_bind_devices || 3
        : machineBindMode === 'no_limit'
          ? 0
          : 1,
    authorization_owner: userAuthorizationEnabled.value
      ? batchForm.authorization_owner
      : (isEditing.value ? (fallbackBatch?.authorization_owner || batchForm.authorization_owner || 'device') : 'device'),
    user_bind_mode: userAuthorizationEnabled.value
      ? batchForm.user_bind_mode
      : (isEditing.value ? (fallbackBatch?.user_bind_mode || batchForm.user_bind_mode || 'none') : 'none'),
    status: batchForm.status,
    remark: batchForm.remark || null
  }
  if (batchForm.kami_type === 'points') {
    payload.points_amount = batchForm.points_amount
    payload.points_valid_days = batchForm.points_valid_days || null
  }
  if (batchForm.kami_type === 'times') {
    payload.times_total = batchForm.times_total
  }
  return payload
}

const handleSaveBatch = async () => {
  if (!batchForm.app_id || !batchForm.batch_no.trim()) {
    ElMessage.warning('请选择应用并填写批次名称')
    return
  }
  if (batchForm.kami_type === 'points' && !batchForm.points_amount) {
    ElMessage.warning('积分卡必须设置积分面额')
    return
  }
  if (batchForm.kami_type === 'times' && !batchForm.times_total) {
    ElMessage.warning('次数卡必须设置可用次数')
    return
  }
  if (deviceLimitEnabled.value && batchForm.machine_bind_mode === 'one_card_multi_device' && (!batchForm.max_bind_devices || batchForm.max_bind_devices < 2)) {
    ElMessage.warning('一卡多机至少需要允许 2 台设备')
    return
  }
  if (
    userAuthorizationEnabled.value &&
    batchForm.authorization_owner === 'user' &&
    batchForm.user_bind_mode === 'none'
  ) {
    ElMessage.warning('用户授权批次必须选择自动识别绑定或必须绑定用户')
    return
  }

  savingBatch.value = true
  try {
    const payload = normalizeBatchPayload()
    if (isEditing.value) {
      await updateKamiBatch(batchForm.id, payload)
      ElMessage.success('批次已更新')
    } else {
      await createKamiBatch(payload)
      ElMessage.success('批次已创建')
      queryParams.app_id = payload.app_id
    }
    batchDialogVisible.value = false
    await loadBatches()
    if (detailVisible.value && currentBatch.value) await loadDetailKamis()
  } finally {
    savingBatch.value = false
  }
}

const handleDeleteBatch = async (row) => {
  if (!row) return
  try {
    await ElMessageBox.confirm(`确定删除批次「${row.batch_no}」吗？只有空批次可以删除。`, '删除批次', {
      type: 'warning'
    })
    await deleteKamiBatch(row.id)
    ElMessage.success('批次已删除')
    if (currentBatch.value?.id === row.id) backToBatches()
    await loadBatches()
  } catch (error) {
    if (error !== 'cancel') {
      const detail = error?.response?.data?.detail
      const message = detail || error?.message || '删除批次失败'
      ElMessage.error(message)
      console.error('删除批次失败:', error)
    }
  }
}

const showAppendDialog = () => {
  if (!kamiGenerateEnabled.value) {
    ElMessage.warning('卡密生成接口未开通')
    return
  }
  appendForm.count = 10
  appendForm.code_prefix = ''
  appendForm.code_length = 16
  appendForm.charset = 'upper_numeric'
  appendDialogVisible.value = true
}

const handleAppendKamis = async () => {
  if (!currentBatch.value) return
  appending.value = true
  try {
    const res = await batchCreateKamis({
      app_id: currentBatch.value.app_id,
      batch_no: currentBatch.value.batch_no,
      count: appendForm.count,
      code_prefix: appendForm.code_prefix,
      code_length: appendForm.code_length,
      charset: appendForm.charset
    })
    ElMessage.success(`成功追加 ${res.data.count} 个卡密`)
    appendDialogVisible.value = false
    detailQuery.page = 1
    await loadDetailKamis()
  } finally {
    appending.value = false
  }
}

const handleDeleteSelectedDetail = async () => {
  if (!currentBatch.value || selectedDetailKamis.value.length === 0) return
  const count = selectedDetailKamis.value.length
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${count} 个卡密吗？已使用卡密会自动跳过。`, '删除卡密', {
      type: 'warning'
    })
    await deleteKamis({
      app_id: currentBatch.value.app_id,
      batch_no: currentBatch.value.batch_no,
      kami_codes: selectedDetailKamis.value.map((item) => item.kami_code)
    })
    ElMessage.success('卡密删除完成')
    await loadDetailKamis()
  } catch (error) {
    if (error !== 'cancel') console.error('删除卡密失败:', error)
  }
}

const handleDetailExport = async () => {
  if (!currentBatch.value) return
  const response = await exportKamis({
    app_id: currentBatch.value.app_id,
    batch_no: currentBatch.value.batch_no
  })
  downloadBlob(response, `kamis_${currentBatch.value.app_id}_${currentBatch.value.batch_no}.csv`)
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

const usedCount = (row) => {
  if (!row) return 0
  if (typeof row.redeemed_count === 'number' && row.redeemed_count > 0) return row.redeemed_count
  if (typeof row.active_count === 'number' && row.active_count > 0) return row.active_count
  return Math.max((row.total_count || 0) - (row.unused_count || 0) - (row.frozen_count || 0), 0)
}

const fixedValidityText = (type) => fixedValidityMap[type] || '-'

const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('复制成功')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const getKamiUserText = (row) => (
  row?.redeemed_user?.username ||
  row?.redeemed_user?.email ||
  row?.redeemed_by_user_id ||
  '-'
)

const getPointsRemaining = (row) => row?.point_remaining_balance ?? row?.points_amount ?? 0

const getPointsRedeemed = (row) => Math.max((row?.points_amount || 0) - getPointsRemaining(row), 0)

const getTimesConsumed = (row) => Math.max((row?.times_total || 0) - (row?.times_remaining ?? 0), 0)

const getBoundDeviceText = (row) => {
  if (row?.bind_uuid) return row.bind_uuid
  if (row?.device_bind_count) return `${row.device_bind_count} 台设备`
  return '-'
}

const getTimeCardValidity = (row) => {
  if (row?.expire_time) return formatBeijingTime(row.expire_time)
  return getValidityText(row)
}

const getTypeBadgeClass = (type) => {
  if (type === 'points') return 'is-points'
  if (type === 'times') return 'is-times'
  if (type === 'lifetime') return 'is-lifetime'
  if (isFixedTimeCard(type)) return 'is-time'
  return 'is-default'
}

const codePreview = (form) => {
  const option = charsetOptions.find((item) => item.value === form.charset) || charsetOptions[0]
  const suffix = option.sample.repeat(Math.ceil(form.code_length / option.sample.length)).slice(0, form.code_length)
  return `${form.code_prefix || ''}${suffix}`
}

onMounted(loadApps)
</script>

<style scoped>
.kami-batches-page {
  min-height: 100%;
}

.kami-batches-page :deep(.el-button--primary:not(.is-plain)) {
  background: #2f80ed !important;
  border-color: #2f80ed !important;
}

.kami-batches-page :deep(.el-button--primary:not(.is-plain):hover) {
  background: #1d4ed8 !important;
  border-color: #1d4ed8 !important;
}

.yz-admin-panel,
.batch-overview-card,
.summary-metric-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.yz-panel-header {
  min-height: 84px;
  padding: 22px 28px;
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

.yz-filter-strip {
  padding: 18px 28px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  background: #f8fafc;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.filter-control {
  width: 210px;
}

.search-control {
  width: 280px;
}

.yz-clean-table {
  width: 100%;
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

.batch-title-link {
  border: 0;
  background: transparent;
  color: #2563eb;
  font: inherit;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  padding: 0;
  cursor: pointer;
}

.batch-title-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 4px 10px;
  border: 1px solid #dbe4f0;
  border-radius: 6px;
  background: #f8fafc;
  color: #334155;
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.type-badge.is-time {
  border-color: #99f6e4;
  background: #ecfdf5;
  color: #0f766e;
}

.type-badge.is-points {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.type-badge.is-times {
  border-color: #fde68a;
  background: #fffbeb;
  color: #b45309;
}

.type-badge.is-lifetime {
  border-color: #fbcfe8;
  background: #fdf2f8;
  color: #be185d;
}

.code-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.count-pills,
.icon-actions,
.panel-actions,
.hero-actions,
.hero-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.count-pill {
  min-width: 30px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #fff;
  font-weight: 700;
}

.count-pill.is-total {
  background: #64748b;
}

.count-pill.is-used {
  background: #f59e0b;
}

.count-pill.is-left {
  background: #059669;
}

.icon-action {
  width: 36px;
  height: 36px;
  padding: 0;
  border-color: #2563eb;
  color: #2563eb;
}

.icon-action.info {
  border-color: #06b6d4;
  color: #0891b2;
}

.icon-action.danger {
  border-color: #ef4444;
  color: #ef4444;
}

.batch-detail-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 24px;
  margin-bottom: 24px;
}

.batch-overview-card {
  min-height: 150px;
  padding: 30px 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.batch-overview-main h2 {
  margin: 8px 0 14px;
  color: #0f172a;
  font-size: 30px;
  line-height: 1.2;
}

.summary-metric-card {
  min-height: 150px;
  padding: 30px 34px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  align-items: center;
  text-align: center;
  gap: 10px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: #475569;
}

.metric-value {
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
}

.metric-value.is-primary {
  color: #2563eb;
}

.metric-value.is-green {
  color: #059669;
}

.metric-value.is-amber {
  color: #f59e0b;
}

.cards-panel :deep(.el-empty) {
  min-height: 420px;
}

.detail-table {
  min-height: 360px;
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

.batch-config-lines {
  display: flex;
  flex-direction: column;
  gap: 3px;
  color: #475569;
  font-size: 13px;
  line-height: 1.45;
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

.batch-form :deep(.el-form-item__label) {
  font-weight: 600;
}

.form-help {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.batch-summary {
  width: 100%;
  color: #475569;
  line-height: 1.5;
}

html.dark .yz-panel-title,
html.dark .batch-overview-main h2 {
  color: #e5e7eb;
}

html.dark .yz-filter-strip,
html.dark .yz-clean-table :deep(.el-table__header th),
html.dark .code-preview {
  background: #111827;
}

@media (max-width: 1100px) {
  .batch-detail-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .yz-panel-header,
  .batch-overview-card,
  .table-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .filter-control,
  .search-control {
    width: 100%;
  }

  .summary-metric-card {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    padding: 24px 16px;
  }
}
</style>
