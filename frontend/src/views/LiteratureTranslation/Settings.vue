<template>
  <div class="literature-translation-settings">
    <!-- 文件上传区域 -->
    <div class="settings-section">
      <h3 class="section-title">上传论文文件</h3>
      <div class="upload-area" 
           @drop="handleDrop" 
           @dragover.prevent
           @dragenter.prevent="isDragover = true"
           @dragleave.prevent="isDragover = false"
           :class="{ 'dragover': isDragover }">
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg"
          @change="handleFileSelect"
          style="display: none"
        />
        <div class="upload-content">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
          <p class="upload-text">拖拽文件到此处或 <button type="button" class="link-btn" @click="triggerFileInput">点击选择</button></p>
          <p class="upload-hint">支持 PDF、DOC、DOCX、TXT、PNG、JPG、JPEG 等格式</p>
        </div>
      </div>

      <!-- 已上传文件 -->
      <div v-if="uploadedFile" class="file-item">
        <div class="file-info">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <div class="file-details">
            <span class="file-name">{{ uploadedFile.name }}</span>
            <span class="file-size">{{ formatFileSize(uploadedFile.size) }}</span>
          </div>
        </div>
        <button @click="removeFile" class="btn-remove" type="button" title="删除">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      
      <button
        @click="handleTranslate"
        class="btn btn-primary"
        :disabled="loading || !canTranslate"
        type="button"
      >
        <svg v-if="!loading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
        </svg>
        <span v-if="loading" class="spinner"></span>
        {{ loading ? '翻译中...' : '开始翻译' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['translate'])

import axios from 'axios'
import { API_BASE_URL } from '../../config.js'

const fileInput = ref(null)
const uploadedFile = ref(null)
const isDragover = ref(false)
const loading = ref(false)

const canTranslate = computed(() => {
  return uploadedFile.value !== null
})

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  if (files.length > 0) {
    uploadedFile.value = files[0]
  }
}

const handleDrop = (event) => {
  isDragover.value = false
  event.preventDefault()
  const files = Array.from(event.dataTransfer.files)
  if (files.length > 0) {
    uploadedFile.value = files[0]
  }
}

const removeFile = () => {
  uploadedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const handleTranslate = async () => {
  if (!canTranslate.value) {
    return
  }
  
  loading.value = true
  
  try {
    // 创建 FormData
    const formData = new FormData()
    formData.append('file', uploadedFile.value)
    formData.append('target_lang', 'zh') // 默认使用中文
    
    // 调用后端 API
    const response = await axios.post(
      `${API_BASE_URL}/api/translate-paper`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        timeout: 300000 // 5分钟超时（翻译可能需要较长时间）
      }
    )
    
    // 将结果传递给父组件
    emit('translate', {
      result: response.data,
      options: {
        fileName: uploadedFile.value.name
      }
    })
  } catch (error) {
    console.error('翻译失败:', error)
    const errorMessage = error.response?.data?.error || error.message || '翻译失败，请稍后重试'
    alert(errorMessage)
  } finally {
    loading.value = false
  }
}

defineExpose({
  loading,
  setLoading: (value) => { loading.value = value }
})
</script>

<style scoped>
.literature-translation-settings {
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


.upload-area {
  border: 2px dashed #cbd5e1;
  border-radius: 12px;
  padding: 32px 16px;
  text-align: center;
  background: #f8fafc;
  transition: all 0.3s ease;
  cursor: pointer;
}

.upload-area:hover,
.upload-area.dragover {
  border-color: #2563eb;
  background: #eff6ff;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-content svg {
  color: #64748b;
  stroke-width: 1.5;
}

.upload-text {
  font-size: 14px;
  color: #475569;
  font-weight: 500;
}

.link-btn {
  background: none;
  border: none;
  color: #2563eb;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  font-size: inherit;
}

.link-btn:hover {
  color: #1d4ed8;
}

.upload-hint {
  font-size: 12px;
  color: #94a3b8;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.file-item:hover {
  border-color: #2563eb;
  box-shadow: 0 2px 4px rgba(37, 99, 235, 0.1);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.file-info svg {
  color: #2563eb;
  flex-shrink: 0;
}

.file-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.file-name {
  font-weight: 500;
  color: #1e293b;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 11px;
  color: #64748b;
}

.btn-remove {
  background: #fee2e2;
  color: #dc2626;
  border: none;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.btn-remove:hover {
  background: #dc2626;
  color: #ffffff;
}


.form {
  display: flex;
  flex-direction: column;
  gap: 0px;
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

.checkbox-label {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #2563eb;
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

select.form-control {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1L6 6L11 1' stroke='%23475569' stroke-width='2'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 36px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 20px;
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

