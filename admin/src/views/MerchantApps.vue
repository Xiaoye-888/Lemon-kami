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
        <el-table-column label="操作" width="260" fixed="right" align="left">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="openDetailDialog(row)">详情</el-button>
              <el-button link type="primary" @click="openInterfacesDialog(row)">接口列表</el-button>
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
        <el-button type="primary" @click="goBatchWorkbench(createdApp)">批次管理</el-button>
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
          <div class="secret-inline">
            <code>{{ maskedAppSecret }}</code>
            <el-button
              v-if="detailApp.is_owned && detailApp.app_secret"
              link
              type="primary"
              :icon="DocumentCopy"
              aria-label="复制 App Secret"
              @click="copyAppSecret"
            />
          </div>
        </div>
        <div class="credential-row credential-row--public">
          <span>RSA 公钥</span>
          <div class="secret-inline">
            <code>{{ maskedRsaPublicKey }}</code>
            <el-button
              v-if="detailApp.is_owned && detailApp.rsa_public_key"
              link
              type="primary"
              :icon="DocumentCopy"
              aria-label="复制 RSA 公钥"
              @click="copyRsaPublicKey"
            />
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="goBatchWorkbench(detailApp)">批次管理</el-button>
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
        <template v-if="currentInterfaceSchema.length">
          <el-form-item v-for="field in currentInterfaceSchema" :key="field.key" :label="field.label">
            <el-switch
              v-if="field.type === 'switch'"
              v-model="interfaceForm.data[field.key]"
              :disabled="!canEditCurrentAppInterfaces"
            />
            <el-input-number
              v-else-if="field.type === 'number'"
              v-model="interfaceForm.data[field.key]"
              :min="field.min ?? 0"
              :max="field.max ?? 999999999"
              :disabled="!canEditCurrentAppInterfaces"
              style="width: 100%"
            />
            <el-input
              v-else
              v-model="interfaceForm.data[field.key]"
              :disabled="!canEditCurrentAppInterfaces"
              style="width: 100%"
            />
            <div v-if="field.help" class="form-help">{{ field.help }}</div>
          </el-form-item>
        </template>
        <el-empty v-else description="该接口暂无可视化配置项" :image-size="80" />
        <el-form-item label="备注">
          <el-input
            v-model="interfaceForm.remark"
            type="textarea"
            :rows="2"
            maxlength="200"
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
import { DocumentCopy } from '@element-plus/icons-vue'
import { formatBeijingTime } from '../utils/datetime'
import { copyTextToClipboard } from '../utils/clipboard'
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
const maskedAppSecret = computed(() => {
  if (!detailApp.value) return '-'
  return detailApp.value.is_owned && detailApp.value.app_secret ? '****************' : '授权应用不公开密钥'
})
const maskedRsaPublicKey = computed(() => {
  if (!detailApp.value) return '-'
  return detailApp.value.is_owned && detailApp.value.rsa_public_key ? '****************' : '授权应用不公开密钥'
})
const createForm = reactive({ name: '' })
const editForm = reactive({ name: '' })
const interfaceForm = reactive({
  enabled: true,
  remark: '',
  data: {}
})

