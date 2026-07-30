<template>
  <div class="merchant-detail-page">
    <div class="page-toolbar">
      <div>
        <el-button plain :icon="ArrowLeft" @click="goBack">返回发卡用户管理</el-button>
        <h2>发卡用户详情 - {{ merchantDetail.profile?.username || '-' }}</h2>
        <p>查看当前发卡用户的自建应用、授权应用和使用用户，并进入该用户作用域批次管理。</p>
      </div>
      <el-button :icon="Refresh" :loading="merchantDetailLoading" @click="loadDetail">刷新</el-button>
    </div>

    <section class="merchant-detail-summary">
      <div data-contract="merchantDetail.profile">
        <span class="summary-label">用户名</span>
        <strong>{{ merchantDetail.profile?.username || '-' }}</strong>
      </div>
      <div data-contract="merchantDetail.quota">
        <span class="summary-label">发卡额度</span>
        <strong>{{ merchantIssueBalance }}</strong>
      </div>
      <div data-contract="merchantDetail.self_owned_apps">
        <span class="summary-label">自建应用</span>
        <strong>{{ merchantDetail.self_owned_apps.length }}</strong>
      </div>
      <div data-contract="merchantDetail.usage_users">
        <span class="summary-label">使用用户</span>
        <strong>{{ merchantDetail.usage_users.length }}</strong>
      </div>
    </section>

    <el-card shadow="never" class="detail-panel" v-loading="merchantDetailLoading">
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
            <el-table-column label="操作" width="420" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button size="small" type="primary" plain @click="showGenerateForApp(row)">生成卡密</el-button>
                  <el-button size="small" plain @click="showBatchesForApp(row)">批次管理</el-button>
                  <el-button size="small" type="primary" plain @click="goAppInterfaces(row)">接口列表</el-button>
                  <el-button size="small" type="primary" plain @click="openEditApp(row)">改名</el-button>
                  <el-button size="small" type="info" @click="viewAppDetail(row)">详情</el-button>
                  <el-button size="small" type="danger" @click="handleDeleteApp(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="授权应用" name="authorized_apps" data-contract="merchantDetail.authorized_apps">
          <el-table :data="merchantDetail.authorized_apps" border stripe>
            <el-table-column prop="name" label="应用名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="app_id" label="App ID" min-width="180" show-overflow-tooltip />
            <el-table-column prop="granted_by" label="授权人" width="120" />
            <el-table-column prop="authorized_at" label="授权时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.authorized_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="300" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button size="small" type="primary" plain @click="showGenerateForApp(row)">生成卡密</el-button>
                  <el-button size="small" plain @click="showBatchesForApp(row)">批次管理</el-button>
                  <el-button size="small" type="primary" plain @click="goAppInterfaces(row)">接口列表</el-button>
                  <el-button size="small" type="info" @click="viewAppDetail(row)">详情</el-button>
                </div>
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
    </el-card>

    <el-dialog v-model="editDialogVisible" title="修改自建应用名称" width="500px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="应用名称" required>
          <el-input v-model="editForm.name" maxlength="80" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="updatingApp" @click="submitEditApp">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="应用详情" width="700px">
      <el-descriptions :column="1" border v-if="currentApp">
        <el-descriptions-item label="应用名称">{{ currentApp.name }}</el-descriptions-item>
        <el-descriptions-item label="App ID">{{ currentApp.app_id }}</el-descriptions-item>
        <el-descriptions-item label="归属">{{ currentApp.is_owned ? '自建应用' : '授权应用' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ currentApp.status === 1 ? '启用' : '禁用' }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ currentApp.created_by || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatOptionalTime(currentApp.created_at) }}</el-descriptions-item>
        <el-descriptions-item v-if="currentApp.is_owned" label="RSA 公钥">
          <el-input :model-value="currentApp.rsa_public_key || ''" type="textarea" :rows="5" readonly />
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import {
  deleteCommercialMerchantApp,
  getCommercialMerchantDetail,
  updateCommercialMerchantApp
} from '../api/commercial'
import { formatBeijingTime } from '../utils/datetime'

const route = useRoute()
const router = useRouter()
const merchantDetailLoading = ref(false)
const merchantDetailTabs = ref('self_owned_apps')
const editDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const updatingApp = ref(false)
const currentApp = ref(null)
const editForm = reactive({
  app_id: '',
  name: ''
})
const merchantDetail = ref({
  profile: null,
  quota: {},
  self_owned_apps: [],
  authorized_apps: [],
  usage_users: []
})
const CONFIRM_DELETE_APP = '确认删除应用'

