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
          <el-form-item label="规则类型">
            <el-select v-model="pricingForm.target_type" style="width: 100%">
              <el-option label="自建应用默认" value="global_self_app" />
              <el-option label="授权应用默认" value="global_authorized_app" />
              <el-option label="授权规格默认" value="authorized_spec" />
              <el-option label="用户自建专属" value="user_self_app" />
              <el-option label="用户授权规格专属" value="user_authorized_spec" />
            </el-select>
          </el-form-item>

          <el-form-item v-if="needsUser" label="发卡用户">
            <el-select v-model="pricingForm.user_id" filterable style="width: 100%">
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
            <el-select v-model="pricingForm.spec_id" filterable style="width: 100%">
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
        <div class="form-actions">
          <el-button @click="resetForm">重置</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">保存规则</el-button>
        </div>
      </el-card>

      <el-card shadow="never" class="panel panel--wide">
        <template #header>当前规则</template>
        <el-table :data="rules" v-loading="loading" border stripe>
          <el-table-column prop="target_type" label="规则类型" min-width="150">
            <template #default="{ row }">{{ targetLabel(row.target_type) }}</template>
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
const rules = ref([])
const apps = ref([])
const merchants = ref([])
const specs = ref([])
const specCache = ref({})

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

function targetLabel(value) {
  return {
    global_self_app: '自建应用默认',
    global_authorized_app: '授权应用默认',
    authorized_spec: '授权规格默认',
    user_self_app: '用户自建专属',
    user_authorized_spec: '用户授权规格专属'
  }[value] || value
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

function resetForm() {
  pricingForm.target_type = 'global_self_app'
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

async function loadSpecs(appId) {
  if (!appId) {
    specs.value = []
    return
  }
  const res = await getKamiSpecs({ app_id: appId, page: 1, page_size: 100 })
  specs.value = res.data?.items || res.data || []
  specCache.value = {
    ...specCache.value,
    ...Object.fromEntries(specs.value.map((spec) => [spec.id, spec]))
  }
}

async function loadAll() {
  loading.value = true
  try {
    const [ruleRes, appRes, merchantRes] = await Promise.all([
      getIssuePricingRules(),
      getApps(),
      getCommercialMerchants({ page: 1, page_size: 100 })
    ])
    rules.value = ruleRes.data?.items || []
    apps.value = appRes.data || []
    merchants.value = merchantRes.data?.items || []
    if (!pricingForm.app_id) {
      pricingForm.app_id = apps.value[0]?.app_id || ''
    }
    if (pricingForm.app_id) {
      await loadSpecs(pricingForm.app_id)
    }
  } finally {
    loading.value = false
  }
}

function validateForm() {
  if (needsUser.value && !pricingForm.user_id) {
    ElMessage.error('请选择发卡用户')
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

function editRule(row) {
  pricingForm.target_type = row.target_type
  pricingForm.user_id = row.user_id || null
  pricingForm.app_id = row.app_id || pricingForm.app_id || apps.value[0]?.app_id || ''
  pricingForm.spec_id = row.spec_id || null
  pricingForm.unit_cost = row.unit_cost || 1
  pricingForm.enabled = Boolean(row.enabled)
  pricingForm.remark = row.remark || ''
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
    pricingForm.spec_id = null
    await loadSpecs(appId)
  }
)

watch(
  () => pricingForm.target_type,
  () => {
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

@media (max-width: 980px) {
  .pricing-grid {
    grid-template-columns: 1fr;
  }
}
</style>
