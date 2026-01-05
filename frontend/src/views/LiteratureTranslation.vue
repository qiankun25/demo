<template>
  <div class="literature-translation">
    <!-- 翻译结果 -->
    <div class="card translation-card" v-if="translation">
      <div class="translation-header">
        <h2>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
          </svg>
          翻译结果
        </h2>
        <div class="header-actions">
          <button @click="copyTranslation" class="btn btn-secondary" type="button" title="复制">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            复制
          </button>
          <button @click="downloadTranslation" class="btn btn-secondary" type="button" title="下载">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            下载
          </button>
        </div>
      </div>
      <div class="translation-content">
        <div class="translation-info" v-if="currentOptions?.fileName">
          <span class="file-name">{{ currentOptions.fileName }}</span>
        </div>
        <div class="translation-text" v-html="formatTranslation(translation)"></div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!translation" class="empty-state">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: #94a3b8; margin-bottom: 24px;">
        <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
      </svg>
      <h3>开始翻译文献</h3>
      <p>请在右侧侧边栏上传论文文件，然后点击翻译按钮</p>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, watch, onUnmounted, onActivated } from 'vue'

defineOptions({
  name: 'LiteratureTranslation'
})

const literatureTranslationResult = inject('literatureTranslationResult', ref({ translation: '', originalText: '', options: null }))

const translation = ref('')
const originalText = ref('')
const currentOptions = ref(null)

// 同步数据函数
const syncData = () => {
  if (literatureTranslationResult.value) {
    translation.value = literatureTranslationResult.value.translation || ''
    originalText.value = literatureTranslationResult.value.originalText || ''
    currentOptions.value = literatureTranslationResult.value.options || null
  } else {
    translation.value = ''
    originalText.value = ''
    currentOptions.value = null
  }
}

// 监听结果变化
const stopWatcher = watch(literatureTranslationResult, (newResult) => {
  syncData()
}, { immediate: true, deep: true })

// 当组件被 keep-alive 激活时，同步数据
onActivated(() => {
  syncData()
})

onUnmounted(() => {
  stopWatcher()
})

const formatTranslation = (text) => {
  if (!text) return ''
  return text
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
}

const copyTranslation = async () => {
  if (!translation.value) return
  try {
    await navigator.clipboard.writeText(translation.value.replace(/<[^>]*>/g, ''))
    // 可以添加一个提示
    alert('翻译内容已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
  }
}

const downloadTranslation = () => {
  if (!translation.value) return
  const blob = new Blob([translation.value.replace(/<[^>]*>/g, '')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const timestamp = new Date().getTime()
  a.download = `文献翻译_${currentOptions.value?.fileName || 'file'}_${timestamp}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.literature-translation {
  max-width: 1200px;
  margin: 0 auto;
}

.card {
  background: #ffffff;
  border-radius: 16px;
  padding: 32px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.translation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e2e8f0;
}

.translation-header h2 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
  color: #0f172a;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.translation-content {
  padding: 24px;
  background: #f8fafc;
  border-radius: 12px;
  font-size: 15px;
  line-height: 1.8;
  color: #1e293b;
}

.translation-info {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.file-name {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

.translation-text {
  white-space: pre-wrap;
}

.translation-text :deep(p) {
  margin-bottom: 16px;
}

.translation-text :deep(p:last-child) {
  margin-bottom: 0;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: none;
}

.btn-secondary {
  background: #ffffff;
  color: #475569;
  border: 2px solid #e2e8f0;
}

.btn-secondary:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.empty-state {
  text-align: center;
  padding: 80px 24px;
  color: #64748b;
}

.empty-state h3 {
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 12px 0;
}

.empty-state p {
  font-size: 15px;
  color: #94a3b8;
  margin: 0;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}

@media (max-width: 768px) {
  .translation-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .card {
    padding: 24px;
  }
}
</style>