const merchantId = computed(() => String(route.params.merchantId || ''))
const merchantIssueBalance = computed(
  () => merchantDetail.value.quota?.kami_issue_balance ?? merchantDetail.value.profile?.kami_issue_balance ?? 0
)

function formatOptionalTime(value) {
  return value ? formatBeijingTime(value) : '-'
}

function goBack() {
  router.push({ name: 'AdminMerchants' })
}

function batchManagementRoute(app, action) {
  const query = { app_id: app.app_id }
  if (action) query.action = action
  return {
    name: 'AdminMerchantBatches',
    params: { merchantId: merchantId.value },
    query
  }
}

function showBatchesForApp(row) {
  if (!row?.app_id || !merchantId.value) return
  router.push(batchManagementRoute(row))
}

function showGenerateForApp(row) {
  if (!row?.app_id || !merchantId.value) return
  router.push(batchManagementRoute(row, 'generate'))
}

function goAppInterfaces(row) {
  if (!row?.app_id) return
  router.push({
    path: `/admin/apps/${row.app_id}/interfaces`,
    query: { app_name: row.name, merchant_id: merchantId.value }
  })
}

function openEditApp(row) {
  if (!row?.can_rename) return
  editForm.app_id = row.app_id
  editForm.name = row.name || ''
  editDialogVisible.value = true
}

function viewAppDetail(row) {
  currentApp.value = row
  detailDialogVisible.value = true
}

async function submitEditApp() {
  const name = editForm.name.trim()
  if (!name) {
    ElMessage.warning('请输入应用名称')
    return
  }
  updatingApp.value = true
  try {
    await updateCommercialMerchantApp(merchantId.value, editForm.app_id, { name })
    ElMessage.success('应用名称已更新')
    editDialogVisible.value = false
    await loadDetail()
  } finally {
    updatingApp.value = false
  }
}

async function handleDeleteApp(row) {
  if (!row?.can_delete) return
  try {
    await ElMessageBox.confirm(
      `确定要删除自建应用“${row.name}”吗？此操作会删除该应用下的卡密、批次、规格、公告、版本、接口配置、设备和日志记录。`,
      '警告',
      {
        confirmButtonText: '继续',
        cancelButtonText: '取消',
        type: 'error',
        distinguishCancelAndClose: true
      }
    )
    const { value } = await ElMessageBox.prompt(`请输入「${CONFIRM_DELETE_APP}」以确认`, '删除应用确认', {
      inputValue: '',
      inputValidator: (value) => value === CONFIRM_DELETE_APP || `请输入${CONFIRM_DELETE_APP}`,
      type: 'error'
    })
    await deleteCommercialMerchantApp(merchantId.value, row.app_id, { confirm_text: value })
    ElMessage.success('应用已删除')
    await loadDetail()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除发卡用户自建应用失败:', error)
    }
  }
}

async function loadDetail() {
  if (!merchantId.value) return
  merchantDetailLoading.value = true
  try {
    const res = await getCommercialMerchantDetail(merchantId.value)
    const data = res.data || {}
    merchantDetail.value = {
      profile: data.profile || null,
      quota: data.quota || {},
      self_owned_apps: data.self_owned_apps || [],
      authorized_apps: data.authorized_apps || [],
      usage_users: data.usage_users || []
    }
  } finally {
    merchantDetailLoading.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.merchant-detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.page-toolbar h2 {
  margin: 14px 0 0;
  font-size: 26px;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
}

.merchant-detail-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.merchant-detail-summary > div {
  border: 1px solid #dbeafe;
  border-radius: 8px;
  padding: 16px;
  background: #f8fbff;
}

.summary-label {
  display: block;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 13px;
}

.summary-label + strong {
  font-size: 22px;
}

.detail-panel {
  border-radius: 8px;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
}

.row-actions :deep(.el-button) {
  margin-left: 0;
  border-radius: 8px;
  font-weight: 600;
}

.merchant-detail-tabs {
  min-width: 0;
}

@media (max-width: 960px) {
  .merchant-detail-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .page-toolbar {
    flex-direction: column;
  }

  .merchant-detail-summary {
    grid-template-columns: 1fr;
  }
}
</style>
