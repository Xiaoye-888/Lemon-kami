<template>
  <div class="end-users-container">
    <el-row :gutter="12" class="stats-row">
      <el-col :span="4" v-for="item in statItems" :key="item.label">
        <el-card class="stat-card">
          <div class="stat-card__label">{{ item.label }}</div>
          <div class="stat-card__value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户授权</span>
          <div class="header-actions">
            <el-button @click="handleExportUsers">导出用户</el-button>
            <el-button type="primary" @click="loadData">刷新</el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="queryParams" class="filter-form">
        <el-form-item label="应用">
          <el-select
            v-model="queryParams.app_id"
            clearable
            filterable
            placeholder="全部应用"
            style="width: 220px"
            @change="handleAppChange"
          >
            <el-option
              v-for="app in apps"
              :key="app.app_id"
              :label="app.name"
              :value="app.app_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="queryParams.keyword" clearable placeholder="用户名/邮箱" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" clearable placeholder="全部" style="width: 120px">
            <el-option label="启用" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadUsers">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="users" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="time_authorization" label="时间余额" width="170" />
        <el-table-column prop="times_remaining" label="次数余额" width="110" />
        <el-table-column prop="points_remaining" label="积分余额" width="110" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="showGrantAuthorizationDialog(row)">分配授权</el-button>
            <el-button size="small" @click="showUserKamisDialog(row)">授权明细</el-button>
            <el-button
              size="small"
              :type="row.status === 1 ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 1 ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" @click="showResetPasswordDialog(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadUsers"
        @current-change="loadUsers"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <el-dialog v-model="resetPasswordVisible" title="重置普通用户密码" width="420px">
      <el-form :model="resetPasswordForm" label-width="90px">
        <el-form-item label="用户">
          <span>{{ resetPasswordForm.username }}</span>
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="resetPasswordForm.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPasswordVisible = false">取消</el-button>
        <el-button type="primary" :loading="resettingPassword" @click="handleResetPassword">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="grantAuthVisible" title="分配用户授权" width="560px">
      <el-form :model="grantForm" label-width="110px">
        <el-form-item label="用户">
          <span>{{ grantForm.username }}</span>
        </el-form-item>
        <el-form-item label="应用" required>
          <el-select v-model="grantForm.app_id" filterable placeholder="选择应用" style="width: 100%">
            <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="授权类型" required>
          <el-select v-model="grantForm.benefit_type" style="width: 100%">
            <el-option label="时间授权" value="time" />
            <el-option label="次数授权" value="times" />
            <el-option label="积分授权" value="points" />
          </el-select>
        </el-form-item>
        <template v-if="grantForm.benefit_type === 'time'">
          <el-form-item label="永久授权">
            <el-switch v-model="grantForm.is_lifetime" />
          </el-form-item>
          <el-form-item v-if="!grantForm.is_lifetime" label="授权天数" required>
            <el-input-number v-model="grantForm.days" :min="1" :max="36500" style="width: 100%" />
          </el-form-item>
        </template>
        <el-form-item v-else :label="grantForm.benefit_type === 'times' ? '授权次数' : '授权积分'" required>
          <el-input-number v-model="grantForm.amount" :min="1" :max="100000000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="来源卡密">
          <el-input v-model="grantForm.source_kami_code" clearable placeholder="可选，用于追溯来源卡密" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="grantForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="grantAuthVisible = false">取消</el-button>
        <el-button type="primary" :loading="grantingAuthorization" @click="handleGrantAuthorization">确认分配</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="userKamisVisible" :title="`${currentUser?.username || '用户'}的授权明细`" width="1120px">
      <el-table :data="userKamis" v-loading="userKamisLoading" border stripe>
        <el-table-column prop="kami_code" label="卡密" min-width="190" show-overflow-tooltip />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ getTypeText(row.kami_type) }}</template>
        </el-table-column>
        <el-table-column prop="batch_no" label="批次" min-width="130" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">{{ getStatusText(row.status) }}</template>
        </el-table-column>
        <el-table-column label="绑定关系" width="120">
          <template #default="{ row }">{{ row.binding_relation || '-' }}</template>
        </el-table-column>
        <el-table-column label="权益配置" width="130">
          <template #default="{ row }">{{ getCardQuotaText(row) }}</template>
        </el-table-column>
        <el-table-column label="剩余/有效期" width="160">
          <template #default="{ row }">{{ getRemainingBenefitText(row) }}</template>
        </el-table-column>
        <el-table-column label="机器码限制" width="130">
          <template #default="{ row }">
            {{ row.machine_bind_mode_text || getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices) }}
          </template>
        </el-table-column>
        <el-table-column label="绑定设备" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ getBoundDeviceText(row) }}</template>
        </el-table-column>
        <el-table-column label="兑换时间" width="170">
          <template #default="{ row }">{{ formatOptionalTime(row.redeemed_at) }}</template>
        </el-table-column>
        <el-table-column label="最近核销" width="170">
          <template #default="{ row }">{{ formatOptionalTime(row.last_consume_at) }}</template>
        </el-table-column>
        <el-table-column label="最近验证" width="170">
          <template #default="{ row }">{{ formatOptionalTime(row.last_verify_at) }}</template>
        </el-table-column>
        <el-table-column label="授权来源" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ getLotSummary(row.authorization_lots) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  exportEndUsers,
  getEndUserKamis,
  getEndUsers,
  getEndUserStats,
  grantAuthorization,
  resetEndUserPassword,
  updateEndUserStatus
} from '../api/points'
import { getApps } from '../api/admin'
import { formatBeijingTime } from '../utils/datetime'
import {
  getMachineBindModeText,
  getStatusText,
  getTypeText,
  getValidityText
} from '../utils/kamiDisplay'

