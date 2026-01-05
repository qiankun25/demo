<template>
  <div class="literature-review-settings">
    <!-- 论文列表 -->
    <div class="settings-section">
      <h3 class="section-title">上传论文</h3>
      <div class="paper-items">
        <div v-for="(item, index) in paperItems" :key="index" class="paper-item">
          <div class="paper-item-header">
            <span class="paper-item-number">论文 {{ index + 1 }}</span>
            <button 
              v-if="paperItems.length > 1"
              @click="removePaperItem(index)" 
              class="btn-remove-item" 
              type="button" 
              title="删除">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          
          <!-- 如果还未选择类型，显示选择按钮 -->
          <div v-if="!item.type" class="paper-item-actions">
            <button 
              @click="selectPaperType(index, 'file')" 
              class="btn-select-type" 
              type="button">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
              上传文件
            </button>
            <button 
              @click="selectPaperType(index, 'url')" 
              class="btn-select-type" 
              type="button">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
              </svg>
              输入URL
            </button>
          </div>
          
          <!-- 文件上传模式 -->
          <div v-else-if="item.type === 'file'" class="paper-item-content">
            <input
              :ref="el => setFileInputRef(index, el)"
              type="file"
              accept=".pdf,application/pdf"
              @change="(e) => handleFileSelectForItem(index, e)"
              style="display: none"
            />
            <div v-if="!item.file" class="file-select-area" @click="triggerFileInput(index)">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
              <span>点击选择文件</span>
              <span class="file-hint">仅支持 PDF 文件</span>
            </div>
            <div v-else class="file-selected">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
              </svg>
              <span class="file-name">{{ item.file.name }}</span>
              <span class="file-size">{{ formatFileSize(item.file.size) }}</span>
              <button @click="changeFileType(index)" class="btn-change-type" type="button">更换</button>
            </div>
          </div>
          
          <!-- URL输入模式 -->
          <div v-else-if="item.type === 'url'" class="paper-item-content">
            <div class="url-input-wrapper">
              <input
                v-model="item.url"
                type="url"
                class="form-control"
                placeholder="https://example.com/paper.pdf"
              />
              <button @click="changeFileType(index)" class="btn-change-type" type="button">更换</button>
            </div>
          </div>
        </div>
        
        <button 
          @click="addPaperItem" 
          class="btn-add-paper" 
          type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          添加论文
        </button>
      </div>
      
      <button
        @click="handleGenerate"
        class="btn btn-primary"
        :disabled="loading || !canGenerate"
        type="button"
      >
        <svg v-if="!loading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
        <span v-if="loading" class="spinner"></span>
        {{ loading ? '生成中...' : '生成综述' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import axios from 'axios'

const emit = defineEmits(['generate'])

import { API_BASE_URL, MINIO_UPLOAD_URL } from '../../config.js'

const loading = ref(false)
const fileInputRefs = ref({}) // 存储每个paper item的file input引用

// 论文列表，每条记录包含type ('file' 或 'url')，file对象，url字符串
const paperItems = ref([{
  type: null, // 'file' 或 'url' 或 null
  file: null,
  url: ''
}])

const options = reactive({
  domain: null,
  style: null
})

const canGenerate = computed(() => {
  // 至少有一条有效的论文记录
  return paperItems.value.some(item => {
    if (item.type === 'file') {
      return item.file !== null
    } else if (item.type === 'url') {
      return item.url && item.url.trim()
    }
    return false
  })
})

const setFileInputRef = (index, el) => {
  if (el) {
    fileInputRefs.value[index] = el
  }
}

const addPaperItem = () => {
  paperItems.value.push({
    type: null,
    file: null,
    url: ''
  })
}

const removePaperItem = (index) => {
  if (paperItems.value.length > 1) {
    paperItems.value.splice(index, 1)
    delete fileInputRefs.value[index]
    // 重新索引fileInputRefs
    const newRefs = {}
    Object.keys(fileInputRefs.value).forEach(key => {
      const numKey = parseInt(key)
      if (numKey < index) {
        newRefs[numKey] = fileInputRefs.value[key]
      } else if (numKey > index) {
        newRefs[numKey - 1] = fileInputRefs.value[key]
      }
    })
    fileInputRefs.value = newRefs
  }
}

const selectPaperType = (index, type) => {
  paperItems.value[index].type = type
  paperItems.value[index].file = null
  paperItems.value[index].url = ''
}

const changeFileType = (index) => {
  paperItems.value[index].type = null
  paperItems.value[index].file = null
  paperItems.value[index].url = ''
}

const triggerFileInput = (index) => {
  fileInputRefs.value[index]?.click()
}

const handleFileSelectForItem = (index, event) => {
  const file = event.target.files[0]
  if (file) {
    const ext = file.name.split('.').pop().toLowerCase()
    // MinIO 服务器只接受 PDF 文件
    if (ext === 'pdf' && file.type === 'application/pdf') {
      paperItems.value[index].file = file
    } else {
      alert('不支持的文件类型。仅支持 PDF 文件（.pdf 扩展名和 application/pdf MIME 类型）')
    }
  }
  // 清空input，以便可以重新选择同一个文件
  event.target.value = ''
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const handleGenerate = async () => {
  if (!canGenerate.value) {
    return
  }
  
  loading.value = true
  
  try {
    const papers = []
    
    // 处理每条论文记录
    for (const item of paperItems.value) {
      if (item.type === 'file' && item.file) {
        // 上传文件到 MinIO 服务器
        try {
          const formData = new FormData()
          formData.append('files', item.file)
          // 可选：设置过期时间（默认3600秒，范围60-604800秒）
          // formData.append('expires', '7200')
          
          const response = await axios.post(
            MINIO_UPLOAD_URL,
            formData,
            {
              headers: {
                'Content-Type': 'multipart/form-data'
              }
            }
          )
          
          // 打印文件上传返回结果
          console.log('========== 文件上传返回结果 ==========')
          console.log('文件名称:', item.file.name)
          console.log('文件大小:', item.file.size, 'bytes')
          console.log('完整响应:', response)
          console.log('响应数据:', response.data)
          console.log('响应状态码:', response.status)
          console.log('====================================')
          
          // 处理响应：检查是否有成功的结果
          if (response.data.results && response.data.results.length > 0) {
            const firstResult = response.data.results[0]
            console.log('第一个上传结果:', firstResult)
            if (firstResult.status === 'success' && firstResult.presigned_url) {
              console.log('获取到的 presigned_url:', firstResult.presigned_url)
              papers.push({
                pdf_url: firstResult.presigned_url,
                title: '',
                authors: []
              })
            } else {
              // 文件上传失败
              const errorMsg = firstResult.error_message || '文件上传失败'
              alert(`文件 ${item.file.name} 上传失败: ${errorMsg}`)
              throw new Error(errorMsg)
            }
          } else {
            alert(`文件 ${item.file.name} 上传失败: 服务器未返回结果`)
            throw new Error('上传响应格式错误')
          }
        } catch (uploadError) {
          console.error('文件上传错误:', uploadError)
          if (uploadError.response) {
            // 服务器返回了响应但状态码不是 2xx
            const status = uploadError.response.status
            const detail = uploadError.response.data?.detail || uploadError.response.data?.message || uploadError.message
            alert(`文件 ${item.file.name} 上传失败 (HTTP ${status}): ${detail}\n\n请检查 MinIO 服务器是否正常运行: ${MINIO_UPLOAD_URL}`)
          } else if (uploadError.request) {
            // 请求已发出但没有收到响应
            alert(`文件 ${item.file.name} 上传失败: 无法连接到 MinIO 服务器\n\n请检查服务器地址: ${MINIO_UPLOAD_URL}`)
          } else {
            // 其他错误
            alert(`文件 ${item.file.name} 上传失败: ${uploadError.message}`)
          }
          throw uploadError
        }
      } else if (item.type === 'url' && item.url && item.url.trim()) {
        // 使用URL
        console.log('使用URL模式，论文URL:', item.url.trim())
        papers.push({
          pdf_url: item.url.trim(),
          title: '',
          authors: []
        })
      }
    }
    
    if (papers.length === 0) {
      alert('请至少添加一条有效的论文记录')
      return
    }
    
    // 打印准备发送给后端的论文列表
    console.log('========== 准备发送给后端的论文列表 ==========')
    console.log('论文数量:', papers.length)
    console.log('论文列表:', papers)
    console.log('请求参数:', {
      papers: papers,
      domain: null,
      style: null
    })
    console.log('==========================================')
    
    // 调用后端API生成综述
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/literature-review`,
        {
          papers: papers,
          domain: null,
          style: null
        }
      )
      
      // 打印文献综述生成返回结果
      console.log('========== 文献综述生成返回结果 ==========')
      console.log('完整响应:', response)
      console.log('响应数据:', response.data)
      console.log('响应状态码:', response.status)
      console.log('响应头:', response.headers)
      if (response.data.trace_id) {
        console.log('任务追踪ID:', response.data.trace_id)
      }
      if (response.data.final_report) {
        console.log('最终报告:', response.data.final_report)
      }
      console.log('========================================')
      
      // 将结果传递给父组件
      emit('generate', {
        result: response.data,
        options: null
      })
    } catch (apiError) {
      console.error('调用后端API失败:', apiError)
      if (apiError.response) {
        // 服务器返回了响应但状态码不是 2xx
        const status = apiError.response.status
        const detail = apiError.response.data?.detail || apiError.response.data?.message || apiError.message
        alert(`生成综述失败 (HTTP ${status}): ${detail}\n\n请检查后端服务是否正常运行: ${API_BASE_URL}/api/literature-review`)
      } else if (apiError.request) {
        // 请求已发出但没有收到响应
        alert(`生成综述失败: 无法连接到后端服务器\n\n请检查服务器地址: ${API_BASE_URL}`)
      } else {
        // 其他错误
        alert(`生成综述失败: ${apiError.message}`)
      }
      throw apiError
    }
  } catch (error) {
    console.error('生成综述失败:', error)
    // 如果错误没有被上面的 catch 处理，说明是文件上传的错误，已经在上面处理过了
    if (!error.response && !error.request) {
      // 重新抛出以触发 loading.value = false
      throw error
    }
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
.literature-review-settings {
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

.paper-items {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.paper-item {
  background: #ffffff;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  transition: all 0.3s ease;
}

.paper-item:hover {
  border-color: #cbd5e1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.paper-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.paper-item-number {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
}

.btn-remove-item {
  background: #fee2e2;
  color: #dc2626;
  border: none;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-remove-item:hover {
  background: #dc2626;
  color: #ffffff;
}

.paper-item-actions {
  display: flex;
  gap: 12px;
}

.btn-select-type {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  border: 2px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-select-type:hover {
  border-color: #2563eb;
  background: #eff6ff;
  color: #2563eb;
}

.btn-select-type svg {
  color: inherit;
}

.paper-item-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-select-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  border: 2px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.3s ease;
}

.file-select-area:hover {
  border-color: #2563eb;
  background: #eff6ff;
}

.file-select-area svg {
  color: #64748b;
}

.file-select-area span {
  font-size: 14px;
  color: #475569;
  font-weight: 500;
}

.file-hint {
  font-size: 12px;
  color: #94a3b8;
  font-weight: normal;
}

.file-selected {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #f0fdf4;
  border: 1px solid #86efac;
  border-radius: 8px;
}

.file-selected svg {
  color: #16a34a;
  flex-shrink: 0;
}

.file-name {
  flex: 1;
  font-weight: 500;
  color: #1e293b;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: #64748b;
}

.url-input-wrapper {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.url-input-wrapper .form-control {
  flex: 1;
}

.btn-change-type {
  padding: 8px 16px;
  background: #ffffff;
  color: #64748b;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.btn-change-type:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #475569;
}

.btn-add-paper {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  border: 2px dashed #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-add-paper:hover {
  border-color: #2563eb;
  color: #2563eb;
  background: #eff6ff;
}

.btn-add-paper svg {
  color: inherit;
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

