import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElLoading } from 'element-plus/es/components/loading/index.mjs'
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import './assets/styles/theme.css'
import router from './router'
import App from './App.vue'
import { useThemeStore } from './stores/theme'
import { initClickBurst } from './utils/clickBurst'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElLoading)

useThemeStore().init()
initClickBurst()
app.mount('#app')