const loading = ref(false)
const resettingPassword = ref(false)
const grantingAuthorization = ref(false)
const userKamisLoading = ref(false)
const resetPasswordVisible = ref(false)
const grantAuthVisible = ref(false)
const userKamisVisible = ref(false)
const users = ref([])
const userKamis = ref([])
const apps = ref([])
const currentUser = ref(null)
const total = ref(0)
const stats = ref({
  total: 0,
  active: 0,
  disabled: 0,
  today_new: 0,
  with_balance: 0,
  total_balance: 0,
  with_authorization: 0,
  total_authorized_times: 0,
  total_authorized_points: 0
})

const queryParams = reactive({
  app_id: '',
  keyword: '',
  status: '',
  page: 1,
  page_size: 20
})

const resetPasswordForm = reactive({
  user_id: null,
  username: '',
  password: ''
})

const grantForm = reactive({
  user_id: null,
  username: '',
  app_id: '',
  benefit_type: 'time',
  amount: 1,
  days: 30,
  is_lifetime: false,
  source_kami_code: '',
  remark: ''
})

const statItems = computed(() => [
  { label: '用户总数', value: stats.value.total },
  { label: '今日新增', value: stats.value.today_new },
  { label: '启用用户', value: stats.value.active },
  { label: '禁用用户', value: stats.value.disabled },
  { label: '有授权用户', value: stats.value.with_authorization ?? stats.value.with_balance },
  {
    label: '次数/积分余额',
    value: `${stats.value.total_authorized_times ?? 0} / ${stats.value.total_authorized_points ?? stats.value.total_balance ?? 0}`
  }
])

const normalizeParams = (params) => {
  const normalized = { ...params }
  if (normalized.status === '') delete normalized.status
  if (!normalized.app_id) delete normalized.app_id
  return normalized
}

const loadApps = async () => {
  const res = await getApps()
  apps.value = res.data || []
  if (apps.value.length > 0 && !queryParams.app_id) {
    queryParams.app_id = apps.value[0].app_id
  }
}

const handleAppChange = () => {
  queryParams.page = 1
  loadData()
}

const loadStats = async () => {
  const params = normalizeParams({ app_id: queryParams.app_id })
  const res = await getEndUserStats(params)
  stats.value = res.data
}

