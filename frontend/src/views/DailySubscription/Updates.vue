<template>
  <div class="daily-updates">
    <!-- 刷新按钮 -->
    <div class="refresh-section">
      <button class="btn btn-secondary refresh-btn" @click="refreshUpdates(true)" :disabled="loading">
        <svg v-if="!loading" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"></polyline>
          <polyline points="1 20 1 14 7 14"></polyline>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
        </svg>
        <span v-if="loading" class="spinner-small"></span>
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <!-- 图表模块 -->
    <div class="chart-module">
      <div class="chart-title">统计信息</div>
      <div class="chart-content">
        <div class="stats-chart">
          <div ref="chartContainer" class="chart-container"></div>
        </div>
        <div class="stats-numbers">
          <div class="stat-item">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">论文数量</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ stats.sources }}</div>
            <div class="stat-label">期刊数量</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading && updates.length === 0" class="loading-state">
      <div class="spinner-large"></div>
      <p>加载中...</p>
    </div>

    <div v-else-if="updates.length === 0" class="empty-state">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
      </svg>
      <h3>暂无更新</h3>
      <p>今天还没有新的学术更新，请稍后再来查看</p>
    </div>

    <div v-else class="updates-list">
      <div
        v-for="update in updates"
        :key="update.id"
        class="update-item"
      >
        <!-- 标题部分 -->
        <h2 class="article-title">{{ update.title }}</h2>

        <!-- 作者部分 -->
        <div class="article-authors">
          <span
            v-for="(author, index) in update.authors"
            :key="index"
            class="author-name"
          >{{ author }}</span>
        </div>

        <!-- 发布信息 -->
        <div class="article-pub-info">
          <span class="pub-date">{{ update.publishDate }}</span>
          <span class="pub-journal">{{ update.journal }}</span>
          <span v-if="update.type" class="pub-type">{{ update.type }}</span>
        </div>

        <!-- 摘要 -->
        <div class="article-abstract" v-if="update.llmsummary">
          <span class="abstract-label">摘要:</span>
          <p class="abstract-text">{{ update.llmsummary }}</p>
        </div>

        <!-- 链接和指标 -->
        <div class="article-engagement">
          <div class="engagement-item">
            <span class="engagement-label">被引</span>
            <span class="engagement-value">{{ update.citations || 0 }}</span>
          </div>
          <div v-if="update.openAccess" class="engagement-item open-access">
            <span class="access-dot"></span>
            <span>Open Access</span>
          </div>
          <div v-if="update.pdfUrl" class="engagement-item engagement-action">
            <a :href="update.pdfUrl" target="_blank" class="paper-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
              <span>查看PDF</span>
            </a>
          </div>
          <div v-if="update.doiUrl" class="engagement-item engagement-action">
            <a :href="update.doiUrl" target="_blank" class="paper-link">
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
</template>

<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import { useSubscriptions } from '../../composables/useSubscriptions'

defineOptions({
  name: 'DailyUpdates'
})

import { API_BASE_URL } from '../../config.js'

const updates = ref([])
const loading = ref(false)
const chartContainer = ref(null)
let chartInstance = null
const limit = ref(5) // 默认返回数量

// 获取订阅相关功能
const { subscriptions, fetchSubscriptions, getSubscriptionsByType } = useSubscriptions()

const stats = computed(() => {
  const venues = new Set(updates.value.map(u => u.venue_display_name || u.journal).filter(Boolean))
  return {
    total: updates.value.length,
    sources: venues.size,
    categories: 0 // 后端数据中暂无分类字段
  }
})

