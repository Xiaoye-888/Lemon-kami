<template>
  <div class="admin-page">
    <div class="page-toolbar">
      <div>
        <h2>发卡用户管理</h2>
        <p>管理可登录商户控制台并消耗发卡额度的账号</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <el-card shadow="never">
      <el-form :inline="true" :model="query" class="filter-form">
        <el-form-item label="关键词">
          <el-input v-model="query.keyword" clearable placeholder="用户名/邮箱" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
            <el-option label="启用" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="140">
          <template #default="{ row }">
            <el-button link type="primary" class="username-link" @click="openMerchantDetail(row)">
              {{ row.username }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="phone" label="手机号" min-width="130" />
        <el-table-column prop="kami_issue_balance" label="发卡额度" width="120" />
        <el-table-column prop="total_kami_issue_granted" label="累计入账" width="120" />
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
        <el-table-column prop="last_login" label="最近登录" width="180">
          <template #default="{ row }">{{ formatOptionalTime(row.last_login) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="openQuotaDialog(row)">发放额度</el-button>
            <el-button size="small" type="success" plain @click="openAppAuthDialog(row)">应用授权</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pager"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>

    <el-dialog v-model="quotaDialogVisible" :title="`发放发卡额度 - ${currentMerchant?.username || ''}`" width="460px">
      <el-form :model="quotaForm" label-width="100px">
        <el-form-item label="额度类型">
          <el-input model-value="发卡额度" disabled />
        </el-form-item>
        <el-form-item label="发放数量" required>
          <el-input-number v-model="quotaForm.amount" :min="1" :max="100000000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="quotaForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quotaDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="quotaSaving" @click="submitIssueQuotaGrant">确认发放</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="appAuthDialogVisible" :title="`应用授权 - ${currentMerchant?.username || ''}`" width="760px">
      <div v-loading="appAuthLoading">
        <el-table :data="appAuthorizations" border stripe height="220">
          <el-table-column prop="app_name" label="应用名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="app_id" label="App ID" min-width="170" show-overflow-tooltip />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                type="danger"
                plain
                :loading="appAuthRevoking === row.id"
                @click="handleRevokeAppAuthorization(row)"
              >
                撤销
              </el-button>
            </template>
          </el-table-column>
          <el-table-column prop="granted_by" label="授权人" width="120" />
          <el-table-column prop="created_at" label="授权时间" width="180">
            <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
          </el-table-column>
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
        <el-button @click="appAuthDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="appAuthSaving" @click="submitAppAuthorization">确认授权</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="merchantDetailVisible"
      :title="`发卡用户详情 - ${merchantDetail.profile?.username || currentMerchant?.username || ''}`"
      size="860px"
      class="merchant-detail-drawer"
    >
      <div v-loading="merchantDetailLoading" class="merchant-detail">
        <div class="merchant-detail-summary">
          <div>
            <span class="summary-label">用户名</span>
            <strong>{{ merchantDetail.profile?.username || '-' }}</strong>
          </div>
          <div>
            <span class="summary-label">发卡额度</span>
            <strong>{{ merchantDetail.quota?.kami_issue_balance ?? merchantDetail.profile?.kami_issue_balance ?? 0 }}</strong>
          </div>
          <div>
            <span class="summary-label">自建应用</span>
            <strong>{{ merchantDetail.self_owned_apps.length }}</strong>
          </div>
          <div>
            <span class="summary-label">使用用户</span>
            <strong>{{ merchantDetail.usage_users.length }}</strong>
          </div>
        </div>

        <el-tabs v-model="merchantDetailTabs" class="merchant-detail-tabs">
          <el-tab-pane label="自建应用" name="self_owned_apps">
            <el-table :data="merchantDetail.self_owned_apps" border stripe>
              <el-table-column prop="name" label="应用名称" min-width="160" show-overflow-tooltip />
              <el-table-column prop="app_id" label="App ID" min-width="180" show-overflow-tooltip />
              <el-table-column prop="status" label="状态" width="90">
                <template #default="{ row }">
                  <el-tag :type="row.status === 1 ? 'success' : 'danger'">
                    {{ row.status === 1 ? '启用' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="创建时间" width="180">
                <template #default="{ row }">{{ formatOptionalTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="180" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="primary" plain @click="openMerchantAppKamis(row)">生成卡密</el-button>
                  <el-button size="small" plain @click="openMerchantAppBatches(row)">批次管理</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="授权应用" name="authorized_apps">
            <el-table :data="merchantDetail.authorized_apps" border stripe>
              <el-table-column prop="app_name" label="应用名称" min-width="160" show-overflow-tooltip />
              <el-table-column prop="app_id" label="App ID" min-width="180" show-overflow-tooltip />
              <el-table-column prop="granted_by" label="授权人" width="120" />
              <el-table-column prop="created_at" label="授权时间" width="180">
                <template #default="{ row }">{{ formatOptionalTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="180" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="primary" plain @click="openMerchantAppKamis(row)">生成卡密</el-button>
                  <el-button size="small" plain @click="openMerchantAppBatches(row)">批次管理</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="使用用户" name="usage_users">
            <el-table :data="merchantDetail.usage_users" border stripe>
              <el-table-column prop="username" label="用户名" min-width="150" show-overflow-tooltip />
              <el-table-column prop="app_name" label="应用" min-width="150" show-overflow-tooltip />
              <el-table-column prop="device_uuid" label="设备 UUID" min-width="180" show-overflow-tooltip />
              <el-table-column prop="last_seen_at" label="最近使用" width="180">
                <template #default="{ row }">{{ formatOptionalTime(row.last_seen_at) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { getCommercialMerchantDetail, getCommercialMerchants } from '../api/commercial'
import { getApps } from '../api/admin'
import {
  getEndUserAppAuthorizations,
  grantEndUserAppAuthorization,
  grantEndUserQuota,
  revokeEndUserAppAuthorization
} from '../api/points'
import { formatBeijingTime } from '../utils/datetime'

const router = useRouter()
const loading = ref(false)
const quotaSaving = ref(false)
const appAuthLoading = ref(false)
const appAuthSaving = ref(false)
const appAuthRevoking = ref('')
const quotaDialogVisible = ref(false)
const appAuthDialogVisible = ref(false)
const merchantDetailVisible = ref(false)
const merchantDetailLoading = ref(false)
const merchantDetailTabs = ref('self_owned_apps')
const rows = ref([])
const total = ref(0)
const apps = ref([])
const appAuthorizations = ref([])
const currentMerchant = ref(null)
const merchantDetail = ref({
  profile: null,
  quota: {},
  self_owned_apps: [],
  authorized_apps: [],
  usage_users: []
})
const query = reactive({
  keyword: '',
  status: '',
  page: 1,
  page_size: 20
})
const quotaForm = reactive({
  amount: 1,
  remark: ''
})
const appAuthForm = reactive({
  app_id: '',
  remark: ''
})
const CONFIRM_GRANT_ISSUE_QUOTA = '确认调整额度'
const CONFIRM_GRANT_APP_AUTHORIZATION = '确认授权应用'

const CONFIRM_REVOKE_APP_AUTHORIZATION = '确认取消授权'

const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

const normalizedQuery = () => {
  const params = { ...query }
  if (!params.keyword) delete params.keyword
  if (params.status === '') delete params.status
  return params
}

async function loadData() {
  loading.value = true
  try {
    const res = await getCommercialMerchants(normalizedQuery())
    rows.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  loadData()
}

async function openMerchantDetail(row) {
  currentMerchant.value = row
  merchantDetailVisible.value = true
  merchantDetailTabs.value = 'self_owned_apps'
  merchantDetail.value = {
    profile: row,
    quota: {},
    self_owned_apps: [],
    authorized_apps: [],
    usage_users: []
  }
  merchantDetailLoading.value = true
  try {
    const res = await getCommercialMerchantDetail(row.id)
    const data = res.data || {}
    merchantDetail.value = {
      profile: data.profile || row,
      quota: data.quota || {},
      self_owned_apps: data.self_owned_apps || [],
      authorized_apps: data.authorized_apps || [],
      usage_users: data.usage_users || []
    }
  } finally {
    merchantDetailLoading.value = false
  }
}

function openMerchantAppBatches(app) {
  if (!app?.app_id) return
  router.push({ path: '/admin/kamis/batches', query: { app_id: app.app_id } })
}

function openMerchantAppKamis(app) {
  if (!app?.app_id) return
  router.push({ path: '/admin/kamis/list', query: { app_id: app.app_id, action: 'generate' } })
}

function openQuotaDialog(row) {
  currentMerchant.value = row
  quotaForm.amount = 1
  quotaForm.remark = ''
  quotaDialogVisible.value = true
}

async function promptSensitiveConfirm(expected, title) {
  const { value } = await ElMessageBox.prompt(`请输入「${expected}」以确认`, title, {
    inputValue: '',
    inputValidator: (value) => value === expected || `请输入${expected}`,
    type: 'warning'
  })
  return value
}

async function submitIssueQuotaGrant() {
  if (!currentMerchant.value || !quotaForm.amount || quotaForm.amount <= 0) return
  quotaSaving.value = true
  try {
    const confirmText = await promptSensitiveConfirm(CONFIRM_GRANT_ISSUE_QUOTA, '发放额度')
    await grantEndUserQuota(currentMerchant.value.id, {
      quota_type: 'kami_issue',
      amount: quotaForm.amount,
      remark: quotaForm.remark || null,
      confirm_text: confirmText
    })
    quotaDialogVisible.value = false
    await loadData()
  } finally {
    quotaSaving.value = false
  }
}

async function openAppAuthDialog(row) {
  currentMerchant.value = row
  appAuthForm.app_id = apps.value[0]?.app_id || ''
  appAuthForm.remark = ''
  appAuthDialogVisible.value = true
  await loadAppAuthorizations(row.id)
}

async function loadAppAuthorizations(userId) {
  appAuthLoading.value = true
  try {
    const res = await getEndUserAppAuthorizations(userId)
    appAuthorizations.value = res.data || []
  } finally {
    appAuthLoading.value = false
  }
}

async function submitAppAuthorization() {
  if (!currentMerchant.value || !appAuthForm.app_id) return
  appAuthSaving.value = true
  try {
    const confirmText = await promptSensitiveConfirm(CONFIRM_GRANT_APP_AUTHORIZATION, '授权应用')
    await grantEndUserAppAuthorization(currentMerchant.value.id, {
      app_id: appAuthForm.app_id,
      remark: appAuthForm.remark || null,
      confirm_text: confirmText
    })
    await loadAppAuthorizations(currentMerchant.value.id)
  } finally {
    appAuthSaving.value = false
  }
}

async function handleRevokeAppAuthorization(row) {
  if (!currentMerchant.value || !row?.id) return
  appAuthRevoking.value = row.id
  try {
    const confirmText = await promptSensitiveConfirm(CONFIRM_REVOKE_APP_AUTHORIZATION, '撤销应用授权')
    await revokeEndUserAppAuthorization(currentMerchant.value.id, row.id, { confirm_text: confirmText })
    await loadAppAuthorizations(currentMerchant.value.id)
  } finally {
    appAuthRevoking.value = ''
  }
}

async function loadApps() {
  const res = await getApps()
  apps.value = res.data || []
}

onMounted(async () => {
  await Promise.all([loadApps(), loadData()])
})
</script>

<style scoped>
.admin-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
}

.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.username-link {
  padding: 0;
  font-weight: 600;
}

.merchant-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.merchant-detail-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.merchant-detail-summary > div {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  background: #f8fafc;
}

.summary-label {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
}

.merchant-detail-tabs {
  min-width: 0;
}

@media (max-width: 760px) {
  .merchant-detail-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
