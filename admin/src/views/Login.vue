<template>
  <div
    class="login-page"
    :class="{ 'login-page--photo': !!loginBgUrl }"
    :style="pageStyle"
  >
    <el-button
      class="login-theme-fab yz-no-burst"
      :icon="themeStore.isDark ? Sunny : Moon"
      text
      circle
      :aria-label="themeStore.isDark ? '切到浅色' : '切到暗色'"
      @click="themeStore.toggle()"
    />

    <div class="login-left">
      <div class="login-left__inner">
        <header class="login-brand">
          <img
            class="login-brand__logo"
            :src="`${publicBase}static/brand-logo.png`"
            alt="小柠檬网络验证"
            width="48"
            height="48"
          />
          <div>
            <h1 class="login-brand__name">小柠檬网络验证</h1>
            <p class="login-brand__sub">管理后台</p>
          </div>
        </header>
        <p class="login-intro">
          小柠檬网络验证围绕「卡密防伪造、防重放、全链路可审计」设计。后端集成 RSA（2048 位）、AES
          与 HMAC-SHA256 等能力，用于关键接口的签名、敏感信息保护与传输校验，降低被篡改、盗用与重放调用的风险。业务侧为每个应用分配
          AppID / App
          Secret，多租户数据隔离；卡密在生成、发放、激活与核销全程留痕。本管理端用于卡密、积分与接口的全生命周期管理、设备与行为审计，并可通过官方
          Python、JavaScript SDK 对接，支持 Docker 部署。MySQL 持久化、Redis 作缓存，管理接口基于
          FastAPI 提供。
        </p>
        <ul class="login-highlights">
          <li v-for="(h, i) in highlights" :key="i">
            <el-icon class="login-highlights__icon" :size="20"><component :is="h.icon" /></el-icon>
            <span>{{ h.text }}</span>
          </li>
        </ul>
      </div>
    </div>

    <div class="login-right">
      <div class="login-glass">
        <div class="login-mascot" :class="{ 'is-typing': loginForm.password.length > 0 }" aria-hidden="true">
          <img :src="`${publicBase}static/brand-logo.png`" alt="" width="56" height="56" />
        </div>
        <h2 class="login-glass__title">欢迎回来</h2>
        <p class="login-glass__desc">使用管理员账号登录</p>

        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="rules"
          label-position="top"
          class="login-form"
          @submit.prevent
        >
          <el-form-item label="账号" prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              size="large"
              clearable
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              size="large"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <div class="login-form__row">
            <el-checkbox v-model="rememberMe">记住我</el-checkbox>
            <el-button link type="primary" class="login-forgot" @click="onForgot">忘记密码？</el-button>
          </div>
          <el-button
            type="primary"
            :loading="loading"
            class="login-submit"
            @click="handleLogin"
          >
            登 录
          </el-button>
          
          <div class="login-no-account">
            <span>没有账号？</span>
            <el-button link type="primary" @click="showContactDialog">联系作者获取</el-button>
          </div>
        </el-form>
        
        <!-- SDK 特性展示 -->
        <div class="sdk-features">
          <div class="sdk-feature-item">
            <div class="sdk-icon python">🐍</div>
            <span>Python SDK</span>
          </div>
          <div class="sdk-feature-item">
            <div class="sdk-icon javascript">🌐</div>
            <span>JavaScript SDK</span>
          </div>
          <div class="sdk-feature-item">
            <div class="sdk-icon java">☕</div>
            <span>Java SDK</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 联系作者对话框 -->
    <el-dialog
      v-model="contactVisible"
      title="🎉 获取测试账号"
      width="500px"
      :close-on-click-modal="false"
    >
      <div class="contact-content">
        <p class="contact-intro">
          欢迎使用小柠檬网络验证管理系统！如需获取测试账号或有任何问题，请联系作者：
        </p>
        
        <div class="contact-cards">
          <div class="contact-card wechat">
            <div class="contact-card-icon">
              <el-icon :size="32"><ChatDotRound /></el-icon>
            </div>
            <div class="contact-card-info">
              <div class="contact-label">微信</div>
              <div class="contact-value">d18880848565</div>
            </div>
          </div>
          
          <div class="contact-card douyin">
            <div class="contact-card-icon">
              <el-icon :size="32"><VideoCamera /></el-icon>
            </div>
            <div class="contact-card-info">
              <div class="contact-label">抖音</div>
              <div class="contact-value">小柠檬spider</div>
            </div>
          </div>
        </div>
        
        <el-alert
          title="快速上手"
          type="success"
          :closable="false"
          style="margin-top: 15px"
        >
          <template #default>
            <ul style="margin: 0; padding-left: 20px">
              <li>✅ 提供 Python、JavaScript、Java 三种 SDK</li>
              <li>✅ 5 行代码即可快速集成</li>
              <li>✅ 完善的文档和示例</li>
              <li>✅ 专业技术支持</li>
            </ul>
          </template>
        </el-alert>
      </div>
      
      <template #footer>
        <el-button type="primary" @click="contactVisible = false">我知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  User,
  Lock,
  Key,
  Document,
  Monitor,
  Link,
  Setting,
  Moon,
  Sunny,
  View,
  ChatDotRound,
  VideoCamera
} from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { useThemeStore } from '../stores/theme'
import { aesEncryptForLogin } from '../utils/crypto'

