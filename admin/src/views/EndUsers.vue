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
          <span>鐢ㄦ埛鎺堟潈</span>
          <div class="header-actions">
            <el-button @click="handleExportUsers">瀵煎嚭鐢ㄦ埛</el-button>
            <el-button
              type="danger"
              plain
              :disabled="selectedUsers.length === 0"
              :loading="deletingUsers"
              @click="handleDeleteSelectedUsers"
            >
              鍒犻櫎鐢ㄦ埛
            </el-button>
            <el-button type="primary" @click="loadData">鍒锋柊</el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="queryParams" class="filter-form">
        <el-form-item label="搴旂敤">
          <el-select
            v-model="queryParams.app_id"
            clearable
            filterable
            placeholder="鍏ㄩ儴搴旂敤"
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
        <el-form-item label="关键词">
          <el-input v-model="queryParams.keyword" clearable placeholder="鐢ㄦ埛鍚?閭" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" clearable placeholder="鍏ㄩ儴" style="width: 120px">
            <el-option label="鍚敤" :value="1" />
            <el-option label="绂佺敤" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadUsers">鏌ヨ</el-button>
        </el-form-item>
      </el-form>

      <el-table
        :data="users"
        v-loading="loading"
        border
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="email" label="閭" min-width="180" />
        <el-table-column prop="time_authorization" label="鏃堕棿浣欓" width="170" />
        <el-table-column prop="times_remaining" label="娆℃暟浣欓" width="110" />
        <el-table-column prop="points_remaining" label="绉垎浣欓" width="110" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '鍚敤' : '绂佺敤' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="娉ㄥ唽鏃堕棿" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="last_login" label="最近登录" width="180">
          <template #default="{ row }">{{ formatOptionalTime(row.last_login) }}</template>
        </el-table-column>
        <el-table-column label="鎿嶄綔" width="330" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="showQuotaDialog(row)">额度管理</el-button>
            <el-button size="small" type="success" plain @click="showAppAuthorizationDialog(row)">应用授权</el-button>
            <el-button size="small" type="primary" plain @click="showGrantAuthorizationDialog(row)">鍒嗛厤鎺堟潈</el-button>
            <el-button size="small" @click="showUserKamisDialog(row)">鎺堟潈鏄庣粏</el-button>
            <el-button
              size="small"
              :type="row.status === 1 ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 1 ? '绂佺敤' : '鍚敤' }}
            </el-button>
            <el-button size="small" @click="showResetPasswordDialog(row)">閲嶇疆瀵嗙爜</el-button>
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
        <el-form-item label="鐢ㄦ埛">
          <span>{{ resetPasswordForm.username }}</span>
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="resetPasswordForm.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPasswordVisible = false">鍙栨秷</el-button>
        <el-button type="primary" :loading="resettingPassword" @click="handleResetPassword">纭畾</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="grantAuthVisible" title="鍒嗛厤鐢ㄦ埛鎺堟潈" width="560px">
      <el-form :model="grantForm" label-width="110px">
        <el-form-item label="鐢ㄦ埛">
          <span>{{ grantForm.username }}</span>
        </el-form-item>
        <el-form-item label="搴旂敤" required>
          <el-select v-model="grantForm.app_id" filterable placeholder="閫夋嫨搴旂敤" style="width: 100%">
            <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="鎺堟潈绫诲瀷" required>
          <el-select v-model="grantForm.benefit_type" style="width: 100%">
            <el-option label="鏃堕棿鎺堟潈" value="time" />
            <el-option label="娆℃暟鎺堟潈" value="times" />
            <el-option label="绉垎鎺堟潈" value="points" />
          </el-select>
        </el-form-item>
        <template v-if="grantForm.benefit_type === 'time'">
          <el-form-item label="姘镐箙鎺堟潈">
            <el-switch v-model="grantForm.is_lifetime" />
          </el-form-item>
          <el-form-item v-if="!grantForm.is_lifetime" label="鎺堟潈澶╂暟" required>
            <el-input-number v-model="grantForm.days" :min="1" :max="36500" style="width: 100%" />
          </el-form-item>
        </template>
        <el-form-item v-else :label="grantForm.benefit_type === 'times' ? '鎺堟潈娆℃暟' : '鎺堟潈绉垎'" required>
          <el-input-number v-model="grantForm.amount" :min="1" :max="100000000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="鏉ユ簮鍗″瘑">
          <el-input v-model="grantForm.source_kami_code" clearable placeholder="鍙€夛紝鐢ㄤ簬杩芥函鏉ユ簮鍗″瘑" />
        </el-form-item>
        <el-form-item label="澶囨敞">
          <el-input v-model="grantForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="grantAuthVisible = false">鍙栨秷</el-button>
        <el-button type="primary" :loading="grantingAuthorization" @click="handleGrantAuthorization">纭鍒嗛厤</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="userKamisVisible" :title="`${currentUser?.username || '用户'}的授权明细`" width="1120px">
      <el-table :data="userKamis" v-loading="userKamisLoading" border stripe>
        <el-table-column prop="kami_code" label="鍗″瘑" min-width="190" show-overflow-tooltip />
        <el-table-column label="绫诲瀷" width="100">
          <template #default="{ row }">{{ getTypeText(row.kami_type) }}</template>
        </el-table-column>
        <el-table-column prop="batch_no" label="鎵规" min-width="130" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">{{ getStatusText(row.status) }}</template>
        </el-table-column>
        <el-table-column label="缁戝畾鍏崇郴" width="120">
          <template #default="{ row }">{{ row.binding_relation || '-' }}</template>
        </el-table-column>
        <el-table-column label="鏉冪泭閰嶇疆" width="130">
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
        <el-table-column label="缁戝畾璁惧" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ getBoundDeviceText(row) }}</template>
        </el-table-column>
        <el-table-column label="鍏戞崲鏃堕棿" width="170">
          <template #default="{ row }">{{ formatOptionalTime(row.redeemed_at) }}</template>
        </el-table-column>
        <el-table-column label="鏈€杩戞牳閿€" width="170">
          <template #default="{ row }">{{ formatOptionalTime(row.last_consume_at) }}</template>
        </el-table-column>
        <el-table-column label="最近验证" width="170">
          <template #default="{ row }">{{ formatOptionalTime(row.last_verify_at) }}</template>
        </el-table-column>
        <el-table-column label="鎺堟潈鏉ユ簮" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ getLotSummary(row.authorization_lots) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
    <el-dialog v-model="quotaVisible" :title="`额度管理 - ${quotaForm.username || '用户'}`" width="720px">
      <div v-loading="quotaLoading">
        <el-descriptions v-if="quotaSummary" :column="2" border>
          <el-descriptions-item label="用户">{{ quotaSummary.username || quotaForm.username }}</el-descriptions-item>
          <el-descriptions-item label="额度账户ID">{{ quotaSummary.quota_account_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="建站额度">{{ quotaSummary.app_create_balance ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="发卡额度">{{ quotaSummary.kami_issue_balance ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="充值额度">{{ quotaSummary.recharge_balance ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatOptionalTime(quotaSummary.updated_at) }}</el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <el-form :model="quotaForm" label-width="100px">
          <el-form-item label="额度类型" required>
            <el-select v-model="quotaForm.quota_type" style="width: 100%">
              <el-option label="建站额度" value="app_create" />
              <el-option label="发卡额度" value="kami_issue" />
              <el-option label="充值额度" value="recharge" />
            </el-select>
          </el-form-item>
          <el-form-item label="发放数量" required>
            <el-input-number v-model="quotaForm.amount" :min="1" :max="100000000" style="width: 100%" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="quotaForm.remark" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="quotaVisible = false">取消</el-button>
        <el-button type="primary" :loading="quotaSaving" @click="handleGrantUserQuota">确认发放</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="appAuthVisible" :title="`应用授权 - ${appAuthForm.username || '用户'}`" width="760px">
      <div v-loading="appAuthLoading">
        <el-table :data="appAuthorizations" border stripe height="260">
          <el-table-column prop="app_name" label="应用名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="app_id" label="App ID" min-width="170" show-overflow-tooltip />
          <el-table-column prop="granted_by" label="授权人" width="120" />
          <el-table-column prop="created_at" label="授权时间" width="180">
            <template #default="{ row }">{{ formatOptionalTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
        </el-table>
        <el-divider />
        <el-form :model="appAuthForm" label-width="100px">
          <el-form-item label="授权应用" required>
            <el-select v-model="appAuthForm.app_id" filterable placeholder="选择应用" style="width: 100%">
              <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
            </el-select>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="appAuthForm.remark" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="appAuthVisible = false">取消</el-button>
        <el-button type="primary" :loading="appAuthSaving" @click="handleGrantUserAppAuthorization">确认授权</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteEndUsers,
  exportEndUsers,
  getEndUserAppAuthorizations,
  getEndUserQuotas,
  getEndUserKamis,
  getEndUsers,
  getEndUserStats,
  grantAuthorization,
  grantEndUserAppAuthorization,
  grantEndUserQuota,
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
const deletingUsers = ref(false)
const userKamisLoading = ref(false)
const quotaLoading = ref(false)
const quotaSaving = ref(false)
const appAuthLoading = ref(false)
const appAuthSaving = ref(false)
const resetPasswordVisible = ref(false)
const grantAuthVisible = ref(false)
const userKamisVisible = ref(false)
const quotaVisible = ref(false)
const appAuthVisible = ref(false)
const users = ref([])
const selectedUsers = ref([])
const userKamis = ref([])
const quotaSummary = ref(null)
const appAuthorizations = ref([])
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

const quotaForm = reactive({
  user_id: null,
  username: '',
  quota_type: 'app_create',
  amount: 1,
  remark: ''
})

const appAuthForm = reactive({
  user_id: null,
  username: '',
  app_id: '',
  remark: ''
})

const statItems = computed(() => [
  { label: '鐢ㄦ埛鎬绘暟', value: stats.value.total },
  { label: '浠婃棩鏂板', value: stats.value.today_new },
  { label: '鍚敤鐢ㄦ埛', value: stats.value.active },
  { label: '绂佺敤鐢ㄦ埛', value: stats.value.disabled },
  { label: '有授权用户', value: stats.value.with_authorization ?? stats.value.with_balance },
  {
    label: '娆℃暟/绉垎浣欓',
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
    selectedUsers.value = []
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

const handleSelectionChange = (selection) => {
  selectedUsers.value = selection
}

const handleDeleteSelectedUsers = async () => {
  if (!selectedUsers.value.length) {
    ElMessage.warning('璇峰厛閫夋嫨瑕佸垹闄ょ殑鐢ㄦ埛')
    return
  }
  const count = selectedUsers.value.length
  try {
    await ElMessageBox.confirm(
      `确定永久删除选中的 ${count} 个用户吗？该操作会同步删除授权、积分、已兑换卡密、设备和日志数据，且无法恢复。`,
      '永久删除用户',
      {
        type: 'warning',
        confirmButtonText: '姘镐箙鍒犻櫎',
        cancelButtonText: '鍙栨秷',
        confirmButtonClass: 'el-button--danger'
      }
    )
    deletingUsers.value = true
    await deleteEndUsers({
      user_ids: selectedUsers.value.map((item) => item.id)
    })
    ElMessage.success('鐢ㄦ埛鍙婂叧鑱旀暟鎹凡鍒犻櫎')
    await loadData()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  } finally {
    deletingUsers.value = false
  }
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
    ElMessage.warning('璇烽€夋嫨搴旂敤')
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

const getQuotaTypeLabel = (quotaType) => {
  const typeMap = {
    app_create: '寤虹珯棰濆害',
    kami_issue: '鍙戝崱棰濆害',
    recharge: '充值额度',
  }
  return typeMap[quotaType] || quotaType
}

const loadUserQuota = async (userId) => {
  quotaLoading.value = true
  try {
    const res = await getEndUserQuotas(userId)
    quotaSummary.value = res.data || null
  } finally {
    quotaLoading.value = false
  }
}

const showQuotaDialog = async (row) => {
  currentUser.value = row
  quotaForm.user_id = row.id
  quotaForm.username = row.username
  quotaForm.quota_type = 'app_create'
  quotaForm.amount = 1
  quotaForm.remark = ''
  quotaVisible.value = true
  await loadUserQuota(row.id)
}

const handleGrantUserQuota = async () => {
  if (!quotaForm.amount || quotaForm.amount <= 0) {
    ElMessage.warning('请输入正数额度')
    return
  }
  quotaSaving.value = true
  try {
    await grantEndUserQuota(quotaForm.user_id, {
      quota_type: quotaForm.quota_type,
      amount: quotaForm.amount,
      remark: quotaForm.remark || null
    })
    ElMessage.success('额度已发放')
    await loadUserQuota(quotaForm.user_id)
    await loadUsers()
  } finally {
    quotaSaving.value = false
  }
}

const loadUserAppAuthorizations = async (userId) => {
  appAuthLoading.value = true
  try {
    const res = await getEndUserAppAuthorizations(userId)
    appAuthorizations.value = res.data || []
  } finally {
    appAuthLoading.value = false
  }
}

const showAppAuthorizationDialog = async (row) => {
  currentUser.value = row
  appAuthForm.user_id = row.id
  appAuthForm.username = row.username
  appAuthForm.app_id = queryParams.app_id || apps.value[0]?.app_id || ''
  appAuthForm.remark = ''
  appAuthVisible.value = true
  await loadUserAppAuthorizations(row.id)
}

const handleGrantUserAppAuthorization = async () => {
  if (!appAuthForm.app_id) {
    ElMessage.warning('璇烽€夋嫨搴旂敤')
    return
  }
  appAuthSaving.value = true
  try {
    await grantEndUserAppAuthorization(appAuthForm.user_id, {
      app_id: appAuthForm.app_id,
      remark: appAuthForm.remark || null
    })
    ElMessage.success('应用授权已发放')
    await loadUserAppAuthorizations(appAuthForm.user_id)
    await loadUsers()
  } finally {
    appAuthSaving.value = false
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
  const action = nextStatus === 1 ? '鍚敤' : '绂佺敤'
  try {
    await ElMessageBox.confirm(`确定要${action}该用户吗？`, '提示', { type: 'warning' })
    await updateEndUserStatus(row.id, nextStatus)
    ElMessage.success(`${action}鎴愬姛`)
    await loadData()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

const getCardQuotaText = (row) => {
  if (row.kami_type === 'points') return `${row.points_amount || 0}绉垎`
  if (row.kami_type === 'times') return `${row.times_total || 0}次`
  return getValidityText(row)
}

const getRemainingBenefitText = (row) => {
  if (row.kami_type === 'points') return `${row.point_source_remaining ?? row.points_remaining ?? row.point_remaining_balance ?? row.points_amount ?? 0}绉垎`
  if (row.kami_type === 'times') return `${row.times_remaining ?? 0}次`
  if (row.kami_type === 'lifetime') return '姘镐箙'
  return row.expire_time ? formatBeijingTime(row.expire_time) : getValidityText(row)
}

const getBoundDeviceText = (row) => {
  if (row?.authorization_owner === 'user' || row?.binding_relation === '鐢ㄦ埛鎺堟潈') return '-'
  if (row?.bind_uuid) return row.bind_uuid
  if (row?.device_bind_count) return `${row.device_bind_count} 台设备`
  return '-'
}

const getLotSummary = (lots = []) => {
  if (!lots.length) return '-'
  return lots
    .map((lot) => {
      const typeMap = { time: '鏃堕棿', times: '娆℃暟', points: '绉垎' }
      const type = typeMap[lot.benefit_type] || lot.benefit_type
      return `${type}:${lot.amount_remaining}/${lot.amount_total}`
    })
    .join('，')
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


