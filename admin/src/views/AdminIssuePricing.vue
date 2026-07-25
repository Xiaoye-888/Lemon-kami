<template>
  <div class="pricing-page">
    <div class="page-toolbar">
      <h2>发卡额度配置</h2>
      <el-button type="primary" :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <section class="pricing-grid">
      <el-card shadow="never" class="panel">
        <template #header>规则配置</template>
        <el-form :model="pricingForm" label-width="120px">
          <el-form-item label="发卡场景">
            <el-radio-group v-model="pricingScenario" class="pricing-radio-group" @change="handleScenarioChange">
              <el-radio-button
                v-for="option in scenarioOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="扣费范围">
            <el-radio-group v-model="pricingScope" class="pricing-radio-group" @change="handleScopeChange">
              <el-radio-button
                v-for="option in scopeOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item v-if="needsUser" label="发卡用户">
            <el-select
              v-model="pricingForm.user_id"
              filterable
              remote
              reserve-keyword
              clearable
              placeholder="搜索发卡用户"
              :remote-method="searchMerchants"
              :loading="merchantLoading"
              style="width: 100%"
            >
              <el-option
                v-for="merchant in merchants"
                :key="merchant.id"
                :label="merchant.username"
                :value="merchant.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item v-if="needsSpec" label="应用">
            <el-select v-model="pricingForm.app_id" filterable style="width: 100%">
              <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
            </el-select>
          </el-form-item>

          <el-form-item v-if="needsSpec" label="卡密规格">
            <el-select
              v-model="pricingForm.spec_id"
              filterable
              remote
              reserve-keyword
              placeholder="搜索卡密规格"
              :remote-method="searchSpecs"
              :loading="specLoading"
              style="width: 100%"
            >
              <el-option
                v-for="spec in specs"
                :key="spec.id"
                :label="specLabel(spec)"
                :value="spec.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="单张消耗额度">
            <el-input-number v-model="pricingForm.unit_cost" :min="1" :max="100000000" style="width: 100%" />
          </el-form-item>

          <el-form-item label="状态">
            <el-switch v-model="pricingForm.enabled" active-text="启用" inactive-text="停用" />
          </el-form-item>

          <el-form-item label="备注">
            <el-input v-model="pricingForm.remark" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>

        <el-alert class="preview-alert" type="info" :closable="false" show-icon>
          <template #title>生效预览</template>
          <div>{{ effectivePreview }}</div>
          <div class="priority-line">命中顺序：{{ priorityPreview }}</div>
        </el-alert>

        <div class="form-actions">
          <el-button @click="resetForm">重置</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">保存规则</el-button>
        </div>
      </el-card>

      <el-card shadow="never" class="panel panel--wide">
        <template #header>当前规则</template>
        <el-table :data="rules" v-loading="loading" border stripe>
          <el-table-column prop="target_type" label="发卡场景" min-width="150">
            <template #default="{ row }">{{ targetSceneLabel(row.target_type) }}</template>
          </el-table-column>
          <el-table-column prop="target_type" label="扣费范围" min-width="170">
            <template #default="{ row }">{{ targetScopeLabel(row.target_type) }}</template>
          </el-table-column>
          <el-table-column prop="username" label="发卡用户" min-width="120">
            <template #default="{ row }">{{ row.username || '-' }}</template>
          </el-table-column>
          <el-table-column prop="app_id" label="应用" min-width="150">
            <template #default="{ row }">{{ appName(row.app_id) }}</template>
          </el-table-column>
          <el-table-column prop="spec_id" label="规格" min-width="170">
            <template #default="{ row }">{{ ruleSpecLabel(row) }}</template>
          </el-table-column>
          <el-table-column prop="unit_cost" label="单张消耗" width="110" />
          <el-table-column prop="target_type" label="命中顺序" min-width="130">
            <template #default="{ row }">{{ targetPriorityLabel(row.target_type) }}</template>
          </el-table-column>
          <el-table-column prop="enabled" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="editRule(row)">编辑</el-button>
              <el-button
                link
                type="danger"
                :loading="rowAction === `delete:${row.id}`"
                @click="handleDelete(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteIssuePricingRule,
  getCommercialMerchants,
  getIssuePricingRules,
  saveIssuePricingRule
} from '../api/commercial'
import { getApps } from '../api/admin'
import { getKamiSpecs } from '../api/kami'

const CONFIRM_CHANGE_ISSUE_PRICING = '确认修改发卡额度'

