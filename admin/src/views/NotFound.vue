<template>
  <div class="not-found">
    <div class="not-found__card">
      <img
        class="not-found__img"
        :src="`${publicBase}static/brand-logo.png`"
        width="80"
        height="80"
        alt=""
      />
      <h1 class="not-found__title">404</h1>
      <p class="not-found__text">小柠檬迷路了，这个页面不存在哦</p>
      <el-button type="primary" size="large" @click="goHome">回首页</el-button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const publicBase = import.meta.env.BASE_URL
const router = useRouter()
const goHome = () => router.push('/')
</script>

<style scoped>
.not-found {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--yz-surface, #f1f5f9);
  padding: 24px;
}
html.dark .not-found {
  background: #0f172a;
}
.not-found__card {
  text-align: center;
  padding: 40px 48px;
  border-radius: 20px;
  background: var(--el-bg-color, #fff);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08);
  max-width: 400px;
}
html.dark .not-found__card {
  background: #1e293b;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
}
.not-found__img {
  margin-bottom: 8px;
  border-radius: 20px;
  opacity: 0.9;
  animation: nf-b 0.8s ease-in-out infinite alternate;
}
@keyframes nf-b {
  from { transform: translateY(0); }
  to { transform: translateY(-6px); }
}
.not-found__title {
  font-size: 40px;
  font-weight: 800;
  color: #2f80ed;
  margin: 0 0 8px;
}
.not-found__text {
  color: var(--el-text-color-secondary, #6b7280);
  margin-bottom: 24px;
  line-height: 1.5;
}
</style>
