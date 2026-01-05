<template>
  <div class="literature-search">
    <!-- 搜索结果 -->
    <div class="card results-card" v-if="searchResults">
      <div class="results-header">
        <h2>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <path d="m21 21-4.35-4.35"></path>
          </svg>
          搜索结果
        </h2>
        <div class="results-info">
          <span v-if="searchResults && (searchResults.results || searchResults.hits)">
            共找到 {{ (searchResults.results || searchResults.hits || []).length }} 条结果
          </span>
          <button @click="downloadResults" class="btn btn-secondary" type="button" v-if="searchResults">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            下载结果
          </button>
        </div>
      </div>
      <div class="results-content">
        <div v-if="displayResults && displayResults.length > 0" class="results-list">
          <div 
            v-for="(result, index) in displayResults" 
            :key="index" 
            class="result-item"
          >
            <div class="result-header">
              <h3 class="result-title">{{ result.title || '无标题' }}</h3>
              <div class="result-header-right">
                <span v-if="result.score !== undefined" class="result-score">
                  相关度: {{ result.score.toFixed(3) }}
                </span>
                <span class="result-index">#{{ index + 1 }}</span>
              </div>
            </div>
            <div class="result-meta" v-if="result.authors || result.publication_date || result.doc_type || result.canonical_id">
              <span v-if="result.authors && result.authors.length > 0" class="meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
                {{ formatAuthors(result.authors) }}
              </span>
              <span v-if="result.publication_date || result.publication_year" class="meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                {{ result.publication_year || formatDate(result.publication_date) }}
              </span>
              <span v-if="result.doc_type" class="meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                </svg>
                {{ result.doc_type }}
              </span>
              <span v-if="result.page !== undefined" class="meta-item">
                页码: {{ result.page }}
              </span>
            </div>
            <div class="result-abstract" v-if="result.chunk_text || result.abstract">
              <p><strong>匹配片段：</strong>{{ result.chunk_text || result.abstract }}</p>
            </div>
            <div v-if="result.section_path" class="result-section">
              <small>章节: {{ result.section_path }}</small>
            </div>
            <div class="result-links" v-if="result.doc_id || result.canonical_id">
              <span v-if="result.canonical_id" class="result-id">
                ID: {{ result.canonical_id }}
              </span>
              <span v-if="result.doc_id" class="result-id">
                文档ID: {{ result.doc_id }}
              </span>
            </div>
          </div>
        </div>
        <div v-else class="empty-results">
          <p>未找到相关结果</p>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!searchResults" class="empty-state">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: #94a3b8; margin-bottom: 24px;">
        <circle cx="11" cy="11" r="8"></circle>
        <path d="m21 21-4.35-4.35"></path>
      </svg>
      <h3>开始文献检索</h3>
      <p>请在右侧侧边栏输入查询关键词并设置搜索选项，然后点击搜索按钮</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, onUnmounted, onActivated } from 'vue'

defineOptions({
  name: 'LiteratureSearch'
})

const literatureSearchResult = inject('literatureSearchResult', ref({ searchResults: null, options: null }))

const searchResults = ref(null)
const currentOptions = ref(null)

// 同步数据函数
const syncData = () => {
  if (literatureSearchResult.value) {
    searchResults.value = literatureSearchResult.value.searchResults || null
    currentOptions.value = literatureSearchResult.value.options || null
  } else {
    searchResults.value = null
    currentOptions.value = null
  }
}

// 计算要显示的结果列表（优先使用 results，否则使用 hits）
const displayResults = computed(() => {
  if (!searchResults.value) return []
  
  // 优先使用转换后的 results 格式
  if (searchResults.value.results && Array.isArray(searchResults.value.results)) {
    return searchResults.value.results
  }
  
  // 如果没有 results，尝试使用 hits 格式
  if (searchResults.value.hits && Array.isArray(searchResults.value.hits)) {
    // 转换 hits 为显示格式
    return searchResults.value.hits.map(hit => ({
      title: hit.doc?.title || '无标题',
      doc_type: hit.doc?.doc_type,
      doc_id: hit.doc?.doc_id,
      canonical_id: hit.doc?.canonical_id,
      chunk_text: hit.chunk?.text,
      page: hit.chunk?.page,
      section_path: hit.chunk?.section_path,
      score: hit.score,
      explain: hit.explain,
      authors: [],
      abstract: hit.chunk?.text || ''
    }))
  }
  
  return []
})