const loading = ref(false)
const saving = ref(false)
const rowAction = ref('')
const merchantLoading = ref(false)
const specLoading = ref(false)
const rules = ref([])
const apps = ref([])
const merchants = ref([])
const specs = ref([])
const specCache = ref({})
const pricingScenario = ref('self')
const pricingScope = ref('global')

const scenarioOptions = [
  { value: 'self', label: '用户自建应用发卡' },
  { value: 'authorized', label: '管理员授权应用发卡' }
]

const scopeOptionsByScenario = {
  self: [
    { value: 'global', label: '全局默认扣费', targetType: 'global_self_app' },
    { value: 'user', label: '指定用户扣费', targetType: 'user_self_app' }
  ],
  authorized: [
    { value: 'global', label: '全局默认扣费', targetType: 'global_authorized_app' },
    { value: 'spec', label: '指定规格扣费', targetType: 'authorized_spec' },
    { value: 'user_spec', label: '指定用户 + 指定规格扣费', targetType: 'user_authorized_spec' }
  ]
}

const targetTypeMeta = {
  global_self_app: {
    scenario: 'self',
    scope: 'global',
    sceneLabel: '用户自建应用发卡',
    scopeLabel: '全局默认扣费',
    priorityLabel: '自建第2优先级'
  },
  user_self_app: {
    scenario: 'self',
    scope: 'user',
    sceneLabel: '用户自建应用发卡',
    scopeLabel: '指定用户扣费',
    priorityLabel: '自建第1优先级'
  },
  global_authorized_app: {
    scenario: 'authorized',
    scope: 'global',
    sceneLabel: '管理员授权应用发卡',
    scopeLabel: '全局默认扣费',
    priorityLabel: '授权第3优先级'
  },
  authorized_spec: {
    scenario: 'authorized',
    scope: 'spec',
    sceneLabel: '管理员授权应用发卡',
    scopeLabel: '指定规格扣费',
    priorityLabel: '授权第2优先级'
  },
  user_authorized_spec: {
    scenario: 'authorized',
    scope: 'user_spec',
    sceneLabel: '管理员授权应用发卡',
    scopeLabel: '指定用户 + 指定规格扣费',
    priorityLabel: '授权第1优先级'
  }
}

const pricingForm = reactive({
  target_type: 'global_self_app',
  user_id: null,
  app_id: '',
  spec_id: null,
  unit_cost: 1,
  enabled: true,
  remark: ''
})

const needsUser = computed(() => ['user_self_app', 'user_authorized_spec'].includes(pricingForm.target_type))
const needsSpec = computed(() => ['authorized_spec', 'user_authorized_spec'].includes(pricingForm.target_type))
const scopeOptions = computed(() => scopeOptionsByScenario[pricingScenario.value] || [])

const effectivePreview = computed(() => {
  const unitCost = pricingForm.unit_cost || 0
  if (pricingForm.target_type === 'global_self_app') {
    return `所有发卡用户在自建应用生成卡密时，每张扣 ${unitCost} 发卡额度。`
  }
  if (pricingForm.target_type === 'user_self_app') {
    return `发卡用户【${selectedMerchantLabel()}】在自建应用生成卡密时，每张扣 ${unitCost} 发卡额度。`
  }
  if (pricingForm.target_type === 'global_authorized_app') {
    return `所有发卡用户使用管理员授权应用生成卡密时，每张扣 ${unitCost} 发卡额度。`
  }
  if (pricingForm.target_type === 'authorized_spec') {
    return `所有发卡用户在授权应用【${selectedAppLabel()}】生成规格【${selectedSpecLabel()}】时，每张扣 ${unitCost} 发卡额度。`
  }
  if (pricingForm.target_type === 'user_authorized_spec') {
    return `发卡用户【${selectedMerchantLabel()}】在授权应用【${selectedAppLabel()}】生成规格【${selectedSpecLabel()}】时，每张扣 ${unitCost} 发卡额度。`
  }
  return `每张扣 ${unitCost} 发卡额度。`
})

const priorityPreview = computed(() => {
  if (pricingScenario.value === 'self') {
    return '指定用户扣费 > 全局默认扣费 > 系统默认 1'
  }
  return '指定用户 + 指定规格扣费 > 指定规格扣费 > 全局默认扣费 > 系统默认 1'
})

function targetLabel(value) {
  return {
    global_self_app: '用户自建应用：全局默认扣费',
    global_authorized_app: '管理员授权应用：全局默认扣费',
    authorized_spec: '管理员授权应用：指定规格扣费',
    user_self_app: '用户自建应用：指定用户扣费',
    user_authorized_spec: '管理员授权应用：指定用户 + 指定规格扣费'
  }[value] || value
}

