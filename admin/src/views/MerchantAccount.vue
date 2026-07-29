<template>
  <div class="account-page">
    <div class="page-toolbar">
      <div>
        <h2>账号设置</h2>
        <p>查看并维护当前发卡用户的账号资料</p>
      </div>
      <el-button :loading="loading" @click="loadProfile">刷新</el-button>
    </div>

    <section class="account-grid">
      <el-card shadow="never" class="panel account-summary">
        <template #header>基本信息</template>
        <div class="profile-head">
          <el-avatar :size="56" class="profile-avatar">{{ avatarText }}</el-avatar>
          <div class="profile-title">
            <strong>{{ profile.username || '-' }}</strong>
            <el-tag :type="statusType" effect="plain">{{ statusText(profile.status) }}</el-tag>
          </div>
        </div>

        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户ID">{{ profile.id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="用户名">{{ profile.username || '-' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ profile.email || '-' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ profile.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatBeijingTime(profile.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="最近登录">{{ formatOptionalTime(profile.last_login) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <div class="side-stack">
        <el-card shadow="never" class="panel">
          <template #header>资料编辑</template>
          <el-form ref="formRef" :model="form" :rules="rules" label-width="88px" class="profile-form">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" maxlength="64" show-word-limit placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="form.email" maxlength="255" clearable placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item label="手机号" prop="phone">
              <el-input v-model="form.phone" maxlength="32" clearable placeholder="请输入手机号" />
            </el-form-item>

            <div class="form-actions">
              <el-button :disabled="loading || saving" @click="resetForm">重置</el-button>
              <el-button type="primary" :loading="saving" @click="saveProfile">保存修改</el-button>
            </div>
          </el-form>
        </el-card>

        <el-card shadow="never" class="panel security-panel">
          <template #header>安全设置</template>
          <el-alert
            title="密码和头像已单独放在安全设置里，这里只开放用户名、邮箱、手机号。"
            type="info"
            :closable="false"
            show-icon
          />
          <div class="permission-list">
            <div class="permission-row">
              <span>后台身份</span>
              <strong>发卡用户</strong>
            </div>
            <div class="permission-row">
              <span>发卡额度</span>
              <strong>由管理员授权和充值审核入账</strong>
            </div>
            <div class="permission-row">
              <span>应用权限</span>
              <strong>可管理自建应用，可使用管理员授权应用发卡</strong>
            </div>
          </div>
        </el-card>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getMerchantMe, updateMerchantMe } from '../api/merchant'
import { useUserStore } from '../stores/user'
import { formatBeijingTime } from '../utils/datetime'

const userStore = useUserStore()
const loading = ref(false)
const saving = ref(false)
const formRef = ref(null)
const profile = ref({ ...(userStore.userInfo || {}) })
const form = reactive({
  username: '',
  email: '',
  phone: ''
})

const avatarText = computed(() => String(profile.value.username || 'U').slice(0, 1).toUpperCase())
const statusType = computed(() => (Number(profile.value.status) === 0 ? 'danger' : 'success'))
const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

const usernameRule = (_, value, callback) => {
  const text = String(value || '').trim()
  if (!text) {
    callback(new Error('请输入用户名'))
    return
  }
  if (text.length < 3 || text.length > 64) {
    callback(new Error('用户名长度需为 3 到 64 位'))
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
}

function normalizeOptionalText(value) {
  const text = String(value ?? '').trim()
  return text || ''
}

async function loadProfile() {
  loading.value = true
  try {
    const res = await getMerchantMe()
    profile.value = res.data || {}
    syncFormFromProfile(profile.value)
    userStore.setUserInfo(profile.value)
  } finally {
    loading.value = false
  }
}

function resetForm() {
  syncFormFromProfile(profile.value)
}

async function saveProfile() {
  if (!formRef.value) {
    return
  }

  await formRef.value.validate(async (valid) => {
    if (!valid) {
      ElMessage.warning('请先检查账号资料')
      return
    }

    saving.value = true
    try {
      const payload = {
        username: normalizeOptionalText(form.username),
        email: normalizeOptionalText(form.email) || null,
        phone: normalizeOptionalText(form.phone) || null
      }
      const res = await updateMerchantMe(payload)
      profile.value = res.data || {}
      syncFormFromProfile(profile.value)
      userStore.setUserInfo(profile.value)
      ElMessage.success('账号资料已更新')
    } finally {
      saving.value = false
    }
  })
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
  font-size: 24px;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
}

.account-grid {
  display: grid;
  grid-template-columns: minmax(360px, 1.1fr) minmax(300px, 0.9fr);
  gap: 16px;
  align-items: start;
}

.side-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel {
  border-radius: 8px;
}

.profile-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
}

.profile-avatar {
  background: linear-gradient(135deg, #2f80ed, #38bdf8);
  font-weight: 700;
}

.profile-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.profile-title strong {
  color: #0f172a;
  font-size: 20px;
}

.profile-form {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 6px;
}

.security-panel :deep(.el-card__body) {
  padding-top: 14px;
}

.permission-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.permission-row {
  min-height: 54px;
  padding: 12px 14px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
}

.permission-row span {
  color: #64748b;
  flex-shrink: 0;
}

.permission-row strong {
  color: #0f172a;
  font-size: 14px;
  text-align: right;
}

@media (max-width: 980px) {
  .account-grid {
    grid-template-columns: 1fr;
  }

  .permission-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .permission-row strong {
    text-align: left;
  }
}
</style>