const interfaceConfigSchemas = {
  'user.register': [
    { key: 'allow_register', label: '允许注册', type: 'switch', default: true },
    { key: 'password_min_length', label: '密码最小长度', type: 'number', min: 6, max: 64, default: 6 }
  ],
  'user.login': [
    { key: 'allow_login', label: '允许登录', type: 'switch', default: true },
    { key: 'token_expire_minutes', label: 'Token 有效分钟', type: 'number', min: 5, max: 43200, default: 1440 }
  ],
  'points.balance': [
    { key: 'include_ledger_balance', label: '返回账本余额', type: 'switch', default: true }
  ],
  'points.redeem': [
    { key: 'allow_redeem', label: '允许卡密充值', type: 'switch', default: true },
    { key: 'bind_user_on_redeem', label: '充值后绑定用户', type: 'switch', default: true }
  ],
  'points.consume': [
    { key: 'min_amount', label: '单次最小扣减', type: 'number', min: 1, max: 100000000, default: 1 },
    { key: 'max_amount', label: '单次最大扣减', type: 'number', min: 1, max: 100000000, default: 1000 },
    { key: 'require_biz_id', label: '必须传 biz_id', type: 'switch', default: true }
  ],
  'points.transactions': [
    { key: 'max_page_size', label: '最大分页条数', type: 'number', min: 10, max: 500, default: 100 }
  ],
  'sdk.public_key': [
    { key: 'allow_public_key', label: '允许获取公钥', type: 'switch', default: true }
  ],
  'sdk.verify': [
    {
      key: 'enable_user_authorization',
      label: '启用用户授权能力',
      type: 'switch',
      default: false,
      help: '开启后可在批次管理中为每个批次设置授权归属和用户绑定策略。'
    },
    { key: 'signature_required', label: '签名校验', type: 'switch', default: true },
    { key: 'nonce_required', label: 'Nonce 防重放', type: 'switch', default: true },
    { key: 'timestamp_tolerance_seconds', label: '时间戳容差秒', type: 'number', min: 30, max: 86400, default: 300 },
    { key: 'ip_lock_enabled', label: 'IP 绑定验证', type: 'switch', default: false }
  ],
  'sdk.unbind': [
    { key: 'allow_unbind', label: '允许解绑', type: 'switch', default: false },
    { key: 'max_unbind_count', label: '最大解绑次数', type: 'number', min: 0, max: 100, default: 0 },
    { key: 'unbind_cooldown_hours', label: '解绑冷却小时', type: 'number', min: 0, max: 8760, default: 24 },
    { key: 'unbind_deduct_hours', label: '时间卡扣减小时', type: 'number', min: 0, max: 8760, default: 0 },
    { key: 'unbind_deduct_times', label: '次数卡扣减次数', type: 'number', min: 0, max: 1000000, default: 0 },
    { key: 'ip_lock_enabled', label: '解绑校验 IP', type: 'switch', default: false }
  ],
  'sdk.device_limit': [
    { key: 'release_on_logout', label: '退出自动释放', type: 'switch', default: true },
    { key: 'heartbeat_timeout_seconds', label: '心跳超时秒数', type: 'number', min: 30, max: 86400, default: 180 }
  ],
  'sdk.notice': [
    { key: 'allow_notice_read', label: '允许公告读取', type: 'switch', default: true },
    { key: 'max_notice_length', label: '公告最大长度', type: 'number', min: 100, max: 20000, default: 5000 },
    { key: 'popup_enabled', label: '允许弹窗公告', type: 'switch', default: true }
  ],
  'sdk.update_check': [
    { key: 'allow_update_check', label: '允许版本检查', type: 'switch', default: true },
    { key: 'min_supported_version_code', label: '最低支持版本编码', type: 'number', min: 1, max: 999999999, default: 1 },
    { key: 'force_update_enabled', label: '允许强制更新', type: 'switch', default: true }
  ],
  'sdk.report': [
    { key: 'allow_report', label: '允许事件上报', type: 'switch', default: true },
    { key: 'max_payload_kb', label: '最大载荷 KB', type: 'number', min: 1, max: 1024, default: 64 }
  ]
}

const currentInterfaceSchema = computed(() => {
  if (!currentInterface.value) return []
  return currentInterface.value.config_schema || interfaceConfigSchemas[currentInterface.value.interface_key] || []
})

function schemaDefaults(schema) {
  const data = {}
  schema.forEach((field) => {
    if (Object.prototype.hasOwnProperty.call(field, 'default')) {
      data[field.key] = field.default
    } else {
      data[field.key] = field.type === 'switch' ? false : ''
    }
  })
  return data
}

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
  interfaceForm.remark = row.remark || ''
  const config = row.config && typeof row.config === 'object' ? row.config : {}
  interfaceForm.data = {
    ...schemaDefaults(currentInterfaceSchema.value),
    ...config
  }
  interfaceConfigDialogVisible.value = true
}

function goBatchWorkbench(row) {
  if (!row?.app_id) return
  createResultVisible.value = false
  detailDialogVisible.value = false
  router.push({ path: '/merchant/batches', query: { app_id: row.app_id } })
}

async function copyAppSecret() {
  if (!detailApp.value?.app_secret) {
    ElMessage.warning('暂无 App Secret 可复制')
    return
  }
  await copyTextToClipboard(detailApp.value.app_secret)
  ElMessage.success('复制成功')
}

async function copyRsaPublicKey() {
  if (!detailApp.value?.rsa_public_key) {
    ElMessage.warning('暂无 RSA 公钥可复制')
    return
  }
  await copyTextToClipboard(detailApp.value.rsa_public_key)
  ElMessage.success('复制成功')
}

async function saveInterfaceConfig() {
  if (!canEditCurrentAppInterfaces.value) return
  if (!currentApp.value?.app_id || !currentInterface.value?.interface_id) return
  savingInterfaceConfig.value = true
  try {
    await updateMerchantAppInterface(currentApp.value.app_id, currentInterface.value.interface_id, {
      enabled: interfaceForm.enabled,
      remark: interfaceForm.remark || null,
      config: { ...interfaceForm.data }
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

.actions {
  flex-wrap: nowrap;
  justify-content: flex-end;
  max-width: 100%;
  overflow-x: auto;
  white-space: nowrap;
}

.actions :deep(.el-button) {
  flex: 0 0 auto;
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

.secret-inline {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.credential-row span {
  color: #64748b;
}

.credential-row strong,
.credential-row code {
  color: #0f172a;
  word-break: break-all;
}

.secret-inline code {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.form-help {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
}

@media (max-width: 720px) {
  .page-toolbar {
    align-items: flex-start;
  }

  .actions {
    justify-content: flex-start;
  }

  .credential-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
