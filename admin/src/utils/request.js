import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

// 从环境变量获取 API 配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const REQUEST_TIMEOUT = parseInt(import.meta.env.VITE_REQUEST_TIMEOUT) || 20000
const REQUEST_RETRIES = parseInt(import.meta.env.VITE_REQUEST_RETRIES) || 1
const REQUEST_RETRY_DELAY = parseInt(import.meta.env.VITE_REQUEST_RETRY_DELAY) || 350
const retryableMethods = new Set(['get', 'head', 'options'])
const retryableStatusCodes = new Set([502, 503, 504])

const waitForRetry = () => new Promise(resolve => setTimeout(resolve, REQUEST_RETRY_DELAY))

function isRetryableRequestError(error) {
  if (!error.config) {
    return false
  }

  const config = error.config
  const method = String(config.method || 'get').toLowerCase()

  if (error.code === 'ERR_CANCELED' || !retryableMethods.has(method)) {
    return false
  }

  const status = error.response?.status
  return !error.response || retryableStatusCodes.has(status)
}

const request = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    if (response.config.responseType === 'blob') {
      return response
    }

    const res = response.data
    
    if (!res.success) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    
    return res
  },
  async error => {
    const config = error.config || {}

    if (isRetryableRequestError(error)) {
      config.__retryCount = Number(config.__retryCount || 0)
      if (config.__retryCount < REQUEST_RETRIES) {
        config.__retryCount += 1
        await waitForRetry()
        return request(config)
      }
    }

    if (error.response) {
      const detail = error.response.data?.detail
      const serverDetail = typeof detail === 'string' ? detail : detail?.message
      switch (error.response.status) {
        case 401:
          ElMessage.error('未授权，请重新登录')
          localStorage.removeItem('token')
          router.push('/login')
          break
        case 403:
          ElMessage.error('拒绝访问')
          break
        case 404:
          ElMessage.error('请求资源不存在')
          break
        case 500:
          ElMessage.error(serverDetail || '服务器错误')
          break
        default:
          ElMessage.error(serverDetail || '请求失败')
      }
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请稍后重试')
    } else {
      ElMessage.error('网络错误，请检查网络连接')
    }
    return Promise.reject(error)
  }
)

export default request
