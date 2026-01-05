import { ref, computed } from 'vue'
import axios from 'axios'
import { API_BASE_URL } from '../config.js'

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 认证状态
const isAuthenticated = ref(false)
const user = ref(null)

// 从localStorage读取认证状态
const loadAuthState = () => {
  const savedAuth = localStorage.getItem('auth')
  if (savedAuth) {
    try {
      const authData = JSON.parse(savedAuth)
      isAuthenticated.value = true
      user.value = authData.user
    } catch (e) {
      console.error('Failed to load auth state:', e)
      localStorage.removeItem('auth')
    }
  }
}

// 初始化时加载认证状态
loadAuthState()

export const useAuth = () => {
  // 登录函数
  const login = async (email, password, rememberMe = false) => {
    try {
      const response = await apiClient.post('/api/auth/login', {
        email: email,
        password: password,
        remember_me: rememberMe
      })
      
      const userData = {
        id: response.data.id,
        username: response.data.username,
        email: response.data.email
      }
      
      isAuthenticated.value = true
      user.value = userData
      
      // 保存到localStorage或sessionStorage
      const authData = {
        user: userData,
        rememberMe: rememberMe
      }
      
      if (rememberMe) {
        localStorage.setItem('auth', JSON.stringify(authData))
      } else {
        sessionStorage.setItem('auth', JSON.stringify(authData))
      }
      
      return userData
    } catch (error) {
      // 处理错误响应
      if (error.response && error.response.data && error.response.data.detail) {
        throw new Error(error.response.data.detail)
      }
      throw new Error(error.message || '登录失败，请检查您的邮箱和密码')
    }
  }

  // 注册函数
  const register = async (email, password, username) => {
    try {
      const response = await apiClient.post('/api/auth/register', {
        username: username,
        email: email,
        password: password
      })
      
      const userData = {
        id: response.data.id,
        username: response.data.username,
        email: response.data.email
      }
      
      return userData
    } catch (error) {
      // 处理错误响应
      if (error.response && error.response.data && error.response.data.detail) {
        throw new Error(error.response.data.detail)
      }
      throw new Error(error.message || '注册失败，请稍后重试')
    }
  }

  // 登出函数
  const logout = () => {
    isAuthenticated.value = false
    user.value = null
    localStorage.removeItem('auth')
    sessionStorage.removeItem('auth')
  }

  // 检查是否已登录
  const checkAuth = () => {
    const savedAuth = localStorage.getItem('auth') || sessionStorage.getItem('auth')
    if (savedAuth) {
      try {
        const authData = JSON.parse(savedAuth)
        isAuthenticated.value = true
        user.value = authData.user
        return true
      } catch (e) {
        console.error('Failed to parse auth state:', e)
        logout()
        return false
      }
    }
    return false
  }

  return {
    isAuthenticated: computed(() => isAuthenticated.value),
    user: computed(() => user.value),
    login,
    register,
    logout,
    checkAuth
  }
}

