<template>
  <div class="app-versions">
    <el-card shadow="never" class="page-card">
      <template #header>
        <div class="card-header">
          <div class="filters">
            <el-select v-model="selectedAppId" placeholder="选择应用" filterable style="width: 260px" @change="loadVersions">
              <el-option
                v-for="app in apps"
                :key="app.app_id"
                :label="app.name"
                :value="app.app_id"
              />
            </el-select>
            <div class="control locked">Windows</div>
          </div>
          <div class="header-actions">
            <el-button :disabled="!selectedAppId" @click="copyUpdateCheckUrl">
              复制检查接口
            </el-button>
            <el-button type="primary" :disabled="!selectedAppId" @click="openCreate">
              <el-icon><Plus /></el-icon>
              新增版本
            </el-button>
          </div>
        </div>
      </template>

      <div class="current-release">
        <span>当前生效：{{ currentVersion ? `${currentVersion.version}（${currentVersion.version_code}）` : '暂无发布版本' }}</span>
        <span>客户端判断：current_version_code &lt; latest_version_code</span>
        <span>建议版本编码：{{ nextVersionCode }}</span>
        <span>默认标题：{{ defaultUpdateTitle() }}</span>
      </div>

      <el-table :data="sortedVersions" v-loading="loading" border stripe @row-click="selectVersion">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="version" label="版本号" width="130" />
        <el-table-column prop="version_code" label="版本编码" width="110" />
        <el-table-column label="平台" width="110">
          <template #default>Windows</template>
        </el-table-column>
        <el-table-column label="生效状态" width="120">
          <template #default="{ row }">
            <el-tag :type="effectiveTag(row)">{{ effectiveStateText(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="更新标题" min-width="160" show-overflow-tooltip />
        <el-table-column prop="notes" label="更新说明" min-width="220" show-overflow-tooltip />
        <el-table-column prop="force_update" label="强制更新" width="110">
          <template #default="{ row }">
            <el-tag :type="row.force_update ? 'danger' : 'info'">{{ row.force_update ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="download_url" label="下载地址" min-width="220" show-overflow-tooltip />
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click.stop="openEdit(row)">编辑</el-button>
            <el-button size="small" plain @click.stop="copyAsNewVersion(row, row.status === 'archived')">
              {{ row.status === 'archived' ? '复制为回退包' : '复制新版本' }}
            </el-button>
            <el-button v-if="row.status === 'draft'" size="small" type="success" plain @click.stop="publishDraft(row)">
              编辑发布
            </el-button>
            <el-button v-if="row.status !== 'archived'" size="small" type="warning" plain @click.stop="archiveVersion(row)">
              编辑下架
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingVersion ? '编辑版本' : '新增版本'" width="760px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="平台">
          <div class="control locked">Windows</div>
        </el-form-item>
        <el-form-item label="版本号" required>
          <el-input v-model="form.version" placeholder="例如 1.1.0" />
        </el-form-item>
        <el-form-item label="版本编码" required>
          <el-input-number v-model="form.version_code" :min="1" :max="999999999" />
        </el-form-item>
        <el-form-item label="更新标题" required>
          <el-input v-model="form.title" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="更新说明">
          <el-input v-model="form.notes" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="强制更新">
          <el-switch v-model="form.force_update" />
        </el-form-item>
        <el-form-item label="下载地址">
          <el-input v-model="form.download_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="地址类型">
          <el-select v-model="form.url_type" style="width: 180px">
            <el-option label="直链" value="direct" />
            <el-option label="网盘/外链" value="external" />
          </el-select>
        </el-form-item>
        <el-form-item label="按钮文案">
          <el-input v-model="form.button_text" maxlength="64" />
        </el-form-item>
        <el-form-item label="发布状态">
          <el-select v-model="form.status" style="width: 180px">
            <el-option label="草稿" value="draft" />
            <el-option label="已发布" value="published" />
            <el-option label="已下架" value="archived" />
          </el-select>
        </el-form-item>
      </el-form>

      <div class="update-preview">
        <div class="update-preview__heading">弹窗预览</div>
        <div class="update-preview__title">{{ previewVersion.title || '发现新版本' }}</div>
        <div class="update-preview__version">
          当前发布版本：{{ previewVersion.version || '未填写' }}（{{ previewVersion.version_code || '-' }}）
        </div>
        <div class="update-preview__notes">{{ previewVersion.notes || '暂无更新说明' }}</div>
        <div class="update-preview__actions">
          <el-button
            v-if="form.download_url"
            tag="a"
            :href="form.download_url"
            target="_blank"
            rel="noopener noreferrer"
            type="primary"
            size="small"
          >
            {{ form.button_text || '立即下载' }}
          </el-button>
          <el-button v-else type="primary" size="small" disabled>
            {{ form.button_text || '立即下载' }}
          </el-button>
          <el-button size="small" :disabled="form.force_update">稍后再说</el-button>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveVersion()">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getApps } from '../api/admin'
import { createAppVersion, getAppVersions, updateAppVersion } from '../api/appContent'
import { copyTextToClipboard } from '../utils/clipboard'
import { formatBeijingTime } from '../utils/datetime'

const WINDOWS_PLATFORM = 'windows'
const DEFAULT_TITLE_SUFFIX = '更新内容'

const apps = ref([])
const versions = ref([])
const selectedAppId = ref('')
const selectedVersion = ref(null)
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingVersion = ref(null)

const form = reactive({
  version: '',
  version_code: 1,
  title: '',
  notes: '',
  force_update: false,
  download_url: '',
  url_type: 'direct',
  button_text: '立即下载',
  status: 'draft'
})

const selectedApp = computed(() => apps.value.find((app) => app.app_id === selectedAppId.value) || null)
const selectedAppName = computed(() => selectedApp.value?.name || '应用')

const sortedVersions = computed(() => [...versions.value].sort((left, right) => {
  const codeDiff = Number(right.version_code || 0) - Number(left.version_code || 0)
  if (codeDiff !== 0) return codeDiff
  return String(right.updated_at || '').localeCompare(String(left.updated_at || ''))
}))

const publishedVersions = computed(() => sortedVersions.value.filter((version) => version.status === 'published'))
const currentVersion = computed(() => publishedVersions.value[0] || null)
const highestVersionCode = computed(() => sortedVersions.value.reduce((highest, version) => {
  return Math.max(highest, Number(version.version_code || 0))
}, 0))
const nextVersionCode = computed(() => highestVersionCode.value + 1)

const draftPreview = computed(() => ({
  platform: WINDOWS_PLATFORM,
  version: form.version,
  version_code: form.version_code,
  title: form.title,
  notes: form.notes,
  force_update: form.force_update,
  download_url: form.download_url,
  url_type: form.url_type,
  button_text: form.button_text,
  status: form.status
}))

const previewVersion = computed(() => (dialogVisible.value ? draftPreview.value : selectedVersion.value || draftPreview.value))

const statusText = (value) => ({ draft: '草稿', published: '已发布', archived: '已下架' }[value] || '草稿')
const statusTag = (value) => ({ draft: 'info', published: 'success', archived: 'warning' }[value] || 'info')

function effectiveState(row) {
  if (!row || row.status !== 'published') return 'not-effective'
  if (currentVersion.value?.id === row.id) return 'current'
  return 'history'
}

function effectiveTag(row) {
  return ({ current: 'success', history: 'info', 'not-effective': 'warning' }[effectiveState(row)] || 'info')
}

function effectiveStateText(row) {
  return ({ current: '当前生效', history: '历史版本', 'not-effective': '未生效' }[effectiveState(row)] || '未生效')
}

function formatLocalDate(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function defaultUpdateTitle() {
  return `${selectedAppName.value} ${formatLocalDate()} ${DEFAULT_TITLE_SUFFIX}`
}

const resetForm = () => {
  form.version = ''
  form.version_code = nextVersionCode.value
  form.title = defaultUpdateTitle()
  form.notes = ''
  form.force_update = false
  form.download_url = ''
  form.url_type = 'direct'
  form.button_text = '立即下载'
  form.status = 'draft'
}

const applyVersionToForm = (row) => {
  form.version = row.version || ''
  form.version_code = Number(row.version_code || 1)
  form.title = row.title || defaultUpdateTitle()
  form.notes = row.notes || ''
  form.force_update = Boolean(row.force_update)
  form.download_url = row.download_url || ''
  form.url_type = row.url_type || 'direct'
  form.button_text = row.button_text || '立即下载'
  form.status = row.status || 'draft'
}

const loadApps = async () => {
  const res = await getApps()
  apps.value = res.data || []
  if (!selectedAppId.value && apps.value.length > 0) {
    selectedAppId.value = apps.value[0].app_id
  }
}

const loadVersions = async () => {
  if (!selectedAppId.value) {
    versions.value = []
    selectedVersion.value = null
    return
  }
  loading.value = true
  try {
    const res = await getAppVersions(selectedAppId.value, { platform: WINDOWS_PLATFORM })
    versions.value = res.data?.items || []
    if (selectedVersion.value) {
      selectedVersion.value = versions.value.find((version) => version.id === selectedVersion.value.id) || null
    }
  } catch (error) {
    console.error('加载版本失败:', error)
    ElMessage.error('加载版本失败')
  } finally {
    loading.value = false
  }
}

const selectVersion = (row) => {
  selectedVersion.value = row
}

const openCreate = () => {
  editingVersion.value = null
  selectedVersion.value = null
  resetForm()
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingVersion.value = row
  selectedVersion.value = row
  applyVersionToForm(row)
  dialogVisible.value = true
}

const copyAsNewVersion = (row, asRollback = false) => {
  editingVersion.value = null
  selectedVersion.value = row
  resetForm()
  form.version = row.version || ''
  form.notes = row.notes || ''
  form.force_update = Boolean(row.force_update)
  form.download_url = row.download_url || ''
  form.url_type = row.url_type || 'direct'
  form.button_text = row.button_text || '立即下载'
  form.status = 'draft'
  form.title = asRollback ? `${selectedAppName.value} ${formatLocalDate()} 回退包` : defaultUpdateTitle()
  if (asRollback) {
    ElMessage.info('回退包需要使用更高版本编码，才能触发已升级客户端更新。')
  }
  dialogVisible.value = true
}

function versionPayloadFromForm(statusOverride) {
  const status = typeof statusOverride === 'string' ? statusOverride : form.status
  return {
    platform: WINDOWS_PLATFORM,
    version: form.version.trim(),
    version_code: Number(form.version_code || 1),
    title: form.title.trim(),
    notes: form.notes.trim() || null,
    force_update: form.force_update,
    download_url: form.download_url.trim() || null,
    url_type: form.url_type,
    button_text: form.button_text.trim() || '立即下载',
    status
  }
}

const confirmLowVersionPublish = async (payload) => {
  if (payload.status !== 'published') return true

  const editingVersionId = editingVersion.value?.id
  const publishingCode = Number(payload.version_code || 0)
  const highestOtherPublishedCode = publishedVersions.value.reduce((highest, version) => {
    if (version.id === editingVersionId) return highest
    return Math.max(highest, Number(version.version_code || 0))
  }, 0)
  const currentVersionCode = Number(currentVersion.value?.version_code || 0)
  const isLoweringCurrentVersion = editingVersionId === currentVersion.value?.id && publishingCode < currentVersionCode
  const needsWarning = highestOtherPublishedCode > 0
    ? publishingCode <= highestOtherPublishedCode || isLoweringCurrentVersion
    : isLoweringCurrentVersion || (!editingVersionId && currentVersionCode > 0 && publishingCode <= currentVersionCode)

  if (!needsWarning) return true

  try {
    await ElMessageBox.confirm(
      '发布的版本编码不高于当前或其他已发布版本，客户端判断可能不会触发更新，是否继续保存？',
      '版本编码提醒',
      {
        type: 'warning',
        confirmButtonText: '继续保存',
        cancelButtonText: '取消'
      }
    )
    return true
  } catch {
    return false
  }
}

async function saveVersion(statusOverride) {
  const payload = versionPayloadFromForm(statusOverride)
  if (!payload.version || !payload.title) {
    ElMessage.warning('请填写版本号和更新标题')
    return
  }
  if (payload.force_update && payload.status === 'published' && !payload.download_url) {
    ElMessage.warning('强制更新发布前必须填写下载地址')
    return
  }
  if (!(await confirmLowVersionPublish(payload))) return

  saving.value = true
  try {
    if (editingVersion.value) {
      await updateAppVersion(selectedAppId.value, editingVersion.value.id, payload)
      ElMessage.success('版本已更新')
    } else {
      await createAppVersion(selectedAppId.value, payload)
      ElMessage.success('版本已保存')
    }
    dialogVisible.value = false
    editingVersion.value = null
    await loadVersions()
  } catch (error) {
    console.error('保存版本失败:', error)
    ElMessage.error('保存版本失败')
  } finally {
    saving.value = false
  }
}

const publishDraft = (row) => {
  openEdit(row)
  form.status = 'published'
}

const archiveVersion = (row) => {
  openEdit(row)
  form.status = 'archived'
}

const copyUpdateCheckUrl = async () => {
  if (!selectedAppId.value) {
    ElMessage.warning('请先选择应用')
    return
  }
  const origin = globalThis.location?.origin || ''
  const path = `/api/v1/sdk/apps/${selectedAppId.value}/updates/check?platform=${WINDOWS_PLATFORM}`
  try {
    await copyTextToClipboard(`${origin}${path}`)
    ElMessage.success('复制成功')
  } catch (error) {
    console.error('复制检查接口失败:', error)
    ElMessage.error('复制失败，请手动复制')
  }
}

onMounted(async () => {
  await loadApps()
  await loadVersions()
})
</script>

<style scoped>
.app-versions {
  height: 100%;
}

.page-card {
  border-radius: 8px;
}

.card-header,
.filters,
.header-actions,
.update-preview__actions,
.current-release {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-header {
  justify-content: space-between;
}

.control.locked {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #f5f7fa;
  color: #606266;
  font-size: 14px;
}

.current-release {
  flex-wrap: wrap;
  padding: 12px 0 16px;
  color: #475569;
  font-size: 13px;
}

.update-preview {
  border: 1px solid #d9e7ff;
  background: #f8fbff;
  border-radius: 8px;
  padding: 16px;
  margin-top: 8px;
}

.update-preview__heading {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}

.update-preview__title {
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
}

.update-preview__version,
.update-preview__notes {
  color: #475569;
  margin-bottom: 8px;
}
</style>