const loadUsers = async () => {
  loading.value = true
  try {
    const params = normalizeParams(queryParams)
    const res = await getEndUsers(params)
    users.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

const loadData = async () => {
  await Promise.all([loadStats(), loadUsers()])
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

const handleExportUsers = async () => {
  const params = normalizeParams(queryParams)
  delete params.page
  delete params.page_size
  const response = await exportEndUsers(params)
  downloadBlob(response, `end_users_${queryParams.app_id || 'all'}.csv`)
}

const showResetPasswordDialog = (row) => {
  resetPasswordForm.user_id = row.id
  resetPasswordForm.username = row.username
  resetPasswordForm.password = ''
  resetPasswordVisible.value = true
}

const showGrantAuthorizationDialog = (row) => {
  currentUser.value = row
  grantForm.user_id = row.id
  grantForm.username = row.username
  grantForm.app_id = queryParams.app_id || row.app_id || apps.value[0]?.app_id || ''
  grantForm.benefit_type = 'time'
  grantForm.amount = 1
  grantForm.days = 30
  grantForm.is_lifetime = false
  grantForm.source_kami_code = ''
  grantForm.remark = ''
  grantAuthVisible.value = true
}

const handleGrantAuthorization = async () => {
  if (!grantForm.app_id) {
    ElMessage.warning('请选择应用')
    return
  }
  if (grantForm.benefit_type === 'time' && !grantForm.is_lifetime && !grantForm.days) {
    ElMessage.warning('请填写授权天数')
    return
  }
  if (grantForm.benefit_type !== 'time' && !grantForm.amount) {
    ElMessage.warning('请填写授权数量')
    return
  }
  grantingAuthorization.value = true
  try {
    const payload = {
      app_id: grantForm.app_id,
      user_id: grantForm.user_id,
      benefit_type: grantForm.benefit_type,
      source_kami_code: grantForm.source_kami_code || null,
      remark: grantForm.remark || null
    }
    if (grantForm.benefit_type === 'time') {
      payload.days = grantForm.is_lifetime ? null : grantForm.days
      payload.is_lifetime = grantForm.is_lifetime
    } else {
      payload.amount = grantForm.amount
    }
    await grantAuthorization(payload)
    ElMessage.success('授权已分配')
    grantAuthVisible.value = false
    await loadData()
  } finally {
    grantingAuthorization.value = false
  }
}

const showUserKamisDialog = async (row) => {
  currentUser.value = row
  userKamisVisible.value = true
  userKamisLoading.value = true
  userKamis.value = []
  try {
    const params = queryParams.app_id ? { app_id: queryParams.app_id } : {}
    const res = await getEndUserKamis(row.id, params)
    userKamis.value = res.data.items || []
  } finally {
    userKamisLoading.value = false
  }
}

const handleResetPassword = async () => {
  if (!resetPasswordForm.password || resetPasswordForm.password.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  resettingPassword.value = true
  try {
    await resetEndUserPassword(resetPasswordForm.user_id, { password: resetPasswordForm.password })
    ElMessage.success('密码已重置')
    resetPasswordVisible.value = false
  } finally {
    resettingPassword.value = false
  }
}

const toggleStatus = async (row) => {
  const nextStatus = row.status === 1 ? 0 : 1
  const action = nextStatus === 1 ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(`确定要${action}该用户吗？`, '提示', { type: 'warning' })
    await updateEndUserStatus(row.id, nextStatus)
    ElMessage.success(`${action}成功`)
    await loadData()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

const getCardQuotaText = (row) => {
  if (row.kami_type === 'points') return `${row.points_amount || 0}积分`
  if (row.kami_type === 'times') return `${row.times_total || 0}次`
  return getValidityText(row)
}

const getRemainingBenefitText = (row) => {
  if (row.kami_type === 'points') return `${row.point_source_remaining ?? row.points_remaining ?? row.point_remaining_balance ?? row.points_amount ?? 0}积分`
  if (row.kami_type === 'times') return `${row.times_remaining ?? 0}次`
  if (row.kami_type === 'lifetime') return '永久'
  return row.expire_time ? formatBeijingTime(row.expire_time) : getValidityText(row)
}

const getBoundDeviceText = (row) => {
  if (row?.authorization_owner === 'user' || row?.binding_relation === '用户授权') return '-'
  if (row?.bind_uuid) return row.bind_uuid
  if (row?.device_bind_count) return `${row.device_bind_count} 台设备`
  return '-'
}

const getLotSummary = (lots = []) => {
  if (!lots.length) return '-'
  return lots
    .map((lot) => {
      const typeMap = { time: '时间', times: '次数', points: '积分' }
      const type = typeMap[lot.benefit_type] || lot.benefit_type
      return `${type}:${lot.amount_remaining}/${lot.amount_total}`
    })
    .join('；')
}

onMounted(async () => {
  await loadApps()
  await loadData()
})
</script>

<style scoped>
.end-users-container {
  height: 100%;
}

.stats-row {
  margin-bottom: 12px;
}

.stat-card {
  min-height: 82px;
}

.stat-card__label {
  color: #64748b;
  font-size: 13px;
}

.stat-card__value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 700;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
