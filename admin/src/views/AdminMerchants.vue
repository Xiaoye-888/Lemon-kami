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
        <el-table-column prop="username" label="用户名" min-width="140" />
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
        <el-table-column prop="created_at" label="注册时间" width="180" />
        <el-table-column prop="last_login" label="最近登录" width="180" />
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
          <el-table-column prop="granted_by" label="授权人" width="120" />
          <el-table-column prop="created_at" label="授权时间" width="180" />
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
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getCommercialMerchants } from '../api/commercial'
import { getApps } from '../api/admin'
import {
  getEndUserAppAuthorizations,
  grantEndUserAppAuthorization,
  grantEndUserQuota
} from '../api/points'

const loading = ref(false)
const quotaSaving = ref(false)
const appAuthLoading = ref(false)
const appAuthSaving = ref(false)
const quotaDialogVisible = ref(false)
const appAuthDialogVisible = ref(false)
const rows = ref([])
const total = ref(0)
const apps = ref([])
const appAuthorizations = ref([])
const currentMerchant = ref(null)
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

function openQuotaDialog(row) {
  currentMerchant.value = row
  quotaForm.amount = 1
  quotaForm.remark = ''
  quotaDialogVisible.value = true
}

async function submitIssueQuotaGrant() {
  if (!currentMerchant.value || !quotaForm.amount || quotaForm.amount <= 0) return
  quotaSaving.value = true
  try {
    await grantEndUserQuota(currentMerchant.value.id, {
      quota_type: 'kami_issue',
      amount: quotaForm.amount,
      remark: quotaForm.remark || null
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
    await grantEndUserAppAuthorization(currentMerchant.value.id, {
      app_id: appAuthForm.app_id,
      remark: appAuthForm.remark || null
    })
    await loadAppAuthorizations(currentMerchant.value.id)
  } finally {
    appAuthSaving.value = false
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
</style>
