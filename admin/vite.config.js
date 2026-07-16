import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [vue()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true
        }
      }
    },
    publicDir: 'public',
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src')
      }
    },
    // 配置静态资源入口和 vendor 分包
    build: {
      rolldownOptions: {
        input: {
          main: path.resolve(__dirname, 'index.html')
        },
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined
            const normalizedId = id.replace(/\\/g, '/')
            if (normalizedId.includes('/@element-plus/icons-vue/')) return 'vendor-element-icons'
            if (normalizedId.includes('/element-plus/theme-chalk/') || normalizedId.includes('/element-plus/dist/')) return 'vendor-element-style'
            if (normalizedId.includes('/element-plus/es/components/')) {
              if (/\/(table|table-column|table-v2|pagination|scrollbar|tree|tree-select|transfer|collapse|descriptions|empty|result|virtual-list)\//.test(normalizedId)) return 'vendor-element-data'
              if (/\/(form|form-item|input|input-number|select|option|option-group|button|button-group|switch|radio|radio-group|checkbox|checkbox-group|date-picker|time-picker|time-select|upload|cascader|color-picker|slider|rate)\//.test(normalizedId)) return 'vendor-element-form'
              if (/\/(dialog|drawer|message|message-box|notification|loading|popover|popper|tooltip|popconfirm|alert|badge|progress|skeleton|skeleton-item)\//.test(normalizedId)) return 'vendor-element-feedback'
              if (/\/(menu|menu-item|submenu|tabs|tab-pane|breadcrumb|breadcrumb-item|dropdown|dropdown-menu|dropdown-item|steps|step|page-header|backtop|anchor|anchor-link)\//.test(normalizedId)) return 'vendor-element-navigation'
              if (/\/(avatar|card|carousel|carousel-item|image|image-viewer|tag|timeline|timeline-item|calendar|statistic|countdown|text|watermark|divider|space|row|col|container|aside|header|main|footer)\//.test(normalizedId)) return 'vendor-element-display'
              return 'vendor-element-components'
            }
            if (normalizedId.includes('/element-plus/es/locale/')) return 'vendor-element-locale'
            if (normalizedId.includes('/element-plus/')) return 'vendor-element-core'
            if (normalizedId.includes('/vue-router/') || normalizedId.includes('/pinia/')) return 'vendor-router'
            if (normalizedId.includes('/vue/') || normalizedId.includes('/@vue/')) return 'vendor-vue'
            if (normalizedId.includes('/crypto-js/')) return 'vendor-crypto'
            return 'vendor'
          }
        }
      }
    }
  }
})
