<template>
  <el-config-provider :locale="zhCn">
    <!--
      key：登录页/404 用 fullPath；其余主框架固定为 main-shell，
      避免在子路由间切换时整页 MainLayout（含侧栏）被重新挂载
    -->
    <router-view v-slot="{ Component, route }">
      <component
        :is="Component"
        :key="route.name === 'Login' || route.name === 'NotFound' ? route.fullPath : 'main-shell'"
      />
    </router-view>
  </el-config-provider>
</template>

<script setup>
import zhCn from 'element-plus/es/locale/lang/zh-cn'
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  min-height: 100vh;
}
</style>
