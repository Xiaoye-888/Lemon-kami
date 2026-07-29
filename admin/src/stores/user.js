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

  function setUserInfo(nextUserInfo) {
    const merged = { ...(nextUserInfo || {}) }
    if (!merged.role && role.value) {
      merged.role = role.value
    }
    userInfo.value = merged
    role.value = merged.role || ''
    localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
    localStorage.setItem('role', role.value)
  }

  async function userLogin(loginForm) {
    const res = await sharedLogin(loginForm)
    token.value = res.token
    role.value = res.role || res.user_info?.role || 'admin'
    setUserInfo({ ...(res.user_info || {}), role: role.value })
    localStorage.setItem('token', res.token)
    return { ...res, redirect: res.redirect || homePath.value }
  }

  async function userRegister(registerForm) {
    const res = await sharedRegister(registerForm)
    token.value = res.token
    role.value = res.role || res.user_info?.role || 'merchant'
    setUserInfo({ ...(res.user_info || {}), role: role.value })
    localStorage.setItem('token', res.token)
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
    setUserInfo,
    userLogin,
    userRegister,
    logout
  }
})
