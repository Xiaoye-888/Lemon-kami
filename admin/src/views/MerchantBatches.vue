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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getMerchantAppSpecs, getMerchantApps, getMerchantBatches, issueMerchantKamis } from '../api/merchant'

const loading = ref(false)
const issuing = ref(false)
const apps = ref([])
const specs = ref([])
const batches = ref([])

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
const canIssue = computed(() => {
  if (!form.app_id || form.count <= 0) return false
  if (selectedApp.value && !selectedApp.value.is_owned) return Boolean(form.spec_id)
  return Boolean(form.kami_type)
})

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
}

async function handleIssue() {
  issuing.value = true
  try {
    const payload = {
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
    const res = await issueMerchantKamis(form.app_id, payload)
    ElMessage.success(`已生成 ${res.data.count} 个卡密`)
    form.batch_no = ''
    await loadBatches()
  } finally {
    issuing.value = false
  }
}

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

@media (max-width: 980px) {
  .batch-grid {
    grid-template-columns: 1fr;
  }
}
</style>
