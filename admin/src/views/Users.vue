<template>
  <div class="users-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>管理员账号</span>
          <el-button v-if="isAdmin" type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            创建账号
          </el-button>
        </div>
      </template>

      <el-table
        :data="users"
        v-loading="loading"
        element-loading-custom-class="yz-bounce"
        border
        stripe
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="email" label="邮箱" min-width="200" />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login" label="最后登录" width="180">
          <template #default="{ row }">
            {{ formatBeijingTime(row.last_login) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <!-- 只有 admin 或自己的账号可以编辑 -->
            <el-button 
              v-if="isAdmin || row.username === currentUsername"
              size="small" 
              type="primary" 
              @click="showEditDialog(row)"
            >
              编辑
            </el-button>
            <!-- 只有 admin 或自己的账号可以重置密码 -->
            <el-button 
              v-if="isAdmin || row.username === currentUsername"
              size="small" 
              type="warning" 
              @click="showResetPassword(row)"
            >
              重置密码
            </el-button>
            <!-- 只有 admin 可以启用/禁用 -->
            <el-button
              v-if="isAdmin && row.username !== currentUsername"
              size="small"
              :type="row.status === 1 ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 1 ? '禁用' : '启用' }}
            </el-button>
            <!-- 只有 admin 可以删除（不能删除自己） -->
            <el-button 
              v-if="isAdmin && row.username !== currentUsername"
              size="small" 
              type="danger" 
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑管理员' : '创建管理员'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="用户名" required v-if="!isEdit">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" required v-if="!isEdit">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetPasswordVisible" title="重置密码" width="400px">
      <el-form :model="resetForm" label-width="100px">
        <el-form-item label="新密码" required>
          <el-input
            v-model="resetForm.new_password"
            type="password"
            placeholder="请输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPasswordVisible = false">取消</el-button>
        <el-button type="primary" @click="handleResetPassword" :loading="resetting">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '../utils/request'
import { useUserStore } from '../stores/user'
import { formatBeijingTime } from '../utils/datetime'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.userInfo?.is_admin || false)
const currentUsername = computed(() => userStore.userInfo?.username || '')

const loading = ref(false)
const submitting = ref(false)
const resetting = ref(false)
const users = ref([])
const dialogVisible = ref(false)
const resetPasswordVisible = ref(false)
const isEdit = ref(false)
const currentUser = ref(null)

const form = reactive({
  username: '',
  password: '',
  email: '',
  phone: ''
})

const resetForm = reactive({
  new_password: ''
})

// 加载用户列表
const loadUsers = async () => {
  loading.value = true
  try {
    const res = await request({
      url: '/admin/users',
      method: 'get'
    })
    users.value = res.data
  } catch (error) {
    console.error('加载失败:', error)
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

// 显示创建对话框
const showCreateDialog = () => {
  isEdit.value = false
  Object.assign(form, {
    username: '',
    password: '',
    email: '',
    phone: ''
  })
  dialogVisible.value = true
}

// 显示编辑对话框
const showEditDialog = (row) => {
  isEdit.value = true
  currentUser.value = row
  Object.assign(form, {
    username: row.username,
    password: '',
    email: row.email,
    phone: row.phone
  })
  dialogVisible.value = true
}

// 提交表单
const handleSubmit = async () => {
  if (!isEdit.value && (!form.username || !form.password)) {
    ElMessage.warning('请填写必填项')
    return
  }

  submitting.value = true
  try {
    if (isEdit.value) {
      // 编辑
      await request({
        url: `/admin/users/${currentUser.value.id}`,
        method: 'put',
        params: {
          email: form.email,
          phone: form.phone
        }
      })
      ElMessage.success('更新成功')
    } else {
      // 创建
      await request({
        url: '/admin/users',
        method: 'post',
        params: {
          username: form.username,
          password: form.password,
          email: form.email,
          phone: form.phone
        }
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadUsers()
  } catch (error) {
    console.error('操作失败:', error)
  } finally {
    submitting.value = false
  }
}

// 显示重置密码对话框
const showResetPassword = (row) => {
  currentUser.value = row
  resetForm.new_password = ''
  resetPasswordVisible.value = true
}

// 重置密码
const handleResetPassword = async () => {
  if (!resetForm.new_password || resetForm.new_password.length < 6) {
    ElMessage.warning('密码长度不能小于6位')
    return
  }

  resetting.value = true
  try {
    await request({
      url: `/admin/users/${currentUser.value.id}/password`,
      method: 'put',
      params: { new_password: resetForm.new_password }
    })
    ElMessage.success('密码重置成功')
    resetPasswordVisible.value = false
  } catch (error) {
    console.error('重置失败:', error)
  } finally {
    resetting.value = false
  }
}

// 切换状态
const toggleStatus = async (row) => {
  const newStatus = row.status === 1 ? 0 : 1
  const action = newStatus === 1 ? '启用' : '禁用'
  
  try {
    await ElMessageBox.confirm(`确定要${action}该账号吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await request({
      url: `/admin/users/${row.id}`,
      method: 'put',
      params: { status: newStatus }
    })
    ElMessage.success(`${action}成功`)
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('操作失败:', error)
    }
  }
}

// 删除用户
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该账号吗？此操作不可恢复！', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'error'
    })
    
    await request({
      url: `/admin/users/${row.id}`,
      method: 'delete'
    })
    ElMessage.success('删除成功')
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
    }
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.users-container {
  height: 100%;
  animation: fadeIn 0.5s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

:deep(.el-table th) {
  height: 48px;
  background: var(--yz-table-header) !important;
  color: #58708c;
  font-weight: 600;
}

:deep(.el-table td) {
  color: #475569;
}

:deep(.el-tag) {
  border-radius: 12px;
  padding: 4px 12px;
}
</style>
