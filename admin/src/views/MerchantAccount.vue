<template>
  <div class="account-page">
    <div class="page-toolbar">
      <div>
        <h2>账号设置</h2>
        <p>查看当前发卡用户账号资料和登录状态</p>
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
          <el-descriptions-item label="创建时间">{{ profile.created_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="最近登录">{{ profile.last_login || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never" class="panel">
        <template #header>账号权限</template>
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
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getMerchantMe } from '../api/merchant'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const loading = ref(false)
const profile = ref({ ...(userStore.userInfo || {}) })

const avatarText = computed(() => String(profile.value.username || 'U').slice(0, 1).toUpperCase())
const statusType = computed(() => (Number(profile.value.status) === 0 ? 'danger' : 'success'))

function statusText(status) {
  return Number(status) === 0 ? '停用' : '正常'
}

async function loadProfile() {
  loading.value = true
  try {
    const res = await getMerchantMe()
    profile.value = res.data || {}
  } finally {
    loading.value = false
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

.permission-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
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