function targetSceneLabel(value) {
  return targetTypeMeta[value]?.sceneLabel || targetLabel(value)
}

function targetScopeLabel(value) {
  return targetTypeMeta[value]?.scopeLabel || '-'
}

function targetPriorityLabel(value) {
  return targetTypeMeta[value]?.priorityLabel || '-'
}

function specLabel(spec) {
  return `${spec.spec_name || spec.spec_key} / ${spec.kami_type}`
}

function appName(appId) {
  if (!appId) return '-'
  const app = apps.value.find((item) => item.app_id === appId)
  return app ? `${app.name} (${app.app_id})` : appId
}

function ruleSpecLabel(row) {
  if (!row.spec_id) return '-'
  const cached = specCache.value[row.spec_id]
  return cached ? specLabel(cached) : `#${row.spec_id}`
}

function selectedMerchantLabel() {
  const merchant = merchants.value.find((item) => item.id === pricingForm.user_id)
  if (merchant) return merchant.username
  return pricingForm.user_id ? `#${pricingForm.user_id}` : '未选择用户'
}

function selectedAppLabel() {
  return pricingForm.app_id ? appName(pricingForm.app_id) : '未选择应用'
}

function selectedSpecLabel() {
  if (!pricingForm.spec_id) return '未选择规格'
  const spec = specs.value.find((item) => item.id === pricingForm.spec_id) || specCache.value[pricingForm.spec_id]
  return spec ? specLabel(spec) : `#${pricingForm.spec_id}`
}

function syncSelectorFromTargetType(targetType) {
  const meta = targetTypeMeta[targetType] || targetTypeMeta.global_self_app
  pricingScenario.value = meta.scenario
  pricingScope.value = meta.scope
}

function applySelectorToTargetType() {
  const option = scopeOptions.value.find((item) => item.value === pricingScope.value) || scopeOptions.value[0]
  if (!option) return
  pricingForm.target_type = option.targetType
  if (!needsUser.value) pricingForm.user_id = null
  if (!needsSpec.value) pricingForm.spec_id = null
}

function handleScenarioChange() {
  pricingScope.value = scopeOptions.value[0]?.value || 'global'
  applySelectorToTargetType()
}

function handleScopeChange() {
  applySelectorToTargetType()
}

function mergeMerchantOptions(items) {
  const merged = new Map()
  for (const merchant of merchants.value) {
    if (merchant.id) merged.set(merchant.id, merchant)
  }
  for (const merchant of items || []) {
    if (merchant.id) merged.set(merchant.id, merchant)
  }
  for (const rule of rules.value) {
    if (rule.user_id) {
      merged.set(rule.user_id, {
        id: rule.user_id,
        username: rule.username || `#${rule.user_id}`
      })
    }
  }
  merchants.value = Array.from(merged.values())
}

function resetForm() {
  pricingForm.target_type = 'global_self_app'
  syncSelectorFromTargetType(pricingForm.target_type)
  pricingForm.user_id = null
  pricingForm.app_id = apps.value[0]?.app_id || ''
  pricingForm.spec_id = null
  pricingForm.unit_cost = 1
  pricingForm.enabled = true
  pricingForm.remark = ''
}

function payloadFromForm() {
  return {
    target_type: pricingForm.target_type,
    user_id: needsUser.value ? pricingForm.user_id : null,
    spec_id: needsSpec.value ? pricingForm.spec_id : null,
    unit_cost: pricingForm.unit_cost,
    enabled: pricingForm.enabled,
    remark: pricingForm.remark || null
  }
}

async function promptSensitiveConfirm(expected, title) {
  const { value } = await ElMessageBox.prompt(`请输入「${expected}」以确认`, title, {
    inputValue: '',
    inputValidator: (value) => value === expected || `请输入 ${expected}`,
    type: 'warning'
  })
  return value
}

async function loadMerchants(keyword = '') {
  merchantLoading.value = true
  try {
    const params = { page: 1, page_size: 100 }
    const normalizedKeyword = keyword.trim()
    if (normalizedKeyword) params.keyword = normalizedKeyword
    const res = await getCommercialMerchants(params)
    mergeMerchantOptions(res.data?.items || [])
  } finally {
    merchantLoading.value = false
  }
}

async function searchMerchants(keyword) {
  await loadMerchants(keyword || '')
}

