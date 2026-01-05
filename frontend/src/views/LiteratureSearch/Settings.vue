<template>
  <div class="literature-search-settings">
    <!-- 搜索表单 -->
    <div class="settings-section">
      <h3 class="section-title">搜索设置</h3>
      <form class="form" @submit.prevent="handleSearch">
        <div class="form-group">
          <label class="form-label">查询关键词</label>
          <input
            v-model="options.query"
            type="text"
            class="form-control"
            placeholder="例如：Large Language Models"
            required
          />
        </div>
        <div class="form-group">
          <label class="form-label">结果数量 (k)</label>
          <input
            v-model.number="options.k"
            type="number"
            class="form-control"
            min="1"
            max="50"
            placeholder="10"
          />
        </div>
        <div class="form-group">
          <label class="form-label">检索类型</label>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
              <input
                type="checkbox"
                v-model="options.use_vector"
                style="width: auto;"
              />
              <span>向量检索（语义检索）</span>
            </label>
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
              <input
                type="checkbox"
                v-model="options.use_fts"
                style="width: auto;"
              />
              <span>关键词检索</span>
            </label>
          </div>
        </div>
        <button
          type="submit"
          class="btn btn-primary"
          :disabled="loading || !canSearch"
        >
          <svg v-if="!loading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <path d="m21 21-4.35-4.35"></path>
          </svg>
          <span v-if="loading" class="spinner"></span>
          {{ loading ? '搜索中...' : '开始搜索' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import axios from 'axios'

const emit = defineEmits(['search'])

import { API_BASE_URL } from '../../config.js'

const loading = ref(false)

const options = reactive({
  query: '',
  k: 10,
  kinds: ['paper'],
  use_vector: true,
  use_fts: true,
  filters: {}
})

const canSearch = computed(() => {
  return options.query.trim().length > 0
})

const handleSearch = async () => {
  if (!canSearch.value) {
    return
  }
  
  loading.value = true
  
  try {
    // 调用后端API进行文献检索（使用 Indexing Service）
    const response = await axios.post(
      `${API_BASE_URL}/api/literature-search`,
      {
        query: options.query.trim(),
        k: options.k || 10,
        kinds: options.kinds || ['paper'],
        filters: options.filters || {},
        use_vector: options.use_vector !== false,
        use_fts: options.use_fts !== false
      }
    )
    
    // 将结果传递给父组件
    emit('search', {
      result: response.data,
      options: { ...options }
    })
  } catch (error) {
    console.error('文献检索失败:', error)
    alert(error.response?.data?.detail || error.message || '文献检索失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

defineExpose({
  options,
  loading,
  setLoading: (value) => { loading.value = value }
})
</script>

<style scoped>
.literature-search-settings {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  font-weight: 500;
  color: #475569;
}

.form-control {
  width: 100%;
  padding: 10px 12px;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  color: #1e293b;
  font-size: 14px;
  transition: all 0.3s ease;
  background: #ffffff;
  box-sizing: border-box;
}

.form-control:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  outline: none;
}

.form-control::placeholder {
  color: #94a3b8;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: none;
  width: 100%;
}

.btn-primary {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #ffffff;
  box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 12px -2px rgba(37, 99, 235, 0.4);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none !important;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #ffffff;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

