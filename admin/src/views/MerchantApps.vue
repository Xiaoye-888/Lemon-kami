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
        <el-table-column prop="name" label="应用名称" min-width="160" />
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
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goBatches(row)">规格批次</el-button>
            <el-button v-if="row.is_owned" link type="primary" @click="showCredential(row)">凭证</el-button>
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

    <el-dialog v-model="createResultVisible" title="应用凭证" width="560px">
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
          <span>应用来源</span>
          <strong>{{ createdApp.is_owned ? '自建应用' : '授权应用' }}</strong>
        </div>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="请在需要接入时按接口文档配置客户端，不在列表页公开展示敏感凭证。"
        />
      </div>
      <template #footer>
        <el-button @click="createResultVisible = false">关闭</el-button>
        <el-button type="primary" @click="goBatches(createdApp)">配置规格</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="credentialVisible" title="应用凭证" width="560px">
      <div v-if="currentApp" class="credential-panel">
        <div class="credential-row">
          <span>应用名称</span>
          <strong>{{ currentApp.name }}</strong>
        </div>
        <div class="credential-row">
          <span>App ID</span>
          <strong>{{ currentApp.app_id }}</strong>
        </div>
        <div class="credential-row credential-row--public">
          <span>RSA 公钥</span>
          <code>{{ currentApp.rsa_public_key || '-' }}</code>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createMerchantApp, getMerchantApps } from '../api/merchant'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const apps = ref([])
const createDialogVisible = ref(false)
const createResultVisible = ref(false)
const credentialVisible = ref(false)
const createdApp = ref(null)
const currentApp = ref(null)
const createForm = reactive({ name: '' })

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

function showCredential(row) {
  currentApp.value = row
  credentialVisible.value = true
}

function goBatches(row) {
  if (!row?.app_id) return
  createResultVisible.value = false
  router.push({ path: '/merchant/batches', query: { app_id: row.app_id } })
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
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
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

.credential-panel {
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
  max-height: 160px;
  overflow: auto;
  padding: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
}
</style>