const chartData = computed(() => {
  const colors = ['#2563eb', '#7c3aed', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#8b5cf6', '#ec4899']
  
  if (!updates.value || updates.value.length === 0) {
    return []
  }
  
  // 统计每个期刊的数量
  const journalCounts = {}
  updates.value.forEach(update => {
    const journal = update.venue_display_name || update.journal || '未知'
    journalCounts[journal] = (journalCounts[journal] || 0) + 1
  })
  
  // 转换为数组并按数量排序（最多显示前8个）
  const journalArray = Object.entries(journalCounts)
    .map(([name, count]) => ({ name, value: count }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)
    .map((item, index) => ({
      ...item,
      itemStyle: {
        color: colors[index % colors.length]
      }
    }))
  
  return journalArray
})

const initChart = () => {
  if (!chartContainer.value) return
  
  if (chartInstance) {
    chartInstance.dispose()
  }
  
  chartInstance = echarts.init(chartContainer.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance) return
  
  const data = chartData.value
  const isMobile = window.innerWidth <= 768
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      show: true,
      orient: isMobile ? 'horizontal' : 'vertical',
      left: isMobile ? 'center' : '50%',
      top: isMobile ? 'bottom' : 'middle',
      bottom: isMobile ? '10' : 'auto',
      itemGap: isMobile ? 10 : 12,
      itemWidth: 14,
      itemHeight: 14,
      textStyle: {
        fontSize: isMobile ? 14 : 16,
        color: '#475569',
        lineHeight: isMobile ? 20 : 22
      },
      formatter: function(name) {
        // 截断过长的期刊名称
        const maxLength = isMobile ? 18 : 25
        return name.length > maxLength ? name.substring(0, maxLength) + '...' : name
      }
    },
    series: [
      {
        name: '期刊分布',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        center: isMobile ? ['50%', '45%'] : ['30%', '50%'],
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold',
            formatter: '{b}\n{c}篇'
          }
        },
        labelLine: {
          show: false
        },
        data: data.length > 0 ? data : [{ name: '暂无数据', value: 0 }]
      }
    ]
  }
  
  chartInstance.setOption(option)
}

// 监听数据变化，更新图表
watch([chartData, stats], () => {
  if (chartContainer.value && !chartInstance) {
    initChart()
  } else if (chartInstance) {
    updateChart()
  }
}, { deep: true })

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

// 将后端数据转换为前端显示格式
const transformBackendData = (backendResults) => {
  if (!backendResults || !Array.isArray(backendResults)) {
    return []
  }
  
  return backendResults.map(item => {
    // 获取PDF URL
    const pdfUrl = item.pdf_url || 
                   item.best_oa_location?.pdf_url || 
                   item.primary_location?.pdf_url || 
                   item.best_oa_location?.landing_page_url ||
                   item.primary_location?.landing_page_url
    
    // 获取DOI链接
    const doiUrl = item.doi || null
    
    return {
      id: item.id,
      title: item.title || '无标题',
      authors: item.authors || [],
      publishDate: item.publication_date || item.publication_year?.toString() || '',
      journal: item.venue_display_name || '未知期刊',
      venue_display_name: item.venue_display_name,
      citations: item.cited_by_count || 0,
      openAccess: item.open_access?.is_oa || false,
      openAccessStatus: item.open_access?.oa_status || null,
      doi: item.doi,
      doiUrl: doiUrl,
      pdfUrl: pdfUrl,
      type: item.type || 'unknown',
      publication_year: item.publication_year,
      publication_date: item.publication_date,
      // llm_summary字段现在在search_results中
      llmsummary: item.llm_summary || item.llmsummary || null
    }
  })
}

// 从订阅设置构建请求参数
const buildRequestParams = () => {
  const keywordSubs = getSubscriptionsByType('keyword')
  const journalSubs = getSubscriptionsByType('journal')
  const authorSubs = getSubscriptionsByType('author')
  
  // 构建 query：合并所有关键词订阅
  let queryValue = 'Large Language Models' // 默认值
  if (keywordSubs.length > 0) {
    // 将所有关键词订阅的值合并，用逗号分隔
    queryValue = keywordSubs.map(sub => sub.subscription_value).join(', ')
  }
  
  // 构建 filters
  const filters = {}
  
  // 添加 last_n_days（固定为1，表示今天）
  filters.last_n_days = 1
  
  // 添加期刊过滤
  if (journalSubs.length > 0) {
    // 如果有多个期刊，可能需要数组，但根据API文档，可能只支持单个值
    // 这里先取第一个，或者可以合并
    if (journalSubs.length === 1) {
      filters.journal = journalSubs[0].subscription_value
    } else {
      // 多个期刊时，可能需要特殊处理，暂时取第一个
      filters.journal = journalSubs[0].subscription_value
      console.warn('多个期刊订阅，当前只使用第一个:', journalSubs[0].subscription_value)
    }
  }
  
  // 添加作者过滤
  if (authorSubs.length > 0) {
    if (authorSubs.length === 1) {
      filters.author = authorSubs[0].subscription_value
    } else {
      // 多个作者时，可能需要特殊处理，暂时取第一个
      filters.author = authorSubs[0].subscription_value
      console.warn('多个作者订阅，当前只使用第一个:', authorSubs[0].subscription_value)
    }
  }
  
  return {
    query: queryValue,
    limit: limit.value,
    filters: filters
  }
}

