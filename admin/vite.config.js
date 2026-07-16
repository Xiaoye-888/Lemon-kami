import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [
      vue(),
      Components({
        dts: false,
        resolvers: [
          ElementPlusResolver({
            importStyle: 'css',
            directives: true
          })
        ]
      })
    ],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://localhost:8001',
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
            if (id.includes('element-plus') || id.includes('@element-plus')) return 'vendor-element'
            if (id.includes('vue-router') || id.includes('pinia')) return 'vendor-router'
            if (id.includes('vue')) return 'vendor-vue'
            if (id.includes('crypto-js')) return 'vendor-crypto'
            return 'vendor'
          }
        }
      }
    }
  }
})
