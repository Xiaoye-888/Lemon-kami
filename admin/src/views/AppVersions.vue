<template>
  <div class="app-versions">
    <header class="page-header">
      <div class="page-title-block">
        <h1>版本更新</h1>
        <p>Windows 客户端发布与更新弹窗</p>
      </div>
      <div class="header-controls">
        <el-select
          v-model="selectedAppId"
          class="app-select"
          placeholder="选择应用"
          filterable
          :disabled="Boolean(rowActionLoading)"
          @change="loadVersions"
        >
          <el-option
            v-for="app in apps"
            :key="app.app_id"
            :label="app.name"
            :value="app.app_id"
          />
        </el-select>
        <div class="control locked">Windows</div>
        <el-button :disabled="!selectedAppId" @click="copyUpdateCheckUrl">
          <el-icon><DocumentCopy /></el-icon>
          复制检查接口
        </el-button>
        <el-button type="primary" :disabled="!selectedAppId || Boolean(rowActionLoading)" @click="openCreate">
          <el-icon><Plus /></el-icon>
          新增版本
        </el-button>
      </div>
    </header>

    <section class="current-release">
      <article class="metric-card metric-card--primary">
        <span class="metric-card__label">当前生效</span>
        <strong>{{ currentVersion ? currentVersion.version : '暂无发布版本' }}</strong>
        <small>
          Code {{ currentVersion ? currentVersion.version_code : '-' }}
          <template v-if="currentVersion"> · {{ currentVersion.force_update ? '强制更新' : '普通更新' }}</template>
        </small>
      </article>
      <article class="metric-card">
        <span class="metric-card__label">建议版本编码</span>
        <strong>{{ nextVersionCode }}</strong>
        <small>按 Windows 记录最高编码 + 1</small>
      </article>
      <article class="metric-card">
        <span class="metric-card__label">客户端判断</span>
        <strong>current_version_code &lt; latest_version_code</strong>
        <small>仅已发布最高编码生效</small>
      </article>
      <article class="metric-card metric-card--wide">
        <span class="metric-card__label">默认标题</span>
        <strong>{{ defaultUpdateTitle() }}</strong>
        <small>回退包也需要更高版本编码</small>
      </article>
    </section>

    <main class="workspace-grid">
      <section class="panel history-panel">
        <div class="panel-heading">
          <div>
            <h2>版本历史</h2>
            <p>以版本表为核心处理发布、复制与下架</p>
          </div>
          <el-tag v-if="currentVersion" type="success" effect="plain">
            当前 Code {{ currentVersion.version_code }}
          </el-tag>
        </div>

        <el-table
          :data="sortedVersions"
          v-loading="loading"
          class="history-table"
          :row-class-name="versionRowClassName"
          @row-click="selectVersion"
        >
          <el-table-column label="Version" min-width="150">
            <template #default="{ row }">
              <div class="version-cell">
                <strong>{{ row.version || '未填写' }}</strong>
                <span>Code {{ row.version_code || '-' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Status" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Effective state" width="150">
            <template #default="{ row }">
              <div class="state-cell">
                <el-tag :type="effectiveTag(row)" effect="plain">{{ effectiveStateText(row) }}</el-tag>
                <span v-if="row.force_update" class="force-dot">强制</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Title / Summary" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="summary-cell">
                <strong>{{ row.title || '未设置标题' }}</strong>
                <span>{{ row.notes || '暂无更新说明' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Published time" width="180">
            <template #default="{ row }">{{ formatBeijingTime(row.published_at || row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="Actions" width="300" fixed="right">
            <template #default="{ row }">
              <div class="action-group">
                <el-button
                  size="small"
                  type="primary"
                  plain
                  :disabled="Boolean(rowActionLoading)"
                  @click.stop="openEdit(row)"
                >
                  {{ row.status === 'draft' ? '继续编辑' : '编辑' }}
                </el-button>
                <el-button
                  size="small"
                  plain
                  :disabled="Boolean(rowActionLoading)"
                  @click.stop="copyAsNewVersion(row, row.status === 'archived')"
                >
                  {{ row.status === 'archived' ? '复制为回退包' : '复制新版本' }}
                </el-button>
                <el-button
                  v-if="row.status === 'draft'"
                  size="small"
                  type="success"
                  plain
                  :loading="rowActionLoading === `publish:${row.id}`"
                  :disabled="Boolean(rowActionLoading)"
                  @click.stop="publishDraft(row)"
                >
                  立即发布
                </el-button>
                <el-button
                  v-if="row.status !== 'archived'"
                  size="small"
                  type="warning"
                  plain
                  :loading="rowActionLoading === `archive:${row.id}`"
                  :disabled="Boolean(rowActionLoading)"
                  @click.stop="archiveVersion(row)"
                >
                  立即下架
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <aside class="release-sidebar">
        <section class="panel draft-panel">
          <div class="panel-heading panel-heading--compact">
            <div>
              <h2>发布工作区</h2>
              <p>新版本草稿</p>
            </div>
            <el-tag type="info" effect="plain">Windows</el-tag>
          </div>

          <div class="draft-summary">
            <div class="draft-summary__item">
              <span>版本编码</span>
              <strong>{{ draftPreview.version_code || nextVersionCode }}</strong>
            </div>
            <div class="draft-summary__item">
              <span>发布状态</span>
              <el-tag :type="statusTag(draftPreview.status)" effect="plain">{{ statusText(draftPreview.status) }}</el-tag>
            </div>
            <div class="draft-summary__item draft-summary__item--wide">
              <span>默认标题</span>
              <strong>{{ draftPreview.title || defaultUpdateTitle() }}</strong>
            </div>
            <div class="draft-summary__item draft-summary__item--wide">
              <span>按钮文案</span>
              <strong>{{ draftPreview.button_text || '立即下载' }}</strong>
            </div>
          </div>

          <div v-if="showLowCodeHint" class="compact-warning">
            低于当前生效编码时，已升级客户端不会触发更新。
          </div>
          <div v-if="showForceDownloadHint" class="compact-warning compact-warning--danger">
            强制发布需要下载地址。
          </div>

          <el-button type="primary" :disabled="!selectedAppId || Boolean(rowActionLoading)" @click="openCreate">
            <el-icon><Plus /></el-icon>
            新增版本
          </el-button>
        </section>

        <section class="panel preview-panel">
          <div class="preview-heading">
            <span>弹窗预览</span>
            <el-tag :type="previewVersion.force_update ? 'danger' : 'info'" effect="plain">
              {{ previewVersion.force_update ? '强制更新' : '可稍后' }}
            </el-tag>
          </div>

          <div class="update-preview update-preview--sidebar">
            <div class="update-preview__title">{{ previewVersion.title || '发现新版本' }}</div>
            <div class="update-preview__version">
              Windows {{ previewVersion.version || '未填写' }} · Code {{ previewVersion.version_code || '-' }}
            </div>
            <div class="update-preview__notes">{{ previewVersion.notes || '暂无更新说明' }}</div>
            <div class="update-preview__actions">
              <el-button
                v-if="previewVersion.download_url"
                tag="a"
                :href="previewVersion.download_url"
                target="_blank"
                rel="noopener noreferrer"
                type="primary"
                size="small"
              >
                {{ previewVersion.button_text || '立即下载' }}
              </el-button>
              <el-button v-else type="primary" size="small" disabled>
                {{ previewVersion.button_text || '立即下载' }}
              </el-button>
              <el-button size="small" :disabled="previewVersion.force_update">稍后再说</el-button>
            </div>
          </div>
        </section>
      </aside>
    </main>

    <el-dialog v-model="dialogVisible" :title="editingVersion ? '编辑版本' : '新增版本'" width="860px" class="version-dialog">
      <div class="dialog-grid">
        <el-form :model="form" label-width="110px">
          <el-form-item label="平台">
            <div class="control locked">Windows</div>
          </el-form-item>
          <el-form-item label="版本号" required>
            <el-input v-model="form.version" placeholder="例如 1.1.0" />
          </el-form-item>
          <el-form-item label="版本编码" required>
            <el-input-number v-model="form.version_code" :min="1" :max="999999999" />
            <div v-if="showLowCodeHint" class="form-hint">低编码发布通常不会触发高版本客户端。</div>
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
            <div v-if="showForceDownloadHint" class="form-hint form-hint--danger">强制发布前必须填写下载地址。</div>
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

        <div class="dialog-preview">
          <div class="preview-heading">
            <span>弹窗预览</span>
            <el-tag :type="form.force_update ? 'danger' : 'info'" effect="plain">
              {{ form.force_update ? '强制更新' : '可稍后' }}
            </el-tag>
          </div>
          <div class="update-preview">
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
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="saving || Boolean(rowActionLoading)" @click="saveVersion()">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DocumentCopy, Plus } from '@element-plus/icons-vue'
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
const rowActionLoading = ref('')
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

const isDraftPristine = computed(() => (
  !dialogVisible.value &&
  !editingVersion.value &&
  !form.version &&
  !form.title &&
  !form.notes &&
  !form.download_url &&
  !form.force_update &&
  form.url_type === 'direct' &&
  form.button_text === '立即下载' &&
  form.status === 'draft'
))

const draftPreview = computed(() => ({
  platform: WINDOWS_PLATFORM,
  version: form.version,
  version_code: isDraftPristine.value ? nextVersionCode.value : Number(form.version_code || nextVersionCode.value),
  title: form.title || defaultUpdateTitle(),
  notes: form.notes,
  force_update: form.force_update,
  download_url: form.download_url,
  url_type: form.url_type,
  button_text: form.button_text,
  status: form.status
}))

const previewVersion = computed(() => (dialogVisible.value ? draftPreview.value : selectedVersion.value || draftPreview.value))

const showForceDownloadHint = computed(() => {
  return form.force_update && form.status === 'published' && !String(form.download_url || '').trim()
})

const showLowCodeHint = computed(() => {
  if (form.status !== 'published') return false
  const publishingCode = Number(form.version_code || 0)
  if (!publishingCode) return false
  const editingVersionId = editingVersion.value?.id
  const highestOtherPublishedCode = publishedVersions.value.reduce((highest, version) => {
    if (version.id === editingVersionId) return highest
    return Math.max(highest, Number(version.version_code || 0))
  }, 0)
  return highestOtherPublishedCode > 0 && publishingCode <= highestOtherPublishedCode
})

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

const versionRowClassName = ({ row }) => (effectiveState(row) === 'current' ? 'is-current-effective' : '')

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
  if (rowActionLoading.value) return
  editingVersion.value = null
  selectedVersion.value = null
  resetForm()
  dialogVisible.value = true
}

const openEdit = (row) => {
  if (rowActionLoading.value) return
  editingVersion.value = row
  selectedVersion.value = row
  applyVersionToForm(row)
  dialogVisible.value = true
}

const copyAsNewVersion = (row, asRollback = false) => {
  if (rowActionLoading.value) return
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

function versionPayloadFromVersion(row, statusOverride) {
  return {
    platform: WINDOWS_PLATFORM,
    version: String(row.version || '').trim(),
    version_code: Number(row.version_code || 1),
    title: String(row.title || '').trim(),
    notes: String(row.notes || '').trim() || null,
    force_update: Boolean(row.force_update),
    download_url: String(row.download_url || '').trim() || null,
    url_type: row.url_type || 'direct',
    button_text: String(row.button_text || '').trim() || '立即下载',
    status: typeof statusOverride === 'string' ? statusOverride : row.status || 'draft'
  }
}

const confirmLowVersionPublish = async (payload, excludedVersionId = editingVersion.value?.id) => {
  if (payload.status !== 'published') return true

  const publishingCode = Number(payload.version_code || 0)
  const highestOtherPublishedCode = publishedVersions.value.reduce((highest, version) => {
    if (version.id === excludedVersionId) return highest
    return Math.max(highest, Number(version.version_code || 0))
  }, 0)
  const currentVersionCode = Number(currentVersion.value?.version_code || 0)
  const isLoweringCurrentVersion = excludedVersionId === currentVersion.value?.id && publishingCode < currentVersionCode
  const needsWarning = highestOtherPublishedCode > 0
    ? publishingCode <= highestOtherPublishedCode || isLoweringCurrentVersion
    : isLoweringCurrentVersion || (!excludedVersionId && currentVersionCode > 0 && publishingCode <= currentVersionCode)

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
  if (rowActionLoading.value) return

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

async function publishDraft(row) {
  const appId = selectedAppId.value
  if (!appId || rowActionLoading.value) return

  rowActionLoading.value = `publish:${row.id}`
  const payload = versionPayloadFromVersion(row, 'published')
  try {
    if (!payload.version || !payload.title) {
      ElMessage.warning('请填写版本号和更新标题')
      return
    }
    if (payload.force_update && !payload.download_url) {
      ElMessage.warning('强制更新发布前必须填写下载地址')
      return
    }
    if (!(await confirmLowVersionPublish(payload, row.id))) return

    await ElMessageBox.confirm(
      '发布后将立即影响 Windows 客户端的在线更新弹窗，是否继续？',
      '确认发布',
      {
        type: 'warning',
        confirmButtonText: '立即发布',
        cancelButtonText: '取消'
      }
    )
    await updateAppVersion(appId, row.id, payload)
    ElMessage.success('版本已发布')
    selectedVersion.value = row
    await loadVersions()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('发布版本失败:', error)
      ElMessage.error('发布版本失败')
    }
  } finally {
    rowActionLoading.value = ''
  }
}

async function archiveVersion(row) {
  const appId = selectedAppId.value
  if (!appId || rowActionLoading.value) return

  rowActionLoading.value = `archive:${row.id}`
  const payload = versionPayloadFromVersion(row, 'archived')
  try {
    await ElMessageBox.confirm(
      '下架后该版本将不再作为 Windows 更新提示使用，是否继续？',
      '确认下架',
      {
        type: 'warning',
        confirmButtonText: '立即下架',
        cancelButtonText: '取消'
      }
    )
    await updateAppVersion(appId, row.id, payload)
    ElMessage.success('版本已下架')
    selectedVersion.value = row
    await loadVersions()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('下架版本失败:', error)
      ElMessage.error('下架版本失败')
    }
  } finally {
    rowActionLoading.value = ''
  }
}

const copyUpdateCheckUrl = async () => {
  if (!selectedAppId.value) {
    ElMessage.warning('请先选择应用')
    return
  }
  const origin = globalThis.location?.origin || ''
  const query = new URLSearchParams({
    platform: WINDOWS_PLATFORM,
    current_version_code: String(currentVersion.value?.version_code || 0)
  })
  const path = `/api/v1/sdk/apps/${selectedAppId.value}/updates/check?${query.toString()}`
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
  min-height: 100%;
  padding: 24px;
  background: #f5f7fb;
  color: #0f172a;
}

.page-header,
.current-release,
.workspace-grid {
  max-width: 1480px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.page-title-block h1 {
  margin: 0;
  color: #0f172a;
  font-size: 26px;
  font-weight: 760;
  line-height: 1.2;
}

.page-title-block p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 14px;
}

.header-controls,
.update-preview__actions,
.state-cell,
.action-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-controls {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.app-select {
  width: 260px;
}

.control.locked {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #d7deea;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-size: 14px;
  font-weight: 600;
}

.current-release {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(160px, 0.75fr) minmax(220px, 1fr) minmax(260px, 1.2fr);
  gap: 12px;
  margin-bottom: 16px;
}

.metric-card,
.panel {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.metric-card {
  min-width: 0;
  padding: 14px 16px;
}

.metric-card--primary {
  border-color: #bfd7ff;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.metric-card__label {
  display: block;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.metric-card strong {
  display: block;
  overflow: hidden;
  color: #0f172a;
  font-size: 18px;
  font-weight: 760;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-card small {
  display: block;
  overflow: hidden;
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
  align-items: start;
}

.panel {
  min-width: 0;
  padding: 16px;
}

.panel-heading,
.preview-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-heading h2 {
  margin: 0;
  color: #0f172a;
  font-size: 16px;
  font-weight: 760;
}

.panel-heading p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
}

.panel-heading--compact {
  margin-bottom: 12px;
}

.history-table {
  width: 100%;
}

.version-cell,
.summary-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.version-cell strong,
.summary-cell strong {
  overflow: hidden;
  color: #0f172a;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.version-cell span,
.summary-cell span {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.force-dot {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 12px;
  font-weight: 700;
}

.action-group {
  max-width: 100%;
  flex-wrap: wrap;
  gap: 6px 8px;
}

.action-group :deep(.el-button) {
  flex: 0 0 auto;
}

.action-group :deep(.el-button + .el-button),
.update-preview__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.release-sidebar {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 16px;
}

.draft-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.draft-summary__item {
  min-width: 0;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.draft-summary__item--wide {
  grid-column: 1 / -1;
}

.draft-summary__item span {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
}

.draft-summary__item strong {
  display: block;
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-warning,
.form-hint {
  border-radius: 8px;
  background: #fff7ed;
  color: #9a3412;
  font-size: 12px;
  line-height: 1.5;
}

.compact-warning {
  margin-bottom: 10px;
  padding: 8px 10px;
}

.compact-warning--danger,
.form-hint--danger {
  background: #fef2f2;
  color: #b91c1c;
}

.form-hint {
  width: 100%;
  margin-top: 8px;
  padding: 6px 8px;
}

.preview-heading {
  margin-bottom: 12px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 760;
}

.update-preview {
  border: 1px solid #d9e7ff;
  border-radius: 10px;
  background: #f8fbff;
  padding: 16px;
}

.update-preview--sidebar {
  min-height: 210px;
}

.update-preview__title {
  margin-bottom: 10px;
  color: #0f172a;
  font-size: 18px;
  font-weight: 760;
  line-height: 1.35;
}

.update-preview__version,
.update-preview__notes {
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.update-preview__notes {
  min-height: 68px;
  margin: 12px 0;
  white-space: pre-wrap;
}

.dialog-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 18px;
  align-items: start;
}

.dialog-preview {
  position: sticky;
  top: 0;
}

:deep(.version-dialog.el-dialog),
:deep(.version-dialog .el-dialog),
:deep(.el-dialog.version-dialog) {
  max-width: 92vw;
}

:deep(.history-table .is-current-effective td.el-table__cell) {
  background: #f8fbff;
}

:deep(.history-table .is-current-effective td.el-table__cell:first-child) {
  box-shadow: inset 3px 0 0 #2563eb;
}

@media (max-width: 1200px) {
  .current-release,
  .workspace-grid {
    grid-template-columns: 1fr 1fr;
  }

  .history-panel,
  .release-sidebar {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .app-versions {
    padding: 16px;
  }

  .page-header,
  .header-controls,
  .dialog-grid {
    display: block;
  }

  .header-controls {
    margin-top: 14px;
  }

  .header-controls > * {
    width: 100%;
    margin-bottom: 10px;
  }

  .app-select {
    width: 100%;
  }

  .current-release,
  .draft-summary {
    grid-template-columns: 1fr;
  }

  .dialog-preview {
    position: static;
    margin-top: 16px;
  }
}
</style>