// 生成缓存key（基于订阅参数等）
const getCacheKey = () => {
  const params = buildRequestParams()
  const filtersStr = JSON.stringify(params.filters)
  const today = new Date().toISOString().split('T')[0]
  return `subscription_updates_${today}_${params.query}_${params.limit}_${filtersStr}`
}

// 从localStorage读取缓存
const loadFromCache = () => {
  try {
    const cacheKey = getCacheKey()
    const cached = localStorage.getItem(cacheKey)
    if (cached) {
      const cachedData = JSON.parse(cached)
      // 检查缓存是否过期（可选：可以设置缓存过期时间，比如24小时）
      const cacheTime = cachedData.timestamp || 0
      const now = Date.now()
      const cacheAge = now - cacheTime
      const maxAge = 24 * 60 * 60 * 1000 // 24小时
      
      if (cacheAge < maxAge) {
        console.log('从缓存加载数据:', cachedData.data.length, '条记录')
        return cachedData.data
      } else {
        console.log('缓存已过期，清除缓存')
        localStorage.removeItem(cacheKey)
      }
    }
  } catch (error) {
    console.error('读取缓存失败:', error)
  }
  return null
}

// 保存到localStorage
const saveToCache = (data) => {
  try {
    const cacheKey = getCacheKey()
    const cacheData = {
      timestamp: Date.now(),
      data: data
    }
    localStorage.setItem(cacheKey, JSON.stringify(cacheData))
    console.log('数据已保存到缓存:', cacheKey)
  } catch (error) {
    console.error('保存缓存失败:', error)
    // 如果存储空间不足，尝试清理旧缓存
    if (error.name === 'QuotaExceededError') {
      clearOldCache()
      try {
        const cacheKey = getCacheKey()
        const cacheData = {
          timestamp: Date.now(),
          data: data
        }
        localStorage.setItem(cacheKey, JSON.stringify(cacheData))
      } catch (retryError) {
        console.error('重试保存缓存仍然失败:', retryError)
      }
    }
  }
}

// 清理旧的缓存（保留最近7天的缓存）
const clearOldCache = () => {
  try {
    const keys = Object.keys(localStorage)
    const now = Date.now()
    const maxAge = 7 * 24 * 60 * 60 * 1000 // 7天
    
    keys.forEach(key => {
      if (key.startsWith('subscription_updates_')) {
        try {
          const cached = localStorage.getItem(key)
          if (cached) {
            const cachedData = JSON.parse(cached)
            const cacheAge = now - (cachedData.timestamp || 0)
            if (cacheAge > maxAge) {
              localStorage.removeItem(key)
              console.log('清理旧缓存:', key)
            }
          }
        } catch (error) {
          // 如果解析失败，直接删除
          localStorage.removeItem(key)
        }
      }
    })
  } catch (error) {
    console.error('清理缓存失败:', error)
  }
}

