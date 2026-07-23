<template>
  <div class="app-notices">
    <el-card shadow="never" class="page-card">
      <template #header>
        <div class="card-header">
          <div class="filters">
            <el-select v-model="selectedAppId" placeholder="选择应用" filterable style="width: 260px" @change="loadNotices">
              <el-option
                v-for="app in apps"
                :key="app.app_id"
                :label="app.name"
                :value="app.app_id"
              />
            </el-select>
          </div>
          <el-button type="primary" :disabled="!selectedAppId" @click="openCreate">
            <el-icon><Plus /></el-icon>
            发布公告
          </el-button>
        </div>
      </template>

      <el-table :data="notices" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="公告标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="content" label="公告内容" min-width="240" show-overflow-tooltip />
        <el-table-column prop="level" label="级别" width="110">
          <template #default="{ row }">
            <el-tag :type="noticeTag(row.level)">{{ noticeLevelText(row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="popup" label="启动弹窗" width="110">
          <template #default="{ row }">{{ row.popup ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="show_once" label="只弹一次" width="110">
          <template #default="{ row }">{{ row.show_once ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="revision" label="修订号" width="90" />
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <div class="action-group">
              <el-button
                size="small"
                type="primary"
                plain
                :disabled="Boolean(rowActionLoading)"
                @click.stop="openEdit(row)"
              >
                编辑
              </el-button>
              <el-button
                size="small"
                type="danger"
                plain
                :loading="rowActionLoading === `delete:${row.id}`"
                :disabled="Boolean(rowActionLoading)"
                @click.stop="deleteNotice(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingNotice ? '编辑公告' : '发布公告'" width="680px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="公告标题" required>
          <el-input v-model="form.title" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="公告内容" required>
          <el-input v-model="form.content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="公告级别">
          <el-select v-model="form.level" style="width: 180px">
            <el-option label="普通" value="normal" />
            <el-option label="重要" value="important" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用公告">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="启动弹窗">
          <el-switch v-model="form.popup" />
        </el-form-item>
        <el-form-item label="只弹一次">
          <el-switch v-model="form.show_once" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveNotice">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getApps } from '../api/admin'
import { createAppNotice, deleteAppNotice, getAppNotices, updateAppNotice } from '../api/appContent'
import { formatBeijingTime } from '../utils/datetime'

const apps = ref([])
const notices = ref([])
const selectedAppId = ref('')
const loading = ref(false)
const saving = ref(false)
const rowActionLoading = ref('')
const dialogVisible = ref(false)
const editingNotice = ref(null)

const form = reactive({
  title: '',
  content: '',
  level: 'normal',
  enabled: true,
  popup: false,
  show_once: true
})

const noticeLevelText = (level) => ({ normal: '普通', important: '重要', urgent: '紧急' }[level] || '普通')
const noticeTag = (level) => ({ normal: 'info', important: 'warning', urgent: 'danger' }[level] || 'info')

const resetForm = () => {
  form.title = ''
  form.content = ''
  form.level = 'normal'
  form.enabled = true
  form.popup = false
  form.show_once = true
}

const loadApps = async () => {
  const res = await getApps()
  apps.value = res.data || []
  if (!selectedAppId.value && apps.value.length > 0) {
    selectedAppId.value = apps.value[0].app_id
  }
}

const loadNotices = async () => {
  if (!selectedAppId.value) {
    notices.value = []
    return
  }
  loading.value = true
  try {
    const res = await getAppNotices(selectedAppId.value)
    notices.value = res.data?.items || []
  } catch (error) {
    console.error('加载公告失败:', error)
    ElMessage.error('加载公告失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingNotice.value = null
  resetForm()
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingNotice.value = row
  form.title = row.title || ''
  form.content = row.content || ''
  form.level = row.level || 'normal'
  form.enabled = Boolean(row.enabled)
  form.popup = Boolean(row.popup)
  form.show_once = Boolean(row.show_once)
  dialogVisible.value = true
}

const saveNotice = async () => {
  if (!form.title.trim() || !form.content.trim()) {
    ElMessage.warning('请填写公告标题和内容')
    return
  }
  saving.value = true
  const payload = {
    title: form.title.trim(),
    content: form.content.trim(),
    level: form.level,
    enabled: form.enabled,
    popup: form.popup,
    show_once: form.show_once
  }
  try {
    if (editingNotice.value) {
      await updateAppNotice(selectedAppId.value, editingNotice.value.id, payload)
      ElMessage.success('公告已更新')
    } else {
      await createAppNotice(selectedAppId.value, payload)
      ElMessage.success('公告已发布')
    }
    dialogVisible.value = false
    await loadNotices()
  } catch (error) {
    console.error('保存公告失败:', error)
    ElMessage.error('保存公告失败')
  } finally {
    saving.value = false
  }
}

const deleteNotice = async (row) => {
  const appId = selectedAppId.value
  if (!appId || rowActionLoading.value) return

  rowActionLoading.value = `delete:${row.id}`
  try {
    await ElMessageBox.confirm(
      `删除后该公告将不再展示给客户端。\n\n公告标题：${row.title || '未填写'}\n公告级别：${noticeLevelText(row.level)}\n启用状态：${row.enabled ? '启用' : '停用'}\n\n是否继续删除？`,
      '确认删除公告',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger'
      }
    )
    await deleteAppNotice(appId, row.id)
    ElMessage.success('公告已删除')
    if (editingNotice.value?.id === row.id) {
      dialogVisible.value = false
      editingNotice.value = null
    }
    await loadNotices()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除公告失败:', error)
      ElMessage.error('删除公告失败')
    }
  } finally {
    rowActionLoading.value = ''
  }
}

onMounted(async () => {
  await loadApps()
  await loadNotices()
})
</script>

<style scoped>
.app-notices {
  height: 100%;
}

.page-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 10px;
}

.action-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