const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

// 保存登录前的主题状态
let previousThemeState = null

const R_KEY = 'lemon-remember-username'
const R_FLAG = 'lemon-remember-me'

const loginFormRef = ref(null)
const loading = ref(false)
const rememberMe = ref(true)
const loginBgUrl = ref('')
const contactVisible = ref(false)

/** Vite 下只有 public/ 内资源会原样提供到根路径，请使用 public/static/login_bg.png */
const publicBase = import.meta.env.BASE_URL

const highlights = [
  { icon: Lock, text: '接口与敏感数据侧：RSA-2048、AES、HMAC-SHA256 等组合，防伪造与防重放' },
  { icon: Key, text: '卡密全生命周期：批量生成、发放、激活、冻结/吊销与状态追踪' },
  { icon: Setting, text: '多应用 AppID / App Secret 分租户隔离与审计' },
  { icon: Monitor, text: '设备侧上报、绑定，异常可观测' },
  { icon: View, text: '激活/验证/管理端操作可审计、可追溯' },
  { icon: Link, text: '官方 Python / JavaScript SDK，可 Docker 部署' }
]

const pageStyle = computed(() => {
  const isDark = themeStore.isDark
  if (loginBgUrl.value) {
    // 提亮度：减暗、必要时加轻暖色漂层，让插画更清晰
    const lift = 'linear-gradient(180deg, rgba(234,246,255,0.24) 0%, rgba(255,255,255,0) 40%)'
    const veil = isDark
      ? `linear-gradient(120deg, rgba(15,23,42,0.42) 0%, rgba(15,23,42,0.22) 50%, rgba(15,23,42,0.5) 100%)`
      : `linear-gradient(120deg, rgba(255,255,255,0.52) 0%, rgba(255,255,255,0.28) 50%, rgba(255,255,255,0.5) 100%)`
    return {
      backgroundImage: `${lift}, ${veil}, url(${loginBgUrl.value})`,
      backgroundSize: 'cover, cover, cover',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
      backgroundColor: isDark ? '#0f172a' : '#f1f5f9'
    }
  }
  return isDark
    ? {
        background: 'linear-gradient(165deg, #0f172a 0%, #172554 50%, #1e293b 100%)',
        backgroundColor: '#0f172a'
      }
    : {
        background: 'linear-gradient(165deg, #eaf6ff 0%, #f8fbff 45%, #dbeafe 100%)',
        backgroundColor: '#f8fafc'
      }
})

onMounted(() => {
  // 登录页面强制使用浅色主题
  previousThemeState = themeStore.isDark
  themeStore.setDark(false)
  
  const exts = ['png', 'jpg', 'jpeg', 'webp']
  let i = 0
  const tryLoad = () => {
    if (i >= exts.length) return
    const u = `${publicBase}static/login_bg.${exts[i]}`
    const img = new Image()
    img.onload = () => {
      loginBgUrl.value = u
    }
    img.onerror = () => {
      i += 1
      tryLoad()
    }
    img.src = u
  }
  tryLoad()

  const user = localStorage.getItem(R_KEY)
  const remembered = localStorage.getItem(R_FLAG) === '1'
  if (user && remembered) {
    loginForm.username = user
    rememberMe.value = true
  } else {
    rememberMe.value = false
  }
})

// 组件卸载时恢复主题
onUnmounted(() => {
  if (previousThemeState !== null) {
    themeStore.setDark(previousThemeState)
  }
})

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能小于6位', trigger: 'blur' }
  ]
}

function persistRemember() {
  if (rememberMe.value) {
    localStorage.setItem(R_KEY, loginForm.username)
    localStorage.setItem(R_FLAG, '1')
  } else {
    localStorage.removeItem(R_KEY)
    localStorage.setItem(R_FLAG, '0')
  }
}

watch(rememberMe, (v) => {
  if (!v) {
    localStorage.setItem(R_FLAG, '0')
  }
})