const refreshUpdates = async (forceRefresh = false) => {
  // 如果不是强制刷新，先尝试从缓存加载
  if (!forceRefresh) {
    const cachedData = loadFromCache()
    if (cachedData && cachedData.length > 0) {
      console.log('使用缓存数据')
      updates.value = cachedData
      loading.value = false
      return
    }
  }
  
  loading.value = true
  try {
    // 从订阅设置构建请求参数
    const requestParams = buildRequestParams()
    console.log('使用订阅参数构建请求:', requestParams)
    
    // 1. 提交任务，获取trace_id
    const submitResponse = await axios.post(
      `${API_BASE_URL}/api/morning-report`,
      {
        query: requestParams.query,
        limit: requestParams.limit,
        filters: requestParams.filters
      }
    )
    
    const traceId = submitResponse.data?.trace_id
    if (!traceId) {
      throw new Error('未获取到trace_id')
    }
    
    console.log('任务已提交，trace_id:', traceId)
    
    // 2. 轮询获取结果（每3秒查询一次，直到任务完成）
    const pollInterval = 3000 // 3秒
    
    let searchResults = null
    
    while (true) {
      try {
        const resultResponse = await axios.get(
          `${API_BASE_URL}/api/morning-report/${traceId}`
        )
        
        searchResults = resultResponse.data?.search_results
        if (searchResults) {
          console.log('获取到结果:', searchResults)
          break
        }
      } catch (error) {
        // 如果返回400，说明任务还未完成，继续等待
        if (error.response?.status === 400) {
          console.log('任务进行中，继续等待...')
          await new Promise(resolve => setTimeout(resolve, pollInterval))
          continue
        }
        // 其他错误直接抛出
        throw error
      }
    }
    
    // 处理结果
    if (searchResults && searchResults.results && Array.isArray(searchResults.results)) {
      // 转换数据格式
      console.log('开始转换数据，结果数量:', searchResults.results.length)
      const transformedData = transformBackendData(searchResults.results)
      updates.value = transformedData
      console.log('转换后的数据:', updates.value)
      
      // 保存到缓存
      saveToCache(transformedData)
    } else {
      console.warn('搜索结果格式不正确:', searchResults)
      updates.value = []
    }
  } catch (error) {
    console.error('获取更新失败:', error)
    alert(error.response?.data?.detail || error.message || '获取更新失败，请稍后重试')
    updates.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // 先获取订阅列表
  try {
    await fetchSubscriptions()
  } catch (err) {
    console.error('获取订阅列表失败:', err)
  }
  
  // 然后刷新更新
  refreshUpdates()
  nextTick(() => {
    initChart()
    // 窗口大小变化时自适应
    window.addEventListener('resize', handleResize)
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize()
    // 窗口大小变化时重新渲染图表以更新图例布局
    updateChart()
  }
}
</script>

<style scoped>
.daily-updates {
  max-width: 1000px;
}

/* 刷新按钮部分 */
.refresh-section {
  margin-bottom: 24px;
  display: flex;
  justify-content: flex-end;
}

.refresh-btn {
  padding: 8px 16px;
  white-space: nowrap;
}

.chart-content {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 24px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

/* 图表模块 */
.chart-module {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  margin-bottom: 24px;
  border: 2px solid #e2e8f0;
}

.chart-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 12px;
  text-align: center;
}

.stats-chart {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  flex: 1;
}

.chart-container {
  width: 100%;
  height: 300px;
}

.stats-numbers {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 120px;
  flex-shrink: 0;
}

.spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(37, 99, 235, 0.3);
  border-radius: 50%;
  border-top-color: #2563eb;
  animation: spin 0.6s linear infinite;
}

.loading-state {
  text-align: center;
  padding: 64px 0;
}

.spinner-large {
  width: 48px;
  height: 48px;
  border: 4px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}

.loading-state p {
  color: #64748b;
  font-size: 14px;
}

.empty-state {
  text-align: center;
  padding: 64px 0;
  color: #64748b;
}

.empty-state svg {
  color: #cbd5e1;
  margin-bottom: 16px;
}

.empty-state h3 {
  font-size: 20px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}

.empty-state p {
  font-size: 14px;
  color: #94a3b8;
}

.updates-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.update-item {
  background: #ffffff;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.update-item:hover {
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

.article-title-cn {
  font-size: 15px;
  font-weight: 500;
  color: #475569;
  margin-bottom: 10px;
  line-height: 1.5;
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

.more-authors {
  font-size: 13px;
  color: #64748b;
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

.pub-type {
  color: #64748b;
  text-transform: capitalize;
}

/* 摘要样式 */
.article-abstract {
  margin-bottom: 12px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 6px;
}

.abstract-label {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  margin-right: 6px;
}

.abstract-text {
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
  margin: 6px 0 0 0;
  display: inline;
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

.engagement-label {
  color: #64748b;
}

.engagement-value {
  color: #0f172a;
  font-weight: 500;
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

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .chart-module {
    padding: 12px;
  }
  
  .chart-content {
    flex-direction: column;
    gap: 16px;
  }
  
  .stats-numbers {
    flex-direction: row;
    justify-content: space-around;
    min-width: auto;
    width: 100%;
  }
  
  .stat-value {
    font-size: 20px;
  }
  
  .stat-label {
    font-size: 11px;
  }
  
  .chart-container {
    width: 100%;
    height: 250px;
  }
  
  .update-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
