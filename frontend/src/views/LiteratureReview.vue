<template>
  <div class="literature-review">
    <!-- 搜索结果列表 -->
    <div v-if="searchResults && searchResults.hits && searchResults.hits.length > 0" class="search-results-section">
      <div class="search-results-header">
        <h2>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <path d="m21 21-4.35-4.35"></path>
          </svg>
          搜索结果
        </h2>
        <span class="search-query">查询: {{ searchResults.query }}</span>
      </div>
      <div class="search-results-list">
        <div
          v-for="(hit, index) in transformedHits"
          :key="index"
          class="result-item"
        >
          <!-- 标题部分 -->
          <h2 class="article-title">{{ hit.title }}</h2>

          <!-- 作者部分 -->
          <div class="article-authors" v-if="hit.authors && hit.authors.length > 0">
            <span
              v-for="(author, authorIndex) in hit.authors"
              :key="authorIndex"
              class="author-name"
            >{{ author }}</span>
          </div>

          <!-- 发布信息 -->
          <div class="article-pub-info">
            <span class="pub-date" v-if="hit.year">{{ hit.year }}</span>
            <span class="pub-journal" v-if="hit.venue">{{ hit.venue }}</span>
            <span class="pub-journal" v-if="hit.source">{{ hit.source }}</span>
          </div>

          <!-- 链接和指标 -->
          <div class="article-engagement">
            <div v-if="hit.openAccess" class="engagement-item open-access">
              <span class="access-dot"></span>
              <span>Open Access</span>
            </div>
            <div v-if="hit.pdfUrl" class="engagement-item engagement-action">
              <a :href="hit.pdfUrl" target="_blank" class="paper-link">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
                <span>查看PDF</span>
              </a>
            </div>
            <div v-if="hit.doiUrl" class="engagement-item engagement-action">
              <a :href="hit.doiUrl" target="_blank" class="paper-link">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
                <span>DOI</span>
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 生成的文献综述 -->
    <div class="card review-card" v-if="review">
      <div class="review-header">
        <h2>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          生成的文献综述
        </h2>
        <button @click="downloadReview" class="btn btn-secondary" type="button">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
          </svg>
          下载
        </button>
      </div>
      <div class="review-content">
        <div v-html="formatReview(review)"></div>
      </div>
    </div>

    <!-- 知识图谱 -->
    <div class="card knowledge-graph-card" v-if="knowledgeGraph">
      <div class="graph-header">
        <h2>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
            <polyline points="2 17 12 22 22 17"></polyline>
            <polyline points="2 12 12 17 22 12"></polyline>
          </svg>
          知识图谱
        </h2>
        <button @click="downloadGraph" class="btn btn-secondary" type="button">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
          </svg>
          下载图谱
        </button>
      </div>
      <div class="graph-container">
        <svg ref="graphSvg" class="knowledge-graph" :width="graphWidth" :height="graphHeight">
          <!-- 连线 -->
          <g class="links">
            <line
              v-for="(link, index) in knowledgeGraph.links"
              :key="index"
              :x1="link.source.x"
              :y1="link.source.y"
              :x2="link.target.x"
              :y2="link.target.y"
              class="link"
            />
          </g>
          <!-- 节点 -->
          <g class="nodes">
            <g
              v-for="(node, index) in knowledgeGraph.nodes"
              :key="index"
              :transform="`translate(${node.x},${node.y})`"
              class="node-group"
            >
              <circle
                :r="node.radius || 30"
                :class="`node node-${node.type}`"
              />
              <text class="node-label" dy=".35em" :y="(node.radius || 30) + 20">
                {{ node.label }}
              </text>
            </g>
          </g>
        </svg>
      </div>
      <div class="graph-legend">
        <div class="legend-item">
          <span class="legend-color concept"></span>
          <span>概念</span>
        </div>
        <div class="legend-item">
          <span class="legend-color method"></span>
          <span>方法</span>
        </div>
        <div class="legend-item">
          <span class="legend-color application"></span>
          <span>应用</span>
        </div>
        <div class="legend-item">
          <span class="legend-color domain"></span>
          <span>领域</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!review && !knowledgeGraph && (!searchResults || !searchResults.hits || searchResults.hits.length === 0)" class="empty-state">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: #94a3b8; margin-bottom: 24px;">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
      </svg>
      <h3>开始生成文献综述</h3>
      <p>请在右侧侧边栏上传文献文件并设置生成选项，然后点击生成按钮</p>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, watch, onUnmounted, onActivated, computed } from 'vue'

