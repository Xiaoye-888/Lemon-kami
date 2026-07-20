<template>
  <div class="app-interfaces">
    <el-card shadow="never" class="page-card">
      <template #header>
        <div class="page-header">
          <div>
            <h2>应用接口列表</h2>
            <p>归属应用：{{ currentAppName || appId }}</p>
          </div>
          <div class="header-actions">
            <el-button @click="router.push('/apps/info')">返回应用</el-button>
            <el-button type="primary" :loading="loading" @click="loadAppInterfaces">刷新</el-button>
          </div>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索接口名称、说明、地址"
          class="search-input"
        />
        <el-segmented v-model="statusFilter" :options="statusOptions" />
      </div>

      <el-skeleton v-if="loading" :rows="8" animated />
      <el-empty v-else-if="filteredInterfaces.length === 0" description="暂无接口数据" />

      <el-table
        v-else
        :data="filteredInterfaces"
        :row-class-name="interfaceRowClass"
        border
        stripe
        class="app-interface-table"
      >
        <el-table-column label="接口ID" width="86">
          <template #default="{ row }">#{{ row.id || row.interface_id }}</template>
        </el-table-column>
        <el-table-column label="接口名称" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="name-cell">
              <strong>{{ row.name }}</strong>
              <el-tag size="small" effect="plain">{{ categoryText(row.category) }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="接口说明" min-width="280" show-overflow-tooltip />
        <el-table-column label="请求地址" min-width="300" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="methodType(row.method)">
              {{ row.method }}
            </el-tag>
            <span class="path-text">{{ resolvePath(row.path) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">
              {{ row.enabled ? '已开通' : '未开通' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="290" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button
                size="small"
                :type="row.enabled ? 'danger' : 'success'"
                :loading="savingKey === row.interface_id"
                @click="toggleInterface(row)"
              >
                {{ row.enabled ? '关闭接口' : '开通接口' }}
              </el-button>
              <el-button size="small" type="warning" @click="openConfig(row)">独立配置</el-button>
              <el-button size="small" type="primary" plain @click="openDocs(row)">开发文档</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="configDialogVisible" title="接口独立配置" width="720px">
      <template v-if="editingInterface">
        <el-descriptions :column="1" border class="config-summary">
          <el-descriptions-item label="接口名称">{{ editingInterface.name }}</el-descriptions-item>
          <el-descriptions-item label="接口地址">
            {{ editingInterface.method }} {{ resolvePath(editingInterface.path) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-form label-width="150px" class="config-form">
          <el-form-item label="开通状态">
            <el-switch v-model="configForm.enabled" />
          </el-form-item>
          <el-form-item label="配置备注">
            <el-input v-model="configForm.remark" maxlength="200" show-word-limit />
          </el-form-item>

          <template v-if="currentSchema.length">
            <el-form-item
              v-for="field in currentSchema"
              :key="field.key"
              :label="field.label"
            >
              <el-switch
                v-if="field.type === 'switch'"
                v-model="configForm.data[field.key]"
              />
              <el-input-number
                v-else-if="field.type === 'number'"
                v-model="configForm.data[field.key]"
                :min="field.min"
                :max="field.max"
                style="width: 100%"
              />
              <el-select
                v-else-if="field.type === 'select'"
                v-model="configForm.data[field.key]"
                style="width: 100%"
              >
                <el-option
                  v-for="option in field.options"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
              <el-input
                v-else-if="field.type === 'textarea'"
                v-model="configForm.data[field.key]"
                type="textarea"
                :rows="field.rows || 3"
              />
              <el-input v-else v-model="configForm.data[field.key]" />
              <div v-if="field.help" class="field-help">{{ field.help }}</div>
            </el-form-item>
          </template>

          <el-alert
            v-else
            title="此接口暂无内置配置项，可通过开通状态和备注控制业务接入说明。"
            type="info"
            :closable="false"
            show-icon
          />
        </el-form>

      </template>
      <template #footer>
        <el-button @click="configDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingConfig" @click="saveConfig">保存配置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getApps } from '../api/admin'
import { getAppInterfaces, updateAppInterface } from '../api/interfaces'
import { openInterfaceDoc } from '../utils/interfaceDocs'

const route = useRoute()
const router = useRouter()
const appId = computed(() => route.params.app_id)
const loading = ref(false)
const savingKey = ref('')
const savingConfig = ref(false)
const interfaces = ref([])
const apps = ref([])
const keyword = ref('')
const statusFilter = ref('all')
const configDialogVisible = ref(false)
const editingInterface = ref(null)

const statusOptions = [
  { label: '全部', value: 'all' },
  { label: '已开通', value: 'enabled' },
  { label: '未开通', value: 'disabled' }
]

const configForm = reactive({
  enabled: false,
  remark: '',
  data: {}
})

const configSchemas = {
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
  'sdk.report': [
    { key: 'allow_report', label: '允许事件上报', type: 'switch', default: true },
    { key: 'max_payload_kb', label: '最大载荷 KB', type: 'number', min: 1, max: 1024, default: 64 }
  ]
}

const currentAppName = computed(() => {
  const queryName = route.query.app_name
  const app = apps.value.find((item) => item.app_id === appId.value)
  return queryName || app?.name || ''
})

const currentSchema = computed(() => {
  if (!editingInterface.value) return []
  return configSchemas[editingInterface.value.interface_key] || []
})

const filteredInterfaces = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return interfaces.value.filter((item) => {
    if (statusFilter.value === 'enabled' && !item.enabled) return false
    if (statusFilter.value === 'disabled' && item.enabled) return false
    if (!text) return true
    return [item.name, item.description, item.path, item.interface_key]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(text))
  })
})

const normalizeInterface = (item) => ({
  ...item,
  enabled: Boolean(item.enabled),
  remark: item.remark || '',
  config: item.config || {}
})

const resolvePath = (path) => String(path || '').replace('{app_id}', appId.value)

const methodType = (method) => {
  const map = { GET: 'success', POST: 'warning', PUT: 'primary', DELETE: 'danger' }
  return map[String(method || '').toUpperCase()] || 'info'
}

const categoryText = (category) => {
  const map = { user: '用户接口', points: '积分接口', sdk: 'SDK 接口', core: '核心接口' }
  return map[category] || category || '未分类'
}

const interfaceRowClass = ({ row }) => (row.enabled ? 'enabled-row' : '')

const schemaDefaults = (schema) => {
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

const loadApps = async () => {
  try {
    const res = await getApps()
    apps.value = res.data || []
  } catch (error) {
    console.error('加载应用失败:', error)
  }
}

const loadAppInterfaces = async () => {
  loading.value = true
  try {
    const res = await getAppInterfaces(appId.value)
    interfaces.value = (res.data || []).map(normalizeInterface)
  } catch (error) {
    console.error('加载应用接口失败:', error)
    ElMessage.error('加载应用接口失败')
  } finally {
    loading.value = false
  }
}

const saveInterface = async (row, patch = {}) => {
  savingKey.value = row.interface_id
  try {
    const res = await updateAppInterface(appId.value, row.interface_id, {
      enabled: patch.enabled ?? row.enabled,
      config: patch.config ?? row.config ?? {},
      remark: patch.remark ?? row.remark ?? null
    })
    Object.assign(row, normalizeInterface(res.data))
    ElMessage.success('接口配置已更新')
  } catch (error) {
    console.error('保存应用接口失败:', error)
    ElMessage.error('保存应用接口失败')
  } finally {
    savingKey.value = ''
  }
}

const toggleInterface = async (row) => {
  await saveInterface(row, { enabled: !row.enabled })
}

const openConfig = (row) => {
  editingInterface.value = row
  configForm.enabled = row.enabled
  configForm.remark = row.remark || ''
  configForm.data = {
    ...schemaDefaults(configSchemas[row.interface_key] || []),
    ...(row.config || {})
  }
  configDialogVisible.value = true
}

const saveConfig = async () => {
  if (!editingInterface.value) return
  savingConfig.value = true
  try {
    await saveInterface(editingInterface.value, {
      enabled: configForm.enabled,
      config: { ...configForm.data },
      remark: configForm.remark || null
    })
    configDialogVisible.value = false
  } finally {
    savingConfig.value = false
  }
}

const openDocs = (row) => {
  openInterfaceDoc(row.interface_key)
}

onMounted(async () => {
  await Promise.all([loadApps(), loadAppInterfaces()])
})
</script>

<style scoped>
.app-interfaces {
  height: 100%;
}

.page-card {
  border-radius: 8px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  line-height: 1.3;
}

.page-header p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.header-actions,
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar {
  margin-bottom: 16px;
  justify-content: space-between;
}

.search-input {
  width: min(420px, 100%);
}

.name-cell,
.table-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.path-text {
  margin-left: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: #334155;
}

.app-interface-table {
  font-size: 12px;
}

.table-actions {
  justify-content: flex-end;
}

.app-interface-table :deep(.enabled-row) td {
  background-color: #f8fff9;
}

.config-summary {
  margin-bottom: 16px;
}

.field-help {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
}

@media (max-width: 1180px) {
  .table-actions {
    justify-content: flex-start;
  }
}
</style>
