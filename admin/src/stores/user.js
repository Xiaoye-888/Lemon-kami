import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { sharedLogin, sharedRegister } from '../api/auth'
import router from '../router'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const savedUserInfo = localStorage.getItem('userInfo')
  const userInfo = ref(savedUserInfo ? JSON.parse(savedUserInfo) : null)
  const role = ref(localStorage.getItem('role') || userInfo.value?.role || '')

  const homePath = computed(() => (role.value === 'merchant' ? '/merchant/dashboard' : '/admin/dashboard'))

  async function userLogin(loginForm) {
    const res = await sharedLogin(loginForm)
    token.value = res.token
    role.value = res.role || res.user_info?.role || 'admin'
    userInfo.value = { ...(res.user_info || {}), role: role.value }
    localStorage.setItem('token', res.token)
    localStorage.setItem('role', role.value)
    localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
    return { ...res, redirect: res.redirect || homePath.value }
  }

  async function userRegister(registerForm) {
    const res = await sharedRegister(registerForm)
    token.value = res.token
    role.value = res.role || res.user_info?.role || 'merchant'
    userInfo.value = { ...(res.user_info || {}), role: role.value }
    localStorage.setItem('token', res.token)
    localStorage.setItem('role', role.value)
    localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
    return { ...res, redirect: res.redirect || homePath.value }
  }

  function logout() {
    token.value = ''
    role.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('userInfo')
    router.push('/login')
  }

  return {
    token,
    role,
    userInfo,
    homePath,
    userLogin,
    userRegister,
    logout
  }
})
