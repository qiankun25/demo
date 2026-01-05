import { ref } from 'vue'
import axios from 'axios'
import { useAuth } from './useAuth'
import { API_BASE_URL } from '../config.js'

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 类型映射：前端类型 -> 后端类型
const TYPE_MAPPING = {
  'journal': 'journal',
  'author': 'scholar',
  'keyword': 'keyword'
}

// 反向映射：后端类型 -> 前端类型
const TYPE_REVERSE_MAPPING = {
  'journal': 'journal',
  'scholar': 'author',
  'keyword': 'keyword'
}

export const useSubscriptions = () => {
  const { user } = useAuth()
  const subscriptions = ref([])
  const loading = ref(false)
  const error = ref(null)

  // 获取请求头（包含用户ID）
  const getHeaders = () => {
    if (!user.value || !user.value.id) {
      throw new Error('用户未登录')
    }
    return {
      'X-User-ID': user.value.id.toString()
    }
  }

  // 获取所有订阅
  const fetchSubscriptions = async () => {
    if (!user.value || !user.value.id) {
      throw new Error('用户未登录')
    }

    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get('/api/subscriptions', {
        headers: getHeaders()
      })
      subscriptions.value = response.data.map(sub => ({
        ...sub,
        // 将后端类型转换为前端类型
        frontendType: TYPE_REVERSE_MAPPING[sub.subscription_type] || sub.subscription_type
      }))
      return subscriptions.value
    } catch (err) {
      error.value = err.response?.data?.detail || err.message || '获取订阅失败'
      throw new Error(error.value)
    } finally {
      loading.value = false
    }
  }

  // 创建订阅
  const createSubscription = async (type, value) => {
    if (!user.value || !user.value.id) {
      throw new Error('用户未登录')
    }

    // 将前端类型转换为后端类型
    const backendType = TYPE_MAPPING[type]
    if (!backendType) {
      throw new Error(`无效的订阅类型: ${type}`)
    }

    loading.value = true
    error.value = null
    try {
      const response = await apiClient.post(
        '/api/subscriptions',
        {
          subscription_type: backendType,
          subscription_value: value.trim()
        },
        {
          headers: getHeaders()
        }
      )
      const newSub = {
        ...response.data,
        frontendType: type
      }
      subscriptions.value.push(newSub)
      return newSub
    } catch (err) {
      error.value = err.response?.data?.detail || err.message || '创建订阅失败'
      throw new Error(error.value)
    } finally {
      loading.value = false
    }
  }

  // 更新订阅
  const updateSubscription = async (subscriptionId, type, value) => {
    if (!user.value || !user.value.id) {
      throw new Error('用户未登录')
    }

    // 将前端类型转换为后端类型
    const backendType = TYPE_MAPPING[type]
    if (!backendType) {
      throw new Error(`无效的订阅类型: ${type}`)
    }

    loading.value = true
    error.value = null
    try {
      const response = await apiClient.put(
        `/api/subscriptions/${subscriptionId}`,
        {
          subscription_type: backendType,
          subscription_value: value.trim()
        },
        {
          headers: getHeaders()
        }
      )
      // 更新本地数据
      const index = subscriptions.value.findIndex(s => s.id === subscriptionId)
      if (index !== -1) {
        subscriptions.value[index] = {
          ...response.data,
          frontendType: type
        }
      }
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || err.message || '更新订阅失败'
      throw new Error(error.value)
    } finally {
      loading.value = false
    }
  }

  // 删除订阅
  const deleteSubscription = async (subscriptionId) => {
    if (!user.value || !user.value.id) {
      throw new Error('用户未登录')
    }

    loading.value = true
    error.value = null
    try {
      await apiClient.delete(`/api/subscriptions/${subscriptionId}`, {
        headers: getHeaders()
      })
      // 从本地数据中删除
      subscriptions.value = subscriptions.value.filter(s => s.id !== subscriptionId)
      return true
    } catch (err) {
      error.value = err.response?.data?.detail || err.message || '删除订阅失败'
      throw new Error(error.value)
    } finally {
      loading.value = false
    }
  }

  // 按类型筛选订阅
  const getSubscriptionsByType = (type) => {
    return subscriptions.value.filter(sub => sub.frontendType === type)
  }

  // 根据类型获取订阅的显示名称
  const getSubscriptionDisplayName = (subscription) => {
    return subscription.subscription_value
  }

  return {
    subscriptions,
    loading,
    error,
    fetchSubscriptions,
    createSubscription,
    updateSubscription,
    deleteSubscription,
    getSubscriptionsByType,
    getSubscriptionDisplayName
  }
}

