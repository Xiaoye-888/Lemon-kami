<template>
  <div class="account-page">
    <div class="page-toolbar">
      <div>
        <h2>修改密码</h2>
        <p>请先验证原密码，再设置新的登录密码</p>
      </div>
      <el-button :loading="loading" @click="loadProfile">刷新</el-button>
    </div>

    <section class="account-shell">
      <el-card shadow="never" class="panel password-panel">
        <template #header>
          <div class="panel-header">
            <span>修改密码</span>
            <el-tag effect="plain">{{ roleLabel }}</el-tag>
          </div>
        </template>

        <el-alert
          title="修改密码需要输入原密码和新密码，提交后请重新使用新密码登录。"
          type="info"
          :closable="false"
          show-icon
        />

        <el-form ref="formRef" :model="form" :rules="rules" label-width="96px" class="password-form">
          <el-form-item label="原密码" prop="old_password">
            <el-input v-model="form.old_password" type="password" show-password placeholder="请输入原密码" />
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input v-model="form.new_password" type="password" show-password placeholder="请输入新密码" />
          </el-form-item>
          <el-form-item label="确认新密码" prop="confirm_password">
            <el-input v-model="form.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
          </el-form-item>
        </el-form>

        <div class="form-actions">
          <el-button :disabled="saving" @click="resetForm">重置</el-button>
          <el-button type="primary" :loading="saving" @click="savePassword">保存修改</el-button>
        </div>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getCurrentAccountProfile, updateCurrentAccountPassword } from '../api/account'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const accountRole = computed(() => (userStore.role === 'merchant' ? 'merchant' : 'admin'))
const roleLabel = computed(() => (accountRole.value === 'merchant' ? '发卡用户' : '管理员'))
const loading = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const newPasswordRule = (_, value, callback) => {
  const text = String(value || '')
  if (!text) {
    callback(new Error('请输入新密码'))
    return
  }
  if (text.length < 6) {
    callback(new Error('新密码长度不能少于 6 位'))
    return
  }
  callback()
}

const confirmRule = (_, value, callback) => {
  if (!String(value || '')) {
    callback(new Error('请再次输入新密码'))
    return
  }
  if (value !== form.new_password) {
    callback(new Error('两次输入的新密码不一致'))
    return
  }
  callback()
}

const rules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [{ validator: newPasswordRule, trigger: 'blur' }],
  confirm_password: [{ validator: confirmRule, trigger: 'blur' }]
}

async function loadProfile() {
  loading.value = true
  try {
    const res = await getCurrentAccountProfile(accountRole.value)
    if (res.data?.username && res.data.username !== userStore.userInfo?.username) {
      userStore.setUserInfo({ ...(userStore.userInfo || {}), ...res.data })
    }
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.old_password = ''
  form.new_password = ''
  form.confirm_password = ''
  formRef.value?.clearValidate?.()
}

async function savePassword() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await updateCurrentAccountPassword(accountRole.value, {
      old_password: form.old_password,
      new_password: form.new_password
    })
    ElMessage.success('密码已更新')
    resetForm()
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
  max-width: 640px;
  margin: 0 auto;
}

.password-panel {
  border-radius: 18px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.password-form {
  margin-top: 16px;
  max-width: 560px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

html.dark .page-toolbar h2 {
  color: #f8fafc;
}

html.dark .page-toolbar p {
  color: #cbd5e1;
}
</style>