async function loadSpecs(appId, keyword = '') {
  if (!appId) {
    specs.value = []
    return
  }
  specLoading.value = true
  try {
    const normalizedKeyword = keyword.trim()
    const res = await getKamiSpecs({ app_id: appId, ...(normalizedKeyword ? { keyword: normalizedKeyword } : {}) })
    specs.value = res.data?.items || res.data || []
    specCache.value = {
      ...specCache.value,
      ...Object.fromEntries(specs.value.map((spec) => [spec.id, spec]))
    }
  } finally {
    specLoading.value = false
  }
}

async function searchSpecs(keyword) {
  await loadSpecs(pricingForm.app_id, keyword || '')
}

async function loadAll() {
  loading.value = true
  try {
    const [ruleRes, appRes] = await Promise.all([
      getIssuePricingRules(),
      getApps()
    ])
    rules.value = ruleRes.data?.items || []
    apps.value = appRes.data || []
    if (!pricingForm.app_id) {
      pricingForm.app_id = apps.value[0]?.app_id || ''
    }
    await Promise.all([
      loadMerchants(),
      pricingForm.app_id ? loadSpecs(pricingForm.app_id) : Promise.resolve()
    ])
  } finally {
    loading.value = false
  }
}

function validateForm() {
  if (needsUser.value && !pricingForm.user_id) {
    ElMessage.error('请选择发卡用户')
    return false
  }
  if (needsSpec.value && !pricingForm.app_id) {
    ElMessage.error('请选择应用')
    return false
  }
  if (needsSpec.value && !pricingForm.spec_id) {
    ElMessage.error('请选择卡密规格')
    return false
  }
  if (!pricingForm.unit_cost || pricingForm.unit_cost <= 0) {
    ElMessage.error('单张消耗额度必须大于 0')
    return false
  }
  return true
}

async function handleSave() {
  if (!validateForm()) return
  saving.value = true
  try {
    const confirmText = await promptSensitiveConfirm(CONFIRM_CHANGE_ISSUE_PRICING, '保存发卡额度规则')
    await saveIssuePricingRule({ ...payloadFromForm(), confirm_text: confirmText })
    ElMessage.success('发卡额度规则已保存')
    await loadAll()
  } finally {
    saving.value = false
  }
}

async function editRule(row) {
  pricingForm.target_type = row.target_type
  syncSelectorFromTargetType(row.target_type)
  pricingForm.user_id = row.user_id || null
  pricingForm.app_id = row.app_id || pricingForm.app_id || apps.value[0]?.app_id || ''
  pricingForm.unit_cost = row.unit_cost || 1
  pricingForm.enabled = Boolean(row.enabled)
  pricingForm.remark = row.remark || ''
  mergeMerchantOptions(row.user_id ? [{ id: row.user_id, username: row.username || `#${row.user_id}` }] : [])
  if (needsSpec.value && pricingForm.app_id) {
    await loadSpecs(pricingForm.app_id)
  }
  pricingForm.spec_id = row.spec_id || null
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该发卡额度规则吗？', '删除规则', { type: 'warning' })
  } catch {
    return
  }
  rowAction.value = `delete:${row.id}`
  try {
    const confirmText = await promptSensitiveConfirm(CONFIRM_CHANGE_ISSUE_PRICING, '删除发卡额度规则')
    await deleteIssuePricingRule(row.id, { confirm_text: confirmText })
    ElMessage.success('发卡额度规则已删除')
    await loadAll()
  } finally {
    rowAction.value = ''
  }
}

watch(
  () => pricingForm.app_id,
  async (appId) => {
    await loadSpecs(appId)
    if (pricingForm.spec_id && !specs.value.some((spec) => spec.id === pricingForm.spec_id)) {
      pricingForm.spec_id = null
    }
  }
)

watch(
  () => pricingForm.target_type,
  (targetType) => {
    const meta = targetTypeMeta[targetType]
    if (meta && (pricingScenario.value !== meta.scenario || pricingScope.value !== meta.scope)) {
      syncSelectorFromTargetType(targetType)
    }
    if (!needsUser.value) pricingForm.user_id = null
    if (!needsSpec.value) pricingForm.spec_id = null
  }
)

onMounted(loadAll)
</script>

<style scoped>
.pricing-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}

.pricing-grid {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
  gap: 14px;
}

.panel {
  border-radius: 8px;
}

.panel--wide {
  min-width: 0;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.pricing-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pricing-radio-group :deep(.el-radio-button__inner) {
  border-left: var(--el-border);
  border-radius: 6px;
  line-height: 1.2;
  white-space: normal;
}

.preview-alert {
  margin-bottom: 14px;
}

.priority-line {
  margin-top: 6px;
  color: #52627a;
}

@media (max-width: 980px) {
  .pricing-grid {
    grid-template-columns: 1fr;
  }
}
</style>
