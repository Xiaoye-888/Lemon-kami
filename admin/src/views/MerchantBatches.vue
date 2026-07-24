<template>
  <div class="batch-page">
    <div class="page-toolbar">
      <h2>批次管理</h2>
      <el-button :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <section class="batch-grid">
      <el-card shadow="never" class="panel">
        <template #header>生成卡密</template>
        <el-form :model="form" label-width="92px">
          <el-form-item label="应用">
            <el-select v-model="form.app_id" placeholder="选择应用" style="width: 100%" @change="handleAppChange">
              <el-option v-for="app in apps" :key="app.app_id" :label="`${app.name} / ${app.is_owned ? '自建' : '授权'}`" :value="app.app_id" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="selectedApp && !selectedApp.is_owned" label="规格">
            <el-select v-model="form.spec_id" placeholder="选择授权规格" style="width: 100%">
              <el-option v-for="spec in specs" :key="spec.id" :label="spec.spec_name" :value="spec.id" />
            </el-select>
          </el-form-item>
          <template v-if="selectedApp?.is_owned">
            <el-form-item label="卡密类型">
              <el-select v-model="form.kami_type" style="width: 100%">
                <el-option label="积分卡" value="points" />
                <el-option label="次数卡" value="times" />
                <el-option label="月卡" value="month" />
                <el-option label="永久卡" value="lifetime" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="form.kami_type === 'points'" label="积分面额">
              <el-input-number v-model="form.points_amount" :min="1" :max="100000000" style="width: 100%" />
            </el-form-item>
            <el-form-item v-if="form.kami_type === 'times'" label="次数">
              <el-input-number v-model="form.times_total" :min="1" :max="100000000" style="width: 100%" />
            </el-form-item>
          </template>
          <el-form-item label="批次号">
            <el-input v-model="form.batch_no" placeholder="可留空自动生成" />
          </el-form-item>
          <el-form-item label="数量">
            <el-input-number v-model="form.count" :min="1" :max="1000" style="width: 100%" />
          </el-form-item>
          <el-form-item label="前缀">
            <el-input v-model="form.code_prefix" maxlength="32" />
          </el-form-item>
          <div v-if="issuePreview" class="issue-preview">
            <div>
              本次预计扣 {{ issuePreview.total_cost }} 发卡额度，当前余额 {{ issuePreview.balance_before }}，生成后余额 {{ issuePreview.balance_after }}
            </div>
            <el-tag :type="issuePreview.can_issue ? 'success' : 'danger'">
              {{ issuePreview.can_issue ? '额度充足' : '额度不足' }}
            </el-tag>
          </div>
          <div v-else-if="previewLoading" class="issue-preview muted">正在计算发卡额度...</div>
          <el-button type="primary" :loading="issuing" :disabled="!canIssue" @click="handleIssue">生成卡密</el-button>
        </el-form>
      </el-card>

      <el-card shadow="never" class="panel">
        <template #header>批次列表</template>
        <el-table :data="batches" v-loading="loading" border stripe>
          <el-table-column prop="batch_no" label="批次号" min-width="170" show-overflow-tooltip />
          <el-table-column prop="count" label="数量" width="80" />
          <el-table-column prop="kami_type" label="类型" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="170" />
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getMerchantAppSpecs, getMerchantApps, getMerchantBatches, issueMerchantKamis, previewMerchantKamis } from '../api/merchant'

const loading = ref(false)
const issuing = ref(false)
const previewLoading = ref(false)
const apps = ref([])
const specs = ref([])
const batches = ref([])
const issuePreview = ref(null)

const form = reactive({
  app_id: '',
  spec_id: null,
  kami_type: 'points',
  points_amount: 100,
  times_total: 10,
  batch_no: '',
  count: 10,
  code_prefix: '',
  code_length: 16,
  charset: 'upper_numeric'
})

const selectedApp = computed(() => apps.value.find((item) => item.app_id === form.app_id))
const canIssueInputs = computed(() => {
  if (!form.app_id || form.count <= 0) return false
  if (selectedApp.value && !selectedApp.value.is_owned) return Boolean(form.spec_id)
  return Boolean(form.kami_type)
})
const canIssue = computed(() => canIssueInputs.value && issuePreview.value?.can_issue !== false)

function buildIssuePayload() {
  return {
    spec_id: selectedApp.value?.is_owned ? null : form.spec_id,
    kami_type: selectedApp.value?.is_owned ? form.kami_type : null,
    points_amount: form.kami_type === 'points' ? form.points_amount : null,
    times_total: form.kami_type === 'times' ? form.times_total : null,
    count: form.count,
    batch_no: form.batch_no || null,
    code_prefix: form.code_prefix || null,
    code_length: form.code_length,
    charset: form.charset
  }
}

async function loadIssuePreview() {
  if (!canIssueInputs.value) {
    issuePreview.value = null
    return
  }
  previewLoading.value = true
  try {
    const res = await previewMerchantKamis(form.app_id, buildIssuePayload())
    issuePreview.value = res.data || null
  } catch (error) {
    issuePreview.value = null
  } finally {
    previewLoading.value = false
  }
}

async function loadApps() {
  const res = await getMerchantApps()
  apps.value = res.data || []
  if (!form.app_id && apps.value.length) form.app_id = apps.value[0].app_id
}

async function loadSpecs() {
  specs.value = []
  form.spec_id = null
  if (!form.app_id) return
  const res = await getMerchantAppSpecs(form.app_id)
  specs.value = res.data || []
  if (selectedApp.value && !selectedApp.value.is_owned && specs.value.length) {
    form.spec_id = specs.value[0].id
  }
}

async function loadBatches() {
  if (!form.app_id) {
    batches.value = []
    return
  }
  const res = await getMerchantBatches(form.app_id)
  batches.value = res.data || []
}

async function loadAll() {
  loading.value = true
  try {
    await loadApps()
    await loadSpecs()
    await loadBatches()
  } finally {
    loading.value = false
  }
}

async function handleAppChange() {
  await loadSpecs()
  await loadBatches()
  await loadIssuePreview()
}

async function handleIssue() {
  if (issuePreview.value?.can_issue === false) {
    ElMessage.error('发卡额度不足')
    return
  }
  issuing.value = true
  try {
    const res = await issueMerchantKamis(form.app_id, buildIssuePayload())
    ElMessage.success(`已生成 ${res.data.count} 个卡密`)
    form.batch_no = ''
    await loadBatches()
    await loadIssuePreview()
  } finally {
    issuing.value = false
  }
}

watch(
  () => [form.app_id, form.spec_id, form.kami_type, form.points_amount, form.times_total, form.count],
  loadIssuePreview
)

onMounted(loadAll)
</script>

<style scoped>
.batch-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}

.batch-grid {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
  gap: 16px;
}

.panel {
  border-radius: 8px;
}

.issue-preview {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #334155;
  font-size: 13px;
}

.issue-preview.muted {
  color: #64748b;
  justify-content: flex-start;
}

@media (max-width: 980px) {
  .batch-grid {
    grid-template-columns: 1fr;
  }
}
</style>