defineOptions({
  name: 'LiteratureReview'
})

const graphSvg = ref(null)
const graphWidth = ref(800)
const graphHeight = ref(600)

const literatureReviewResult = inject('literatureReviewResult', ref({ review: '', knowledgeGraph: null, searchResults: null, options: null }))

const review = ref('')
const knowledgeGraph = ref(null)
const searchResults = ref(null)
const currentOptions = ref(null)

// 转换搜索结果数据
const transformedHits = computed(() => {
  if (!searchResults.value || !searchResults.value.hits || !Array.isArray(searchResults.value.hits)) {
    return []
  }
  
  return searchResults.value.hits.map(hit => {
    const doc = hit.doc || {}
    
    // 处理 extra 字段：可能是对象，也可能是 JSON 字符串（extra_json）
    let extra = {}
    if (doc.extra && typeof doc.extra === 'object') {
      extra = doc.extra
    } else if (doc.extra_json) {
      try {
        extra = JSON.parse(doc.extra_json)
      } catch (e) {
        console.warn('解析 extra_json 失败:', e)
        extra = {}
      }
    }
    
    // 解析 authors_json 如果存在
    let authors = []
    if (doc.authors_json) {
      try {
        authors = JSON.parse(doc.authors_json)
      } catch (e) {
        // 如果解析失败，使用空数组
        authors = doc.authors || []
      }
    } else if (doc.authors) {
      authors = doc.authors
    }
    
    // 获取PDF URL（优先使用 extra.pdf_url）
    const pdfUrl = extra.pdf_url || doc.pdf_url || null
    
    // 获取DOI URL（extra.doi 可能是完整的 URL）
    const doiUrl = extra.doi || null
    
    return {
      title: doc.title || '无标题',
      authors: authors,
      year: doc.year || null,
      venue: doc.venue || null,
      source: doc.source || null,
      openAccess: doc.open_access || false,
      pdfUrl: pdfUrl,
      doiUrl: doiUrl,
      score: hit.score || 0
    }
  })
})

// 同步数据函数
const syncData = () => {
  if (literatureReviewResult.value) {
    review.value = literatureReviewResult.value.review || ''
    knowledgeGraph.value = literatureReviewResult.value.knowledgeGraph || null
    searchResults.value = literatureReviewResult.value.searchResults || null
    currentOptions.value = literatureReviewResult.value.options || null
  } else {
    review.value = ''
    knowledgeGraph.value = null
    searchResults.value = null
    currentOptions.value = null
  }
}

// 监听结果变化
const stopWatcher = watch(literatureReviewResult, (newResult) => {
  syncData()
}, { immediate: true, deep: true })

// 当组件被 keep-alive 激活时，同步数据
onActivated(() => {
  syncData()
})

onUnmounted(() => {
  stopWatcher()
})