const handleLogin = async () => {
  if (!loginFormRef.value) {
    return
  }
  
  await loginFormRef.value.validate(async (valid) => {
    if (!valid) {
      ElMessage.warning('请检查输入信息')
      return
    }
    
    loading.value = true
    
    try {
      // 获取 AES 密钥
      let aesKey = null
      
      try {
        const response = await fetch('/api/v1/admin/login/public-key')
        if (response.ok) {
          const result = await response.json()
          aesKey = result.aes_key
        }
      } catch {
        // 兼容未启用登录加密密钥的旧部署。
      }
      
      let loginData
      if (aesKey) {
        // 使用纯 AES 加密
        const encrypted = aesEncryptForLogin({
          username: loginForm.username,
          password: loginForm.password
        }, aesKey)
        loginData = {
          ...encrypted,
          encrypted: true
        }
      } else {
        // 降级为明文传输
        loginData = {
          username: loginForm.username,
          password: loginForm.password,
          encrypted: false
        }
      }
      
      await userStore.userLogin(loginData)
      persistRemember()
      ElMessage.success('登录成功')
      router.push('/')
    } catch (e) {
      ElMessage.error(e.message || '登录失败，请检查用户名和密码')
    } finally {
      loading.value = false
    }
  })
}

const onForgot = () => {
  ElMessage.info('请联系系统管理员重置密码')
}

const showContactDialog = () => {
  contactVisible.value = true
}
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(300px, 2fr);
  align-items: stretch;
}

/* 深色主题 + 背景图：左栏亮字 */
html.dark .login-page--photo .login-brand__name,
html.dark .login-page--photo .login-intro,
html.dark .login-page--photo .login-highlights li span {
  color: rgba(248, 250, 252, 0.98);
}

html.dark .login-page--photo .login-brand__sub {
  color: #38bdf8;
  opacity: 0.95;
}

html.dark .login-page--photo .login-intro {
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
}

