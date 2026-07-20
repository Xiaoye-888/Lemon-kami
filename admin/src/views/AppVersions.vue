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
            <el-select v-model="platformFilter" style="width: 150px" @change="loadVersions">
              <el-option label="全部平台" value="" />
              <el-option label="通用" value="all" />
              <el-option label="Windows" value="windows" />
              <el-option label="macOS" value="macos" />
              <el-option label="Android" value="android" />
            </el-select>
          </div>
          <el-button type="primary" :disabled="!selectedAppId" @click="openCreate">
            <el-icon><Plus /></el-icon>
            新增版本
          </el-button>
        </div>
      </template>

      <el-table :data="versions" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="version" label="版本号" width="130" />
        <el-table-column prop="version_code" label="版本编码" width="110" />
        <el-table-column prop="platform" label="平台" width="110">
          <template #default="{ row }">{{ platformText(row.platform) }}</template>
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
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingVersion ? '编辑版本' : '新增版本'" width="760px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="平台">
          <el-select v-model="form.platform" style="width: 180px">
            <el-option label="通用" value="all" />
            <el-option label="Windows" value="windows" />
            <el-option label="macOS" value="macos" />
            <el-option label="Android" value="android" />
          </el-select>
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
        <div class="update-preview__title">{{ form.title || '发现新版本' }}</div>
        <div class="update-preview__version">当前发布版本：{{ form.version || '未填写' }}</div>
        <div class="update-preview__notes">{{ form.notes || '暂无更新说明' }}</div>
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
        <el-button type="primary" :loading="saving" @click="saveVersion">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getApps } from '../api/admin'
import { createAppVersion, getAppVersions, updateAppVersion } from '../api/appContent'
import { formatBeijingTime } from '../utils/datetime'

const apps = ref([])
const versions = ref([])
const selectedAppId = ref('')
const platformFilter = ref('')
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingVersion = ref(null)

const form = reactive({
  platform: 'all',
  version: '',
  version_code: 1,
  title: '发现新版本',
  notes: '',
  force_update: false,
  download_url: '',
  url_type: 'direct',
  button_text: '立即下载',
  status: 'draft'
})

const platformText = (value) => ({ all: '通用', windows: 'Windows', macos: 'macOS', android: 'Android' }[value] || '通用')
const statusText = (value) => ({ draft: '草稿', published: '已发布', archived: '已下架' }[value] || '草稿')
const statusTag = (value) => ({ draft: 'info', published: 'success', archived: 'warning' }[value] || 'info')

const resetForm = () => {
  form.platform = 'all'
  form.version = ''
  form.version_code = 1
  form.title = '发现新版本'
  form.notes = ''
  form.force_update = false
  form.download_url = ''
  form.url_type = 'direct'
  form.button_text = '立即下载'
  form.status = 'draft'
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
    return
  }
  loading.value = true
  try {
    const params = platformFilter.value ? { platform: platformFilter.value } : undefined
    const res = await getAppVersions(selectedAppId.value, params)
    versions.value = res.data?.items || []
  } catch (error) {
    console.error('加载版本失败:', error)
    ElMessage.error('加载版本失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingVersion.value = null
  resetForm()
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingVersion.value = row
  form.platform = row.platform || 'all'
  form.version = row.version || ''
  form.version_code = Number(row.version_code || 1)
  form.title = row.title || '发现新版本'
  form.notes = row.notes || ''
  form.force_update = Boolean(row.force_update)
  form.download_url = row.download_url || ''
  form.url_type = row.url_type || 'direct'
  form.button_text = row.button_text || '立即下载'
  form.status = row.status || 'draft'
  dialogVisible.value = true
}

const saveVersion = async () => {
  if (!form.version.trim() || !form.title.trim()) {
    ElMessage.warning('请填写版本号和更新标题')
    return
  }
  if (form.force_update && form.status === 'published' && !form.download_url.trim()) {
    ElMessage.warning('强制更新发布前必须填写下载地址')
    return
  }
  saving.value = true
  const payload = {
    platform: form.platform,
    version: form.version.trim(),
    version_code: Number(form.version_code || 1),
    title: form.title.trim(),
    notes: form.notes || null,
    force_update: form.force_update,
    download_url: form.download_url.trim() || null,
    url_type: form.url_type,
    button_text: form.button_text.trim() || '立即下载',
    status: form.status
  }
  try {
    if (editingVersion.value) {
      await updateAppVersion(selectedAppId.value, editingVersion.value.id, payload)
      ElMessage.success('版本已更新')
    } else {
      await createAppVersion(selectedAppId.value, payload)
      ElMessage.success('版本已保存')
    }
    dialogVisible.value = false
    await loadVersions()
  } catch (error) {
    console.error('保存版本失败:', error)
    ElMessage.error('保存版本失败')
  } finally {
    saving.value = false
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
.update-preview__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-header {
  justify-content: space-between;
}

.update-preview {
  border: 1px solid #d9e7ff;
  background: #f8fbff;
  border-radius: 8px;
  padding: 16px;
  margin-top: 8px;
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
