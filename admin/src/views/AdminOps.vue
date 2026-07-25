<template>
  <div class="ops-page">
    <div class="page-toolbar">
      <div>
        <h2>运维中心</h2>
        <p>备份、凭证生命周期、近期错误</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <section class="health-grid">
      <el-card v-for="item in healthCards" :key="item.label" shadow="never" class="health-card">
        <span>{{ item.label }}</span>
        <strong :class="{ danger: !item.ok }">{{ item.ok ? '正常' : '异常' }}</strong>
        <small>{{ item.path || item.message }}</small>
      </el-card>
    </section>

    <section class="ops-grid">
      <el-card shadow="never">
        <template #header>备份管理</template>
        <div class="backup-actions">
          <el-select v-model="backupType" class="backup-type">
            <el-option label="数据库备份" value="database" />
            <el-option label="上传文件备份" value="uploads" />
          </el-select>
          <el-button type="primary" :loading="creatingBackup" @click="handleCreateBackup">
            创建备份
          </el-button>
        </div>
        <el-table :data="backups" v-loading="loading" border stripe>
          <el-table-column prop="backup_no" label="备份号" min-width="180" show-overflow-tooltip />
          <el-table-column prop="backup_type" label="类型" width="100" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="file_size" label="大小" width="110" />
          <el-table-column prop="created_at" label="创建时间" width="180" />
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :loading="downloading === row.backup_no" @click="handleDownload(row)">
                下载
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>凭证清理</template>
        <el-form :model="cleanupForm" label-width="110px">
          <el-form-item label="保留天数">
            <el-input-number v-model="cleanupForm.older_than_days" :min="1" :max="3650" />
          </el-form-item>
          <el-form-item>
            <el-button :loading="previewingCleanup" @click="handlePreviewCleanup">预览</el-button>
            <el-button type="warning" :loading="cleaningProofs" @click="handleCleanupProofs">执行清理</el-button>
          </el-form-item>
        </el-form>
        <el-descriptions v-if="cleanupResult" :column="1" border>
          <el-descriptions-item label="匹配订单">{{ cleanupResult.matched_count }}</el-descriptions-item>
          <el-descriptions-item label="删除文件">{{ cleanupResult.deleted_count }}</el-descriptions-item>
          <el-descriptions-item label="模式">{{ cleanupResult.dry_run ? '预览' : '执行' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </section>

    <el-card shadow="never">
      <template #header>近期错误</template>
      <el-table :data="recentErrors" border stripe>
        <el-table-column prop="line" label="日志内容" min-width="240" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  cleanupProofUploads,
  createOpsBackup,
  downloadOpsBackup,
  getOpsBackups,
  getOpsHealth,
  getRecentErrorLogs
} from '../api/ops'

const CONFIRM_CREATE_BACKUP = '确认创建备份'
const CONFIRM_DOWNLOAD_BACKUP = '确认下载备份'
const CONFIRM_CLEANUP_PROOFS = '确认清理凭证'

const loading = ref(false)
const creatingBackup = ref(false)
const previewingCleanup = ref(false)
const cleaningProofs = ref(false)
const downloading = ref('')
const health = ref({})
const backups = ref([])
const recentErrors = ref([])
const cleanupResult = ref(null)
const backupType = ref('database')
const cleanupForm = reactive({
  older_than_days: 30
})

const healthCards = computed(() => [
  { label: '数据库', ...(health.value.database || {}) },
  { label: '上传目录', ...(health.value.uploads || {}) },
  { label: '备份目录', ...(health.value.backups || {}) },
  { label: '日志目录', ...(health.value.logs || {}) }
])

async function loadAll() {
  loading.value = true
  try {
    const [healthRes, backupsRes, errorsRes] = await Promise.all([
      getOpsHealth(),
      getOpsBackups({ page: 1, page_size: 20 }),
      getRecentErrorLogs({ max_lines: 100 })
    ])
    health.value = healthRes.data || {}
    backups.value = backupsRes.data?.items || []
    recentErrors.value = (errorsRes.data?.items || []).map((line) => ({ line }))
  } finally {
    loading.value = false
  }
}

async function readConfirmation(message, expected) {
  const { value } = await ElMessageBox.prompt(message, '敏感操作确认', {
    confirmButtonText: '确认',
    cancelButtonText: '取消',
    inputPlaceholder: expected,
    inputValidator: (value) => value === expected || `请输入：${expected}`
  })
  return value
}

async function handleCreateBackup() {
  const confirmText = await readConfirmation('创建备份', CONFIRM_CREATE_BACKUP)
  creatingBackup.value = true
  try {
    await createOpsBackup({ backup_type: backupType.value, confirm_text: confirmText })
    ElMessage.success('备份已创建')
    await loadAll()
  } finally {
    creatingBackup.value = false
  }
}

async function handleDownload(row) {
  const confirmText = await readConfirmation(`下载备份 ${row.backup_no}`, CONFIRM_DOWNLOAD_BACKUP)
  downloading.value = row.backup_no
  try {
    const response = await downloadOpsBackup(row.backup_no, { confirm_text: confirmText })
    saveBlob(response.data, row.file_name || `${row.backup_no}.gz`)
  } finally {
    downloading.value = ''
  }
}

async function handlePreviewCleanup() {
  previewingCleanup.value = true
  try {
    const res = await cleanupProofUploads({
      older_than_days: cleanupForm.older_than_days,
      dry_run: true
    })
    cleanupResult.value = res.data
  } finally {
    previewingCleanup.value = false
  }
}

async function handleCleanupProofs() {
  const confirmText = await readConfirmation('执行凭证清理', CONFIRM_CLEANUP_PROOFS)
  cleaningProofs.value = true
  try {
    const res = await cleanupProofUploads({
      older_than_days: cleanupForm.older_than_days,
      dry_run: false,
      confirm_text: confirmText
    })
    cleanupResult.value = res.data
    ElMessage.success('凭证清理已完成')
  } finally {
    cleaningProofs.value = false
  }
}

function saveBlob(data, filename) {
  const blob = new Blob([data], { type: 'application/octet-stream' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

onMounted(loadAll)
</script>

<style scoped>
.ops-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar,
.backup-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
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

.health-grid,
.ops-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.ops-grid {
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.6fr);
}

.health-card {
  border-radius: 8px;
}

.health-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.health-card span,
.health-card small {
  color: #64748b;
}

.health-card strong {
  color: #16a34a;
  font-size: 22px;
}

.health-card strong.danger {
  color: #dc2626;
}

.backup-type {
  width: 160px;
}

@media (max-width: 1100px) {
  .health-grid,
  .ops-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 720px) {
  .health-grid,
  .ops-grid {
    grid-template-columns: 1fr;
  }
}
</style>
