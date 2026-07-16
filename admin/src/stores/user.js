import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login } from '../api/admin'
import router from '../router'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  // 从 localStorage 恢复 userInfo
  const savedUserInfo = localStorage.getItem('userInfo')
  const userInfo = ref(savedUserInfo ? JSON.parse(savedUserInfo) : null)

  // 登录
  async function userLogin(loginForm) {
    try {
      const res = await login(loginForm)
      token.value = res.token
      localStorage.setItem('token', res.token)
      // 保存完整的用户信息
      userInfo.value = res.user_info
      localStorage.setItem('userInfo', JSON.stringify(res.user_info))
      return res
    } catch (error) {
      throw error
    }
  }

  // 登出
  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    router.push('/login')
  }

  return {
    token,
    userInfo,
    userLogin,
    logout
  }
})