html.dark .login-page--photo .login-highlights li {
  background: rgba(0, 0, 0, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: rgba(248, 250, 252, 0.95);
  backdrop-filter: blur(6px);
}

html.dark .login-page--photo .login-highlights__icon {
  color: #38bdf8;
}

/* 浅色主题 + 背景图：高亮层已偏亮，左栏用深字更易读 */
html:not(.dark) .login-page--photo .login-brand__name,
html:not(.dark) .login-page--photo .login-intro,
html:not(.dark) .login-page--photo .login-highlights li span {
  color: #0f172a;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.4);
}

html:not(.dark) .login-page--photo .login-brand__sub {
  color: #1d4ed8;
  font-weight: 600;
}

html:not(.dark) .login-page--photo .login-intro {
  text-shadow: none;
  color: #334155;
  font-size: 13.5px;
}

html:not(.dark) .login-page--photo .login-highlights li {
  background: rgba(255, 255, 255, 0.58);
  border: 1px solid rgba(255, 255, 255, 0.75);
  color: #1e293b;
  backdrop-filter: blur(8px);
}

html:not(.dark) .login-page--photo .login-highlights__icon {
  color: #2f80ed;
}

.login-theme-fab {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 20;
  color: #2f80ed !important;
  background: rgba(15, 23, 42, 0.65) !important;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

html:not(.dark) .login-theme-fab {
  background: rgba(255, 255, 255, 0.9) !important;
  color: #1d4ed8 !important;
  border-color: rgba(0, 0, 0, 0.08) !important;
}

/* 左栏 */
.login-left {
  position: relative;
  padding: clamp(24px, 4vw, 48px);
  display: flex;
  align-items: center;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.06);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

html:not(.dark) .login-page--photo .login-left {
  background: rgba(255, 255, 255, 0.18);
  border-right: 1px solid rgba(255, 255, 255, 0.35);
}

.login-left__inner {
  position: relative;
  z-index: 1;
  max-width: 520px;
  width: 100%;
  margin: 0 auto;
  padding: clamp(8px, 1.5vh, 16px) 0;
}

html:not(.dark) .login-page:not(.login-page--photo) .login-left {
  background: linear-gradient(145deg, #eaf6ff 0%, #dbeafe 100%);
}
html:not(.dark) .login-page:not(.login-page--photo) .login-brand__name {
  color: #1f2937;
}
html:not(.dark) .login-page:not(.login-page--photo) .login-intro {
  color: #4b5563;
  text-shadow: none;
}
html:not(.dark) .login-page:not(.login-page--photo) .login-highlights li {
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(47, 128, 237, 0.12);
  color: #1f2937;
}
html:not(.dark) .login-page:not(.login-page--photo) .login-highlights__icon {
  color: #2f80ed;
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.login-brand__logo {
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  flex-shrink: 0;
}

.login-brand__name {
  font-size: clamp(22px, 2.2vw, 30px);
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: 0;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
}

.login-brand__sub {
  color: #38bdf8;
  font-size: 14px;
  margin-top: 4px;
  font-weight: 500;
}

.login-intro {
  line-height: 1.8;
  color: rgba(226, 232, 240, 0.92);
  font-size: 13.5px;
  margin-bottom: 28px;
  max-width: 52ch;
}

.login-highlights {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
}

@media (max-width: 1200px) {
  .login-highlights {
    grid-template-columns: 1fr;
  }
}

.login-highlights li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 12px;
  line-height: 1.5;
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.login-highlights li:hover {
  transform: translateY(-1px);
}

.login-highlights__icon {
  color: #2f80ed;
  flex-shrink: 0;
  margin-top: 1px;
}

/* 右栏：有背景图时不铺死白，让毛玻璃透底 */
.login-right {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px 20px 36px;
  position: relative;
  background: rgba(0, 0, 0, 0.04);
}

html:not(.dark) .login-page--photo .login-right {
  background: rgba(255, 255, 255, 0.06);
}

html:not(.dark) .login-page:not(.login-page--photo) .login-right {
  background: #e8eef5;
}

.login-glass {
  width: 100%;
  max-width: 400px;
  padding: 32px 28px 36px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(20px) saturate(1.15);
  -webkit-backdrop-filter: blur(20px) saturate(1.15);
  animation: glass-in 0.2s ease-out;
}

html.dark .login-page--photo .login-glass {
  background: rgba(15, 23, 42, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.16);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
}

/* 浅色主题：磨砂半透明，避免整块实白 */
html:not(.dark) .login-glass {
  background: rgba(255, 255, 255, 0.38);
  border: 1px solid rgba(255, 255, 255, 0.72);
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.12);
  backdrop-filter: blur(22px) saturate(1.2);
  -webkit-backdrop-filter: blur(22px) saturate(1.2);
}

@keyframes glass-in {
  from {
    opacity: 0.85;
    transform: translateY(8px) scale(0.99);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.login-mascot {
  width: 70px;
  height: 70px;
  margin: 0 auto 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.15), rgba(255, 237, 213, 0.08));
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

html:not(.dark) .login-mascot {
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.85), rgba(255, 237, 213, 0.6));
  border: 1px solid rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(6px);
}

html:not(.dark) .login-page--photo .login-mascot {
  background: rgba(255, 255, 255, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
}

.login-mascot.is-typing {
  transform: scale(1.04) rotate(-2deg);
}

.login-mascot.is-typing img {
  filter: drop-shadow(0 4px 8px rgba(249, 115, 22, 0.4));
}

.login-glass__title {
  text-align: center;
  font-size: 20px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.login-glass__desc {
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 20px;
}

.login-form :deep(.el-form-item__label) {
  font-weight: 600;
}

.login-form__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: -4px 0 16px;
  font-size: 14px;
}

.login-forgot {
  padding: 0;
}

.login-submit {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 12px;
}

.login-no-account {
  text-align: center;
  margin-top: 16px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

/* SDK 特性展示 */
.sdk-features {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

html:not(.dark) .sdk-features {
  border-top-color: rgba(0, 0, 0, 0.08);
}

.sdk-feature-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  transition: transform 0.3s;
}

.sdk-feature-item:hover {
  transform: translateY(-3px);
}

.sdk-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  font-size: 24px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
}

html:not(.dark) .sdk-icon {
  background: rgba(255, 255, 255, 0.5);
}

.sdk-icon.python {
  background: linear-gradient(135deg, #3776ab20, #ffd43b20);
}

.sdk-icon.javascript {
  background: linear-gradient(135deg, #f7df1e20, #f7df1e10);
}

.sdk-icon.java {
  background: linear-gradient(135deg, #00739620, #f8982020);
}

/* 联系对话框样式 */
.contact-content {
  padding: 10px 0;
}

.contact-intro {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
  margin-bottom: 20px;
}

.contact-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
}

.contact-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border: 1px solid #e4e7ed;
  transition: all 0.3s;
}

.contact-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.contact-card.wechat {
  background: linear-gradient(135deg, #07c16010 0%, #07c16005 100%);
  border-color: #07c16030;
}

.contact-card.douyin {
  background: linear-gradient(135deg, #fe2c5510 0%, #fe2c5505 100%);
  border-color: #fe2c5530;
}

.contact-card-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: white;
  color: #409eff;
}

.contact-card.wechat .contact-card-icon {
  color: #07c160;
}

.contact-card.douyin .contact-card-icon {
  color: #fe2c55;
}

.contact-card-info {
  flex: 1;
}

.contact-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.contact-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  font-family: 'Consolas', monospace;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
  }
  .login-left {
    padding-bottom: 0;
  }
  .login-right {
    padding-top: 0;
  }
}
</style>
