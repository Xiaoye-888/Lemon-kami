<template>
  <div class="merchant-apps">
    <div class="page-toolbar">
      <div>
        <h2>我的应用</h2>
        <p>管理自建应用和管理员授权应用</p>
      </div>
      <div class="actions">
        <el-button type="primary" :loading="creating" @click="openCreateDialog">新建应用</el-button>
        <el-button :loading="loading" @click="loadApps">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="page-card">
      <el-table :data="apps" v-loading="loading" border stripe>
        <el-table-column prop="name" label="应用名称" min-width="170" show-overflow-tooltip />
        <el-table-column prop="app_id" label="App ID" min-width="190" show-overflow-tooltip />
        <el-table-column label="来源" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_owned ? 'success' : 'info'" effect="plain">
              {{ row.is_owned ? '自建应用' : '授权应用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">{{ row.status === 1 ? '启用' : '停用' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right" align="left">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="openDetailDialog(row)">详情</el-button>
              <el-button link type="primary" @click="openInterfacesDialog(row)">接口列表</el-button>
              <el-button link type="primary" @click="goBatches(row)">规格批次</el-button>
              <el-button v-if="row.is_owned" link type="primary" @click="showEditDialog(row)">改名</el-button>
              <el-button v-if="row.is_owned" link type="danger" @click="showDeleteDialog(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="新建应用" width="420px">
      <el-form :model="createForm" label-width="86px">
        <el-form-item label="应用名称" required>
          <el-input v-model="createForm.name" maxlength="64" placeholder="请输入应用名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreateApp">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createResultVisible" title="创建成功" width="560px">
      <div v-if="createdApp" class="credential-panel">
        <div class="credential-row">
          <span>应用名称</span>
          <strong>{{ createdApp.name }}</strong>
        </div>
        <div class="credential-row">
          <span>App ID</span>
          <strong>{{ createdApp.app_id }}</strong>
        </div>
        <div class="credential-row">
          <span>来源</span>
          <strong>{{ createdApp.is_owned ? '自建应用' : '授权应用' }}</strong>
        </div>
      </div>
      <template #footer>
        <el-button @click="createResultVisible = false">关闭</el-button>
        <el-button type="primary" @click="goBatches(createdApp)">配置规格</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="应用详情" width="640px">
      <div v-if="detailApp" class="detail-panel">
        <div class="credential-row">
          <span>应用名称</span>
          <strong>{{ detailApp.name }}</strong>
        </div>
        <div class="credential-row">
          <span>App ID</span>
          <strong>{{ detailApp.app_id }}</strong>
        </div>
        <div class="credential-row">
          <span>来源</span>
          <strong>{{ detailApp.is_owned ? '自建应用' : '授权应用' }}</strong>
        </div>
        <div class="credential-row">
          <span>状态</span>
          <strong>{{ detailApp.status === 1 ? '启用' : '停用' }}</strong>
        </div>
        <div class="credential-row">
          <span>创建时间</span>
          <strong>{{ formatBeijingTime(detailApp.created_at) }}</strong>
        </div>
        <div class="credential-row">
          <span>App Secret</span>
          <code>{{ detailApp.is_owned ? detailApp.app_secret : '授权应用不公开密钥' }}</code>
        </div>
        <div class="credential-row credential-row--public">
          <span>RSA 公钥</span>
          <code>{{ detailApp.is_owned ? detailApp.rsa_public_key : '授权应用不公开密钥' }}</code>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="goBatches(detailApp)">规格批次</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="改名" width="420px">
      <el-form :model="editForm" label-width="86px">
        <el-form-item label="应用名称" required>
          <el-input v-model="editForm.name" maxlength="64" placeholder="请输入新名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="updatingApp" @click="handleUpdateApp">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deleteDialogVisible" title="删除应用" width="420px">
      <div v-if="currentApp" class="delete-panel">
        <el-alert type="warning" :closable="false" show-icon title="删除后应用、规格、批次和卡密相关数据会一并清理。">
          <template #default>
            <div class="delete-summary">
              <div>应用名称：{{ currentApp.name }}</div>
              <div>App ID：{{ currentApp.app_id }}</div>
            </div>
          </template>
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="deletingApp" @click="handleDeleteApp">确认删除</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="interfacesDialogVisible" title="接口列表" width="900px">
      <div v-if="currentApp" class="interfaces-head">
        <div>
          <strong>{{ currentApp.name }}</strong>
          <span> / {{ currentApp.is_owned ? '自建应用' : '授权应用' }}</span>
        </div>
        <el-tag :type="currentApp.is_owned ? 'success' : 'info'" effect="plain">
          {{ currentApp.is_owned ? '自建应用可配置' : '授权应用只读' }}
        </el-tag>
      </div>
      <el-table :data="interfaceRows" v-loading="interfacesLoading" border stripe>
        <el-table-column prop="name" label="接口名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="interface_key" label="接口标识" min-width="160" show-overflow-tooltip />
        <el-table-column prop="path" label="路径" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">{{ row.status === 1 ? '启用' : '停用' }}</template>
        </el-table-column>
        <el-table-column label="配置" width="100">
          <template #default="{ row }">{{ row.configured ? '已配置' : '未配置' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="openInterfaceConfigDialog(row)">
              {{ currentApp?.is_owned ? '配置' : '查看' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="interfacesDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="interfaceConfigDialogVisible"
      :title="currentApp?.is_owned ? '接口配置' : '接口查看'"
      width="620px"
    >
      <div v-if="currentInterface" class="credential-panel">
        <div class="credential-row">
          <span>接口名称</span>
          <strong>{{ currentInterface.name }}</strong>
        </div>
        <div class="credential-row">
          <span>接口标识</span>
          <strong>{{ currentInterface.interface_key }}</strong>
        </div>
      </div>
      <el-form :model="interfaceForm" label-width="96px" class="interface-form">
        <el-form-item label="启用">
          <el-switch v-model="interfaceForm.enabled" :disabled="!canEditCurrentAppInterfaces" />
        </el-form-item>
        <el-form-item label="额度限制">
          <el-input-number
            v-model="interfaceForm.quota_limit"
            :min="0"
            :max="999999999"
            :disabled="!canEditCurrentAppInterfaces"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="过期时间">
          <el-date-picker
            v-model="interfaceForm.expires_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            format="YYYY-MM-DD HH:mm:ss"
            placeholder="可选"
            :disabled="!canEditCurrentAppInterfaces"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="interfaceForm.remark"
            type="textarea"
            :rows="2"
            maxlength="200"
            :disabled="!canEditCurrentAppInterfaces"
          />
        </el-form-item>
        <el-form-item label="配置 JSON">
          <el-input
            v-model="interfaceForm.configText"
            type="textarea"
            :rows="8"
            placeholder="请输入 JSON 配置"
            :disabled="!canEditCurrentAppInterfaces"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="interfaceConfigDialogVisible = false">取消</el-button>
        <el-button
          v-if="canEditCurrentAppInterfaces"
          type="primary"
          :loading="savingInterfaceConfig"
          @click="saveInterfaceConfig"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { formatBeijingTime } from '../utils/datetime'
import {
  createMerchantApp,
  deleteMerchantApp,
  getMerchantAppDetail,
  getMerchantApps,
  getMerchantAppInterfaces,
  updateMerchantApp,
  updateMerchantAppInterface
} from '../api/merchant'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const updatingApp = ref(false)
const deletingApp = ref(false)
const interfacesLoading = ref(false)
const savingInterfaceConfig = ref(false)
const apps = ref([])
const createDialogVisible = ref(false)
const createResultVisible = ref(false)
const detailDialogVisible = ref(false)
const editDialogVisible = ref(false)
const deleteDialogVisible = ref(false)
const interfacesDialogVisible = ref(false)
const interfaceConfigDialogVisible = ref(false)
const createdApp = ref(null)
const detailApp = ref(null)
const currentApp = ref(null)
const currentInterface = ref(null)
const interfaceRows = ref([])
const canEditCurrentAppInterfaces = computed(() => currentApp.value?.is_owned === true)
const createForm = reactive({ name: '' })
const editForm = reactive({ name: '' })
const interfaceForm = reactive({
  enabled: true,
  quota_limit: null,
  expires_at: '',
  remark: '',
  configText: '{}'
})

function openCreateDialog() {
  createForm.name = ''
  createDialogVisible.value = true
}

async function loadApps() {
  loading.value = true
  try {
    const res = await getMerchantApps()
    apps.value = res.data || []
  } finally {
    loading.value = false
  }
}

async function handleCreateApp() {
  const name = createForm.name.trim()
  if (!name) {
    ElMessage.warning('请输入应用名称')
    return
  }
  creating.value = true
  try {
    const res = await createMerchantApp({ name })
    createdApp.value = res.data || null
    createDialogVisible.value = false
    createResultVisible.value = true
    ElMessage.success('应用已创建')
    await loadApps()
  } finally {
    creating.value = false
  }
}

async function openDetailDialog(row) {
  if (!row?.app_id) return
  currentApp.value = row
  try {
    const res = await getMerchantAppDetail(row.app_id)
    detailApp.value = res.data || row
  } catch {
    detailApp.value = row
  }
  detailDialogVisible.value = true
}

function showEditDialog(row) {
  currentApp.value = row
  editForm.name = row.name || ''
  editDialogVisible.value = true
}

async function handleUpdateApp() {
  if (!currentApp.value?.app_id) return
  const name = editForm.name.trim()
  if (!name) {
    ElMessage.warning('请输入应用名称')
    return
  }
  updatingApp.value = true
  try {
    await updateMerchantApp(currentApp.value.app_id, { name })
    ElMessage.success('应用已改名')
    editDialogVisible.value = false
    await loadApps()
    if (detailDialogVisible.value) {
      await openDetailDialog({ app_id: currentApp.value.app_id })
    }
  } finally {
    updatingApp.value = false
  }
}

function showDeleteDialog(row) {
  currentApp.value = row
  deleteDialogVisible.value = true
}

async function handleDeleteApp() {
  if (!currentApp.value?.app_id) return
  deletingApp.value = true
  try {
    await deleteMerchantApp(currentApp.value.app_id)
    ElMessage.success('应用已删除')
    deleteDialogVisible.value = false
    detailDialogVisible.value = false
    interfacesDialogVisible.value = false
    await loadApps()
  } finally {
    deletingApp.value = false
  }
}

async function openInterfacesDialog(row) {
  if (!row?.app_id) return
  currentApp.value = row
  interfacesLoading.value = true
  try {
    const res = await getMerchantAppInterfaces(row.app_id)
    interfaceRows.value = res.data || []
    interfacesDialogVisible.value = true
  } finally {
    interfacesLoading.value = false
  }
}

function openInterfaceConfigDialog(row) {
  currentInterface.value = row
  interfaceForm.enabled = row.enabled !== undefined ? row.enabled : true
  interfaceForm.quota_limit = row.quota_limit ?? null
  interfaceForm.expires_at = row.expires_at || ''
  interfaceForm.remark = row.remark || ''
  const config = row.config && typeof row.config === 'object' ? row.config : {}
  interfaceForm.configText = JSON.stringify(config, null, 2)
  interfaceConfigDialogVisible.value = true
}

function goBatches(row) {
  if (!row?.app_id) return
  createResultVisible.value = false
  detailDialogVisible.value = false
  router.push({ path: '/merchant/batches', query: { app_id: row.app_id } })
}

async function saveInterfaceConfig() {
  if (!canEditCurrentAppInterfaces.value) return
  if (!currentApp.value?.app_id || !currentInterface.value?.interface_id) return
  let config = null
  const configText = interfaceForm.configText?.trim()
  if (configText) {
    try {
      config = JSON.parse(configText)
    } catch {
      ElMessage.error('接口配置 JSON 格式不正确')
      return
    }
  }
  savingInterfaceConfig.value = true
  try {
    await updateMerchantAppInterface(currentApp.value.app_id, currentInterface.value.interface_id, {
      enabled: interfaceForm.enabled,
      quota_limit: interfaceForm.quota_limit,
      expires_at: interfaceForm.expires_at || null,
      remark: interfaceForm.remark || null,
      config
    })
    ElMessage.success('接口配置已保存')
    interfaceConfigDialogVisible.value = false
    await openInterfacesDialog(currentApp.value)
  } finally {
    savingInterfaceConfig.value = false
  }
}

onMounted(loadApps)
</script>

<style scoped>
.merchant-apps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar,
.actions,
.interfaces-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  max-width: 100%;
  white-space: nowrap;
}

.row-actions :deep(.el-button) {
  margin-left: 0;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
}

.page-card {
  border-radius: 8px;
}

.credential-panel,
.detail-panel,
.delete-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.credential-row {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.credential-row span {
  color: #64748b;
}

.credential-row strong,
.credential-row code {
  color: #0f172a;
  word-break: break-all;
}

.credential-row--public code {
  max-height: 180px;
  overflow: auto;
  padding: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
  white-space: pre-wrap;
}

.delete-summary {
  margin-top: 10px;
  display: grid;
  gap: 6px;
  color: #475569;
  font-size: 13px;
}

.interface-form {
  margin-top: 12px;
}

@media (max-width: 720px) {
  .credential-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