// 监听结果变化
const stopWatcher = watch(literatureSearchResult, (newResult) => {
  syncData()
}, { immediate: true, deep: true })

// 当组件被 keep-alive 激活时，同步数据
onActivated(() => {
  syncData()
})

onUnmounted(() => {
  stopWatcher()
})

const formatAuthors = (authors) => {
  if (!authors || !Array.isArray(authors)) return '未知作者'
  if (authors.length === 0) return '未知作者'
  if (authors.length === 1) return authors[0]
  if (authors.length <= 3) return authors.join(', ')
  return `${authors.slice(0, 3).join(', ')} 等`
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  // 尝试解析日期字符串，提取年份
  try {
    const date = new Date(dateStr)
    if (!isNaN(date.getTime())) {
      return date.getFullYear().toString()
    }
    // 如果直接是年份字符串
    if (/^\d{4}$/.test(dateStr)) {
      return dateStr
    }
    return dateStr
  } catch (e) {
    return dateStr
  }
}

const getPaperUrl = (result) => {
  // 优先使用 open_access 中的 URL
  if (result.open_access?.best_oa_location?.url_for_pdf) {
    return result.open_access.best_oa_location.url_for_pdf
  }
  if (result.open_access?.best_oa_location?.url) {
    return result.open_access.best_oa_location.url
  }
  if (result.open_access?.oa_url) {
    return result.open_access.oa_url
  }
  // 使用 locations 中的 URL
  if (result.locations && result.locations.length > 0) {
    return result.locations[0].url_for_pdf || result.locations[0].url
  }
  // 使用直接的 url 字段
  return result.url
}

const downloadResults = () => {
  if (!searchResults.value) return
  
  const data = {
    query: searchResults.value.query || currentOptions.value?.query || '文献检索',
    timestamp: new Date().toISOString(),
    results: displayResults.value,
    total: displayResults.value.length
  }
  
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `文献检索_${searchResults.value.query || currentOptions.value?.query || 'search'}_${new Date().getTime()}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

</script>

<style scoped>
.literature-search {
  max-width: 1200px;
  margin: 0 auto;
}

.results-card {
  background: #ffffff;
  margin-bottom: 24px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e2e8f0;
}

.results-header h2 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
  color: #0f172a;
}

.results-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.results-info span {
  font-size: 14px;
  color: #64748b;
}

.results-content {
  padding: 24px;
  background: #f8fafc;
  border-radius: 12px;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.result-item {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  transition: all 0.3s ease;
}

.result-item:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.result-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 12px;
}

.result-score {
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 8px;
  border-radius: 6px;
  font-weight: 500;
}

.result-title {
  flex: 1;
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
  line-height: 1.4;
}

.result-index {
  font-size: 12px;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 4px 8px;
  border-radius: 6px;
  font-weight: 500;
  margin-left: 12px;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #64748b;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-item svg {
  color: #94a3b8;
}

.result-abstract {
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.6;
  color: #475569;
}

.result-abstract p {
  margin: 0;
}

.result-section {
  margin-bottom: 8px;
  font-size: 12px;
  color: #94a3b8;
  font-style: italic;
}

.result-links {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.result-id {
  font-size: 12px;
  color: #64748b;
  font-family: monospace;
  background: #f1f5f9;
  padding: 4px 8px;
  border-radius: 4px;
}

.result-link {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #2563eb;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.result-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.result-doi {
  font-size: 12px;
  color: #64748b;
  font-family: monospace;
}

.empty-results {
  text-align: center;
  padding: 40px;
  color: #94a3b8;
}

.empty-results p {
  margin: 0;
  font-size: 15px;
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
  .results-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .result-header {
    flex-direction: column;
    gap: 8px;
  }

  .result-index {
    align-self: flex-start;
    margin-left: 0;
  }

  .result-meta {
    flex-direction: column;
    gap: 8px;
  }
}
</style>

