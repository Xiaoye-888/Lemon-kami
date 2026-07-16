import { defineStore } from 'pinia'

const THEME_KEY = 'lemon-theme'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    isDark: false
  }),
  actions: {
    init() {
      const raw = localStorage.getItem(THEME_KEY)
      if (raw === 'dark' || raw === 'light') {
        this.isDark = raw === 'dark'
      } else {
        this.isDark = false
      }
      this.apply()
    },
    setDark(v) {
      this.isDark = v
      this.apply()
    },
    toggle() {
      this.setDark(!this.isDark)
    },
    apply() {
      if (this.isDark) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
      localStorage.setItem(THEME_KEY, this.isDark ? 'dark' : 'light')
    }
  }
})
