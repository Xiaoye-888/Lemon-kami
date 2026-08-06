<template>
  <div class="account-page">
    <div class="page-toolbar">
      <div>
        <h2>账号设置</h2>
        <p>查看并维护当前{{ roleLabel }}的账号资料</p>
      </div>
      <el-button :loading="loading" @click="loadProfile">刷新</el-button>
    </div>

    <section class="account-shell">
      <el-card shadow="never" class="panel account-summary">
        <template #header>
          <div class="panel-header">
            <span>基本信息</span>
            <el-button size="small" :icon="EditPen" :disabled="loading" @click="openEditDialog">
              编辑
            </el-button>
          </div>
        </template>

        <div class="profile-head">
          <el-avatar :size="72" :src="profileAvatarUrl" class="profile-avatar">
            {{ avatarText }}
          </el-avatar>
          <div class="profile-title">
            <strong>{{ profile.username || '-' }}</strong>
            <div class="profile-meta">
              <el-tag :type="statusType" effect="plain">{{ statusText(profile.status) }}</el-tag>
              <span class="profile-role">{{ roleLabel }}</span>
            </div>
          </div>
        </div>

        <el-descriptions :column="1" border class="profile-descriptions">
          <el-descriptions-item label="用户ID">{{ profile.id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="用户名">{{ profile.username || '-' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ profile.email || '-' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ profile.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="后台身份">{{ roleLabel }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatBeijingTime(profile.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="最近登录">{{ formatOptionalTime(profile.last_login) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </section>

    <el-dialog
      v-model="editDialogVisible"
      title="资料编辑"
      width="640px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px" class="profile-form">
        <el-form-item label="头像">
          <div class="avatar-editor">
            <el-avatar :size="72" :src="editAvatarPreview" class="avatar-editor__preview">
              {{ avatarText }}
            </el-avatar>
            <div class="avatar-editor__actions">
              <el-upload
                :show-file-list="false"
                :http-request="handleAvatarUpload"
                :before-upload="validateAvatarFile"
                accept="image/png,image/jpeg,image/jpg,image/webp"
              >
                <el-button :loading="avatarUploading" :icon="Picture">上传头像</el-button>
              </el-upload>
              <div class="avatar-editor__hint">支持 PNG、JPG、WEBP，最大 2MB</div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" maxlength="64" show-word-limit placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" maxlength="255" clearable placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" maxlength="32" clearable placeholder="请输入手机号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="loading || saving || avatarUploading" @click="resetForm">重置</el-button>
        <el-button :disabled="saving" @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveProfile">保存修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { EditPen, Picture } from '@element-plus/icons-vue'
import { getCurrentAccountProfile, updateCurrentAccountProfile, uploadCurrentAccountAvatar } from '../api/account'
import { useUserStore } from '../stores/user'
import { formatBeijingTime } from '../utils/datetime'

const userStore = useUserStore()
const accountRole = computed(() => (userStore.role === 'merchant' ? 'merchant' : 'admin'))
const roleLabel = computed(() => (accountRole.value === 'merchant' ? '发卡用户' : '管理员'))
const loading = ref(false)
const saving = ref(false)
const avatarUploading = ref(false)
const editDialogVisible = ref(false)
const formRef = ref(null)
const profile = ref({ ...(userStore.userInfo || {}) })
const form = reactive({
  username: '',
  email: '',
  phone: '',
  avatar_url: ''
})

const avatarText = computed(() => String(profile.value.username || 'U').slice(0, 1).toUpperCase())
const statusType = computed(() => (Number(profile.value.status) === 0 ? 'danger' : 'success'))
const profileAvatarUrl = computed(() => form.avatar_url || profile.value.avatar_url || '')
const editAvatarPreview = computed(() => form.avatar_url || profile.value.avatar_url || '')
const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

const usernameRule = (_, value, callback) => {
  const text = String(value || '').trim()
  if (!text) {
    callback(new Error('请输入用户名'))
    return
  }
  const minLength = accountRole.value === 'merchant' ? 2 : 3
  if (text.length < minLength || text.length > 64) {
    callback(new Error(`用户名长度需为 ${minLength} 到 64 位`))
    return
  }
  if (/\s/.test(text)) {
    callback(new Error('用户名不能包含空格'))
    return
  }
  callback()
}

const emailRule = (_, value, callback) => {
  const text = String(value || '').trim()
  if (!text) {
    callback()
    return
  }
  if (text.length > 255) {
    callback(new Error('邮箱长度不能超过 255 位'))
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) {
    callback(new Error('请输入有效邮箱'))
    return
  }
  callback()
}

const phoneRule = (_, value, callback) => {
  const text = String(value || '').trim()
  if (!text) {
    callback()
    return
  }
  if (text.length > 32) {
    callback(new Error('手机号长度不能超过 32 位'))
    return
  }
  if (!/^[0-9+\-\s()]{6,32}$/.test(text)) {
    callback(new Error('请输入有效手机号'))
    return
  }
  callback()
}

const rules = {
  username: [{ validator: usernameRule, trigger: 'blur' }],
  email: [{ validator: emailRule, trigger: ['blur', 'change'] }],
  phone: [{ validator: phoneRule, trigger: ['blur', 'change'] }]
}

function statusText(status) {
  return Number(status) === 0 ? '停用' : '正常'
}

function syncFormFromProfile(source) {
  form.username = String(source?.username || '')
  form.email = source?.email || ''
  form.phone = source?.phone || ''
  form.avatar_url = source?.avatar_url || ''
}

function openEditDialog() {
  syncFormFromProfile(profile.value)
  formRef.value?.clearValidate?.()
  editDialogVisible.value = true
}

function resetForm() {
  syncFormFromProfile(profile.value)
  formRef.value?.clearValidate?.()
}

function validateAvatarFile(file) {
  const allowedTypes = new Set(['image/png', 'image/jpeg', 'image/jpg', 'image/webp'])
  if (!allowedTypes.has(file.type)) {
    ElMessage.error('头像仅支持 PNG、JPG、WEBP')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('头像文件不能超过 2MB')
    return false
  }
  return true
}

async function handleAvatarUpload(options) {
  const rawFile = options.file
  if (!rawFile) return

  avatarUploading.value = true
  try {
    const res = await uploadCurrentAccountAvatar(accountRole.value, rawFile)
    profile.value = res.data || profile.value
    syncFormFromProfile(profile.value)
    userStore.setUserInfo(profile.value)
    ElMessage.success('头像已更新')
    options.onSuccess?.(res)
  } catch (error) {
    options.onError?.(error)
  } finally {
    avatarUploading.value = false
  }
}

async function loadProfile() {
  loading.value = true
  try {
    const res = await getCurrentAccountProfile(accountRole.value)
    profile.value = res.data || {}
    syncFormFromProfile(profile.value)
    userStore.setUserInfo(profile.value)
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  if (!formRef.value) {
    return
  }

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    ElMessage.warning('请先检查账号资料')
    return
  }

  saving.value = true
  try {
    const payload = {
      username: String(form.username || '').trim(),
      email: String(form.email || '').trim() || null,
      phone: String(form.phone || '').trim() || null,
      avatar_url: String(form.avatar_url || '').trim() || null
    }
    const res = await updateCurrentAccountProfile(accountRole.value, payload)
    profile.value = res.data || {}
    syncFormFromProfile(profile.value)
    userStore.setUserInfo(profile.value)
    editDialogVisible.value = false
    ElMessage.success('账号资料已更新')
  } finally {
    saving.value = false
  }
}

onMounted(loadProfile)
</script>

<style scoped>
.account-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
}

.account-shell {
  width: 100%;
  max-width: 1040px;
  margin: 0 auto;
}

.account-summary {
  width: 100%;
  border-radius: 18px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.profile-head {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 24px;
}

.profile-avatar {
  flex-shrink: 0;
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  color: #1d4ed8;
  font-weight: 800;
}

.profile-title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.profile-title strong {
  font-size: 30px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.15;
}

.profile-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.profile-role {
  color: #475569;
  font-size: 14px;
}

.profile-descriptions {
  width: 100%;
}

.profile-form {
  max-width: 560px;
}

.avatar-editor {
  display: flex;
  align-items: center;
  gap: 16px;
}

.avatar-editor__preview {
  flex-shrink: 0;
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  color: #1d4ed8;
  font-weight: 800;
}

.avatar-editor__actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.avatar-editor__hint {
  font-size: 12px;
  color: #64748b;
}

html.dark .page-toolbar h2,
html.dark .profile-title strong {
  color: #f8fafc;
}

html.dark .page-toolbar p,
html.dark .profile-role,
html.dark .avatar-editor__hint {
  color: #cbd5e1;
}
</style>
