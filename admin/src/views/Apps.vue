<template>
  <div class="apps-container">
    <el-card shadow="never" class="page-card">
      <template #header>
        <div class="card-header">
          <span>应用列表</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            创建应用
          </el-button>
        </div>
      </template>

      <el-table :data="apps" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="app_id" label="App ID" min-width="190" show-overflow-tooltip />
        <el-table-column prop="name" label="应用名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="created_by" label="创建人" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <div class="actions">
              <el-button
                size="small"
                :type="row.status === 1 ? 'warning' : 'success'"
                @click="toggleStatus(row)"
              >
                {{ row.status === 1 ? '禁用' : '启用' }}
              </el-button>
              <el-button size="small" type="primary" @click="goAppInterfaces(row)">
                接口列表
              </el-button>
              <el-button size="small" type="info" @click="viewDetail(row)">详情</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="创建应用" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="应用名称" required>
          <el-input v-model="createForm.name" placeholder="请输入应用名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="应用详情" width="700px">
      <el-descriptions :column="1" border v-if="currentApp">
        <el-descriptions-item label="App ID">{{ currentApp.app_id }}</el-descriptions-item>
        <el-descriptions-item label="应用名称">{{ currentApp.name }}</el-descriptions-item>
        <el-descriptions-item label="App Secret">
          <el-text type="danger" style="user-select: all;">••••••••••••••••</el-text>
        </el-descriptions-item>
        <el-descriptions-item label="创建人">{{ currentApp.created_by || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatBeijingTime(currentApp.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="RSA 公钥">
          <el-input v-model="currentApp.rsa_public_key" type="textarea" :rows="6" readonly />
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { createApp, deleteApp, getApps, updateAppStatus } from '../api/admin'
import { formatBeijingTime } from '../utils/datetime'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const apps = ref([])
const createDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const currentApp = ref(null)

const createForm = reactive({
  name: ''
})

const loadApps = async () => {
  loading.value = true
  try {
    const res = await getApps()
    apps.value = res.data || []
  } catch (error) {
    console.error('加载应用失败:', error)
    ElMessage.error('加载应用失败')
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  createForm.name = ''
  createDialogVisible.value = true
}

const handleCreate = async () => {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入应用名称')
    return
  }

  creating.value = true
  try {
    await createApp({ name: createForm.name.trim() })
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    await loadApps()
  } catch (error) {
    console.error('创建失败:', error)
  } finally {
    creating.value = false
  }
}

const toggleStatus = async (row) => {
  const newStatus = row.status === 1 ? 0 : 1
  const action = newStatus === 1 ? '启用' : '禁用'

  try {
    await ElMessageBox.confirm(`确定要${action}该应用吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await updateAppStatus(row.app_id, newStatus)
    ElMessage.success(`${action}成功`)
    await loadApps()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('操作失败:', error)
    }
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除应用“${row.name}”吗？此操作会删除该应用下的卡密和设备记录。`,
      '警告',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'error',
        distinguishCancelAndClose: true
      }
    )
    const res = await deleteApp(row.app_id)
    ElMessage.success(res.message || '删除成功')
    await loadApps()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

const viewDetail = (row) => {
  currentApp.value = row
  detailDialogVisible.value = true
}

const goAppInterfaces = (row) => {
  router.push({
    path: `/apps/${row.app_id}/interfaces`,
    query: { app_name: row.name }
  })
}

onMounted(loadApps)
</script>

<style scoped>
.apps-container {
  height: 100%;
}

.page-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

:deep(.el-table th) {
  background: #f8fafc;
  color: #334155;
  font-weight: 600;
}
</style>
