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
        <el-button type="primary" :disabled="!selectedAppId || Boolean(rowActionLoading)" @click="openCreate">
          <el-icon><Plus /></el-icon>
          新增完整版本
        </el-button>
      </div>
    </header>

    <section class="current-release">
      <article class="metric-card metric-card--primary">
        <span class="metric-card__label">当前生效</span>
        <strong>{{ currentVersion ? currentVersion.version : '暂无发布版本' }}</strong>
        <small>
          编码 {{ currentVersion ? currentVersion.version_code : '-' }}
          <template v-if="currentVersion"> · {{ currentVersion.force_update ? '强制更新' : '普通更新' }}</template>
        </small>
      </article>
      <article class="metric-card">
        <span class="metric-card__label">建议版本编码</span>
        <strong>{{ nextVersionCode }}</strong>
        <small>按 Windows 记录最高编码 + 1</small>
      </article>
      <article class="metric-card metric-card--wide">
        <span class="metric-card__label">客户端判断</span>
        <strong>客户端版本编码低于当前已发布最高编码时，将提示更新</strong>
        <small>只有已发布版本参与判断</small>
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
          <template #empty>
            <div class="version-empty-state">
              <strong>还没有发布过 Windows 版本</strong>
              <span>新增第一个版本后，客户端会根据版本编码判断是否弹出更新。</span>
              <el-button type="primary" size="small" :disabled="!selectedAppId" @click.stop="openCreate">
                新增版本
              </el-button>
            </div>
          </template>

          <el-table-column label="版本信息" min-width="150">
            <template #default="{ row }">
              <div class="version-cell">
                <strong>{{ row.version || '未填写' }}</strong>
                <span>编码 {{ row.version_code || '-' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="发布状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="生效状态" width="150">
            <template #default="{ row }">
              <div class="state-cell">
                <el-tag :type="effectiveTag(row)" effect="plain">{{ effectiveStateText(row) }}</el-tag>
                <span v-if="row.force_update" class="force-dot">强制</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="标题与说明" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="summary-cell">
                <strong>{{ row.title || '未设置标题' }}</strong>
                <span>{{ row.notes || '暂无更新说明' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="发布时间" width="180">
            <template #default="{ row }">{{ formatBeijingTime(row.published_at || row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="300" fixed="right">
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
                <el-button
                  size="small"
                  type="danger"
                  plain
                  :loading="rowActionLoading === `delete:${row.id}`"
                  :disabled="Boolean(rowActionLoading)"
                  @click.stop="deleteVersion(row)"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="history-secondary">
          <section class="assistant-card">
            <div class="assistant-card__heading">
              <div>
                <h3>发布检查</h3>
                <p>字段是否满足发布条件，一眼判断能不能发。</p>
              </div>
              <el-tag :type="releaseChecks.every((item) => item.passed) ? 'success' : 'warning'" effect="plain">
                {{ releaseChecks.filter((item) => !item.passed).length }} 项待完善
              </el-tag>
            </div>
            <div class="check-list">
              <div
                v-for="item in releaseChecks"
                :key="item.label"
                class="check-list__item"
                :class="{ 'is-passed': item.passed }"
              >
                <strong>{{ item.label }}</strong>
                <span>{{ item.passed ? '已完成' : '待完善' }}</span>
              </div>
            </div>
          </section>
          <section class="assistant-card preview-panel preview-panel--inline">
            <div class="preview-heading">
              <span>客户端弹窗预览</span>
              <el-tag :type="previewVersion.force_update ? 'danger' : 'info'" effect="plain">
                {{ previewVersion.force_update ? '强制更新' : '可稍后' }}
              </el-tag>
            </div>

            <div class="update-preview update-preview--inline">
              <div class="update-preview__title">{{ previewVersion.title || '发现新版本' }}</div>
              <div class="update-preview__version">
                Windows {{ previewVersion.version || '未填写' }} · 编码 {{ previewVersion.version_code || '-' }}
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
                  {{ previewVersion.button_text || '立即下载' }}
                </el-button>
                <el-button v-else type="primary" size="small" disabled>
                  {{ previewVersion.button_text || '立即下载' }}
                </el-button>
                <el-button size="small" :disabled="previewVersion.force_update">稍后再说</el-button>
              </div>
            </div>
          </section>
        </div>
      </section>

      <aside class="release-sidebar">
        <section class="panel draft-panel">
          <div class="panel-heading panel-heading--compact">
            <div>
              <h2>快捷发布</h2>
              <p>{{ editingVersion ? '正在编辑历史版本' : '常用字段快速创建并发布新版本' }}</p>
            </div>
            <el-tag type="info" effect="plain">Windows</el-tag>
          </div>

          <el-form class="release-form" :model="form" label-position="top">
            <div class="release-form__row">
              <el-form-item label="版本号" required>
                <el-input v-model="form.version" placeholder="例如 1.1.0" />
              </el-form-item>
              <el-form-item label="版本编码" required>
                <el-input-number v-model="form.version_code" :min="1" :max="999999999" controls-position="right" />
              </el-form-item>
            </div>
            <div v-if="showLowCodeHint" class="form-hint">低编码发布通常不会触发高版本客户端。</div>

            <div class="release-form__row">
              <el-form-item label="发布状态">
                <el-select v-model="form.status">
                  <el-option label="草稿" value="draft" />
                  <el-option label="已发布" value="published" />
                  <el-option label="已下架" value="archived" />
                </el-select>
              </el-form-item>
              <el-form-item label="按钮文案">
                <el-input v-model="form.button_text" maxlength="64" />
              </el-form-item>
            </div>

            <el-form-item label="更新标题" required>
              <el-input v-model="form.title" maxlength="128" show-word-limit />
            </el-form-item>

            <el-form-item label="更新说明">
              <el-input
                v-model="form.notes"
                type="textarea"
                :rows="3"
                maxlength="1000"
                show-word-limit
                placeholder="填写本次更新内容，客户端弹窗会展示这里的说明"
              />
            </el-form-item>

            <el-form-item label="下载地址">
              <el-input v-model="form.download_url" placeholder="https://..." />
              <div v-if="showForceDownloadHint" class="form-hint form-hint--danger">强制发布前必须填写下载地址。</div>
            </el-form-item>

            <div class="release-form__row release-form__row--compact">
              <el-form-item label="地址类型">
                <el-select v-model="form.url_type">
                  <el-option label="直链" value="direct" />
                  <el-option label="网盘/外链" value="external" />
                </el-select>
              </el-form-item>
              <el-form-item label="强制更新">
                <el-switch
                  v-model="form.force_update"
                  inline-prompt
                  active-text="开启"
                  inactive-text="关闭"
                />
              </el-form-item>
            </div>
          </el-form>

          <div v-if="showLowCodeHint" class="compact-warning">
            低于当前生效编码时，已升级客户端不会触发更新。
          </div>
          <div v-if="showForceDownloadHint" class="compact-warning compact-warning--danger">
            强制发布需要下载地址。
          </div>

          <div class="workspace-actions">
            <el-button
              :loading="saving && pendingSaveStatus === 'draft'"
              :disabled="!selectedAppId || saving || Boolean(rowActionLoading)"
              @click="saveVersion('draft')"
            >
              保存草稿
            </el-button>
            <el-button
              type="primary"
              :loading="saving && pendingSaveStatus === 'published'"
              :disabled="!selectedAppId || saving || Boolean(rowActionLoading)"
              @click="saveVersion('published')"
            >
              检查并发布
            </el-button>
          </div>
        </section>
      </aside>
    </main>

    <el-dialog
      v-model="createDialogVisible"
      title="新增完整版本"
      width="760px"
      class="version-dialog"
      :close-on-click-modal="!saving"
      :close-on-press-escape="!saving"
    >
      <div class="dialog-intro">
        <strong>完整版本信息</strong>
        <span>适合编辑正式版本、详细更新说明和下载动作。</span>
      </div>
      <el-form class="release-form release-form--dialog" :model="form" label-position="top">
        <div class="release-form__row">
          <el-form-item label="版本号" required>
            <el-input v-model="form.version" placeholder="例如 1.1.0" />
          </el-form-item>
          <el-form-item label="版本编码" required>
            <el-input-number v-model="form.version_code" :min="1" :max="999999999" controls-position="right" />
          </el-form-item>
        </div>

        <div class="release-form__row">
          <el-form-item label="发布状态">
            <el-select v-model="form.status">
              <el-option label="草稿" value="draft" />
              <el-option label="已发布" value="published" />
              <el-option label="已下架" value="archived" />
            </el-select>
          </el-form-item>
          <el-form-item label="按钮文案">
            <el-input v-model="form.button_text" maxlength="64" />
          </el-form-item>
        </div>

        <el-form-item label="更新标题" required>
          <el-input v-model="form.title" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="更新说明">
          <el-input
            v-model="form.notes"
            type="textarea"
            :rows="6"
            maxlength="1000"
            show-word-limit
            placeholder="逐条填写本次新增、修复或优化内容"
          />
        </el-form-item>
        <el-form-item label="下载地址">
          <el-input v-model="form.download_url" placeholder="https://..." />
          <div v-if="showForceDownloadHint" class="form-hint form-hint--danger">强制发布前必须填写下载地址。</div>
        </el-form-item>

        <div class="release-form__row release-form__row--compact">
          <el-form-item label="地址类型">
            <el-select v-model="form.url_type">
              <el-option label="直链" value="direct" />
              <el-option label="网盘/外链" value="external" />
            </el-select>
          </el-form-item>
          <el-form-item label="强制更新">
            <el-switch
              v-model="form.force_update"
              inline-prompt
              active-text="开启"
              inactive-text="关闭"
            />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <div class="dialog-actions">
          <el-button :disabled="saving" @click="createDialogVisible = false">取消</el-button>
          <el-button
            :loading="saving && pendingSaveStatus === 'draft'"
            :disabled="!selectedAppId || saving || Boolean(rowActionLoading)"
            @click="saveVersion('draft')"
          >
            保存草稿
          </el-button>
          <el-button
            type="primary"
            :loading="saving && pendingSaveStatus === 'published'"
            :disabled="!selectedAppId || saving || Boolean(rowActionLoading)"
            @click="saveVersion('published')"
          >
            检查并发布
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getApps } from '../api/admin'
import { createAppVersion, deleteAppVersion, getAppVersions, updateAppVersion } from '../api/appContent'
import { formatBeijingTime } from '../utils/datetime'

const WINDOWS_PLATFORM = 'windows'
const ALL_PLATFORM = 'all'
const WINDOWS_COMPATIBLE_PLATFORMS = new Set([WINDOWS_PLATFORM, ALL_PLATFORM])
const DEFAULT_TITLE_SUFFIX = '更新内容'

const apps = ref([])
const versions = ref([])
const selectedAppId = ref('')
const selectedVersion = ref(null)
const loading = ref(false)
const saving = ref(false)
const pendingSaveStatus = ref('')
const rowActionLoading = ref('')
const editingVersion = ref(null)
const createDialogVisible = ref(false)

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

function compareSdkEffectiveVersions(left, right) {
  const codeDiff = Number(right.version_code || 0) - Number(left.version_code || 0)
  if (codeDiff !== 0) return codeDiff

  const publishedDiff = String(right.published_at || '').localeCompare(String(left.published_at || ''))
  if (publishedDiff !== 0) return publishedDiff

  return Number(right.id || 0) - Number(left.id || 0)
}

const publishedVersions = computed(() => sortedVersions.value.filter((version) => version.status === 'published'))
const effectivePublishedVersions = computed(() => [...publishedVersions.value].sort(compareSdkEffectiveVersions))
const currentVersion = computed(() => effectivePublishedVersions.value[0] || null)
const highestVersionCode = computed(() => sortedVersions.value.reduce((highest, version) => {
  return Math.max(highest, Number(version.version_code || 0))
}, 0))
const nextVersionCode = computed(() => highestVersionCode.value + 1)

const isDraftPristine = computed(() => (
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

const previewVersion = computed(() => draftPreview.value)

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

const releaseChecks = computed(() => {
  const currentCode = Number(currentVersion.value?.version_code || 0)
  const formCode = Number(form.version_code || 0)
  return [
    {
      label: '版本号已填写',
      passed: Boolean(String(form.version || '').trim())
    },
    {
      label: '版本编码高于当前发布版本',
      passed: !currentCode || formCode > currentCode || editingVersion.value?.id === currentVersion.value?.id
    },
    {
      label: '按钮文案已设置',
      passed: Boolean(String(form.button_text || '').trim())
    },
    {
      label: '下载地址待确认',
      passed: Boolean(String(form.download_url || '').trim())
    }
  ]
})

const statusText = (value) => ({ draft: '草稿', published: '已发布', archived: '已下架' }[value] || '草稿')
const statusTag = (value) => ({ draft: 'info', published: 'success', archived: 'warning' }[value] || 'info')
const urlTypeText = (value) => ({ direct: '直链', external: '网盘/外链' }[value] || '直链')

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

function normalizeVersionPlatform(value) {
  return String(value || ALL_PLATFORM).trim().toLowerCase()
}

function isWindowsCompatibleVersion(version) {
  return WINDOWS_COMPATIBLE_PLATFORMS.has(normalizeVersionPlatform(version?.platform))
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
    const res = await getAppVersions(selectedAppId.value)
    versions.value = (res.data?.items || []).filter(isWindowsCompatibleVersion)
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
  createDialogVisible.value = true
}

const openEdit = (row) => {
  if (rowActionLoading.value) return
  createDialogVisible.value = false
  editingVersion.value = row
  selectedVersion.value = row
  applyVersionToForm(row)
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

async function confirmDialogPublish(payload) {
  if (payload.status !== 'published') return true

  const currentCode = Number(currentVersion.value?.version_code || 0)
  const publishCode = Number(payload.version_code || 0)
  const clientEffect = publishCode > currentCode
    ? '会成为新的最高编码，低于该编码的客户端会提示更新'
    : '不高于当前生效编码，已升级客户端可能不会再次弹窗'
  const notes = payload.notes || '未填写'

  try {
    await ElMessageBox.confirm(
      `发布后将立即影响 Windows 客户端的在线更新弹窗，请核对完整信息。\n\n应用：${selectedAppName.value}\n平台：Windows\n版本号：${payload.version || '未填写'}\n版本编码：${payload.version_code || '-'}\n发布状态：${statusText(payload.status)}\n更新标题：${payload.title || '未填写'}\n更新说明：${notes}\n下载地址：${payload.download_url || '未填写'}\n地址类型：${urlTypeText(payload.url_type)}\n按钮文案：${payload.button_text || '立即下载'}\n强制更新：${payload.force_update ? '是' : '否'}\n客户端弹窗：${clientEffect}\n\n确认发布吗？`,
      '发布确认明细',
      {
        type: 'warning',
        confirmButtonText: '确认发布',
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
  if (!(await confirmDialogPublish(payload))) return

  saving.value = true
  pendingSaveStatus.value = payload.status
  try {
    if (editingVersion.value) {
      await updateAppVersion(selectedAppId.value, editingVersion.value.id, payload)
      ElMessage.success('版本已更新')
    } else {
      await createAppVersion(selectedAppId.value, payload)
      ElMessage.success('版本已保存')
    }
    editingVersion.value = null
    createDialogVisible.value = false
    await loadVersions()
  } catch (error) {
    console.error('保存版本失败:', error)
    ElMessage.error('保存版本失败')
  } finally {
    saving.value = false
    pendingSaveStatus.value = ''
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
    if (!(await confirmDialogPublish(payload))) return
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

async function deleteVersion(row) {
  const appId = selectedAppId.value
  if (!appId || rowActionLoading.value) return

  rowActionLoading.value = `delete:${row.id}`
  try {
    await ElMessageBox.confirm(
      `删除后该版本将从版本历史中移除，不能再用于客户端更新判断。\n\n版本号：${row.version || '未填写'}\n版本编码：${row.version_code || '-'}\n发布状态：${statusText(row.status)}\n\n是否继续删除？`,
      '确认删除版本',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger'
      }
    )
    await deleteAppVersion(appId, row.id)
    ElMessage.success('版本已删除')
    if (selectedVersion.value?.id === row.id) {
      selectedVersion.value = null
    }
    await loadVersions()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除版本失败:', error)
      ElMessage.error('删除版本失败')
    }
  } finally {
    rowActionLoading.value = ''
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
  max-width: 1600px;
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
  grid-template-columns: minmax(180px, 1fr) minmax(160px, 0.75fr) minmax(320px, 1.6fr);
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
  grid-template-columns: minmax(0, 1fr) 440px;
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

.version-empty-state {
  display: flex;
  min-height: 170px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #64748b;
  text-align: center;
}

.version-empty-state strong {
  color: #0f172a;
  font-size: 18px;
}

.version-empty-state span {
  max-width: 420px;
  line-height: 1.6;
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

.history-secondary {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: 12px;
  margin-top: 14px;
}

.assistant-card {
  display: flex;
  max-height: 230px;
  min-width: 0;
  flex-direction: column;
  padding: 14px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.assistant-card h3 {
  margin: 0;
  color: #0f172a;
  font-size: 14px;
  font-weight: 760;
}

.assistant-card p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.assistant-card__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.check-list {
  display: grid;
  flex: 1;
  grid-template-columns: 1fr;
  gap: 8px;
  min-height: 0;
  overflow: hidden;
}

.check-list__item {
  display: flex;
  min-height: 34px;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  background: #fff7ed;
}

.check-list__item.is-passed {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.check-list__item span {
  color: #9a3412;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.check-list__item.is-passed span {
  color: #15803d;
}

.check-list__item strong {
  display: block;
  overflow: hidden;
  color: #0f172a;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.release-sidebar {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 16px;
}

.release-form {
  margin-bottom: 12px;
}

.release-form__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
}

.release-form__row--compact {
  align-items: center;
}

.release-form :deep(.el-form-item) {
  margin-bottom: 10px;
}

.release-form :deep(.el-form-item__label) {
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

.release-form :deep(.el-select),
.release-form :deep(.el-input-number) {
  width: 100%;
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

.preview-panel--inline {
  background: #ffffff;
}

.preview-panel--inline .preview-heading {
  margin-bottom: 10px;
}

.update-preview--inline {
  flex: 1;
  min-height: 0;
  padding: 14px;
  overflow: hidden;
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

.update-preview--inline .update-preview__notes {
  max-height: 58px;
  min-height: 42px;
  overflow: hidden;
}

.workspace-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
}

.workspace-actions :deep(.el-button) {
  margin-left: 0;
}

.dialog-intro {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid #d9e7ff;
  border-radius: 8px;
  background: #f8fbff;
}

.dialog-intro strong {
  color: #0f172a;
  font-size: 15px;
  font-weight: 760;
}

.dialog-intro span {
  color: #64748b;
  font-size: 12px;
}

.release-form--dialog {
  margin-bottom: 0;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.dialog-actions :deep(.el-button) {
  margin-left: 0;
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
  .header-controls {
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
  .history-secondary,
  .release-form__row,
  .check-list,
  .workspace-actions {
    grid-template-columns: 1fr;
  }
}
</style>