const formatReview = (text) => {
  return text
    .replace(/^# (.+)$/gm, '<h1 style="font-size: 28px; font-weight: 700; color: #0f172a; margin: 32px 0 16px 0; padding-bottom: 12px; border-bottom: 2px solid #e2e8f0;">$1</h1>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size: 22px; font-weight: 600; color: #0f172a; margin: 28px 0 12px 0; padding-bottom: 8px; border-bottom: 1px solid #e2e8f0;">$1</h2>')
    .replace(/^### (.+)$/gm, '<h3 style="font-size: 18px; font-weight: 600; color: #1e293b; margin: 24px 0 8px 0;">$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight: 600; color: #0f172a;">$1</strong>')
    .replace(/\n/g, '<br>')
}

const downloadReview = () => {
  const blob = new Blob([review.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `文献综述_${currentOptions.value?.theme || 'review'}_${new Date().getTime()}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

const downloadGraph = () => {
  if (!graphSvg.value) return
  
  const svgData = new XMLSerializer().serializeToString(graphSvg.value)
  const blob = new Blob([svgData], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `知识图谱_${currentOptions.value?.theme || 'graph'}_${new Date().getTime()}.svg`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

</script>

<style scoped>
.literature-review {
  max-width: 1000px;
  margin: 0 auto;
}

/* 搜索结果部分 */
.search-results-section {
  margin-bottom: 24px;
}

.search-results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 2px solid #e2e8f0;
}

.search-results-header h2 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
  color: #0f172a;
}

.search-query {
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
}

.search-results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-item {
  background: #ffffff;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.result-item:hover {
  border-color: #2563eb;
  box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.1);
  transform: translateY(-2px);
}

/* 标题样式 */
.article-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 6px;
  line-height: 1.4;
}

/* 作者样式 */
.article-authors {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.author-name {
  font-size: 13px;
  color: #0f172a;
  font-weight: 500;
}

/* 发布信息 */
.article-pub-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 13px;
  color: #64748b;
  flex-wrap: wrap;
}

.pub-date {
  color: #64748b;
}

.pub-journal {
  color: #0f172a;
  font-weight: 500;
}

/* 互动指标 */
.article-engagement {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
  flex-wrap: wrap;
}

.engagement-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #64748b;
}

.engagement-item svg {
  color: #64748b;
  flex-shrink: 0;
}

.open-access {
  color: #059669;
}

.open-access .access-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  display: inline-block;
  margin-right: 4px;
}

.engagement-action {
  cursor: pointer;
  transition: color 0.2s ease;
}

.engagement-action:hover {
  color: #2563eb;
}

.engagement-action:hover svg {
  color: #2563eb;
}

.paper-link {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #2563eb;
  text-decoration: none;
  font-size: 13px;
  transition: color 0.2s ease;
}

.paper-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.paper-link svg {
  flex-shrink: 0;
}

.review-card {
  background: #ffffff;
  margin-bottom: 24px;
}

.review-header,
.graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e2e8f0;
}

.review-header h2,
.graph-header h2 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
  color: #0f172a;
}

.review-content {
  padding: 24px;
  background: #f8fafc;
  border-radius: 12px;
  font-size: 15px;
  line-height: 1.8;
  color: #1e293b;
  white-space: pre-wrap;
}

.review-content :deep(p) {
  margin-bottom: 16px;
}

.review-content :deep(ul), .review-content :deep(ol) {
  margin-left: 24px;
  margin-bottom: 16px;
}

.review-content :deep(li) {
  margin-bottom: 8px;
}

.knowledge-graph-card {
  background: #ffffff;
}

.graph-container {
  background: #f8fafc;
  border-radius: 12px;
  padding: 24px;
  overflow: auto;
  border: 2px solid #e2e8f0;
}

.knowledge-graph {
  display: block;
  margin: 0 auto;
  background: #ffffff;
  border-radius: 8px;
}

.link {
  stroke: #cbd5e1;
  stroke-width: 2;
  stroke-opacity: 0.6;
}

.node-group {
  cursor: pointer;
}

.node {
  fill: #2563eb;
  stroke: #ffffff;
  stroke-width: 3;
  cursor: pointer;
  transition: all 0.3s ease;
}

.node:hover {
  stroke-width: 4;
  filter: brightness(1.1);
}

.node-concept {
  fill: #2563eb;
}

.node-method {
  fill: #7c3aed;
}

.node-application {
  fill: #10b981;
}

.node-domain {
  fill: #f59e0b;
}

.node-label {
  font-size: 12px;
  font-weight: 500;
  fill: #1e293b;
  text-anchor: middle;
  pointer-events: none;
}

.graph-legend {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #e2e8f0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #475569;
}

.legend-color {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.legend-color.concept {
  background: #2563eb;
}

.legend-color.method {
  background: #7c3aed;
}

.legend-color.application {
  background: #10b981;
}

.legend-color.domain {
  background: #f59e0b;
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
  .review-header,
  .graph-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .graph-container {
    padding: 16px;
  }

  .knowledge-graph {
    width: 100%;
    height: auto;
  }

  .graph-legend {
    flex-wrap: wrap;
    gap: 16px;
  }
}
</style>
