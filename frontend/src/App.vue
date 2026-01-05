<template>
  <div id="app">
    <!-- 登录页面独立显示，不显示布局 -->
    <router-view v-if="isLoginPage" />
    
    <!-- 主应用布局 -->
    <template v-else>
      <button class="mobile-menu-btn" @click="toggleSidebar" v-if="!sidebarOpen">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      </button>
      
      <div class="app-layout">
      <aside class="sidebar" :class="{ 'sidebar-open': sidebarOpen, 'sidebar-collapsed': sidebarCollapsed }">
        <div class="sidebar-header">
          <div class="logo">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="logo-text">ResearchGO</span>
          </div>
          <button class="sidebar-toggle" @click="toggleCollapse" type="button">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline v-if="!sidebarCollapsed" points="15 18 9 12 15 6"></polyline>
              <polyline v-else points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
          <button class="sidebar-close" @click="toggleSidebar">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        
        <nav class="sidebar-nav">
          <router-link to="/" class="sidebar-link" @click="closeSidebarOnMobile" :title="sidebarCollapsed ? '首页' : ''">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
            <span class="link-text">首页</span>
          </router-link>
          
          <router-link to="/daily-subscription/updates" class="sidebar-link" @click="closeSidebarOnMobile" :title="sidebarCollapsed ? '学术日报' : ''">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
            <span class="link-text">学术日报</span>
          </router-link>
          
          <router-link to="/literature-review" class="sidebar-link" @click="closeSidebarOnMobile" :title="sidebarCollapsed ? '文献综述' : ''">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span class="link-text">文献综述</span>
          </router-link>
          
          <router-link to="/literature-translation" class="sidebar-link" @click="closeSidebarOnMobile" :title="sidebarCollapsed ? '文献翻译' : ''">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
            </svg>
            <span class="link-text">文献翻译</span>
          </router-link>
          
          <router-link to="/literature-search" class="sidebar-link" @click="closeSidebarOnMobile" :title="sidebarCollapsed ? '文献检索' : ''">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
            </svg>
            <span class="link-text">文献检索</span>
          </router-link>
        </nav>
        
        <div class="sidebar-footer">
          <div class="user-info" @click="showUserMenu = !showUserMenu">
            <div class="user-avatar">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
            </div>
            <div class="user-details" v-if="!sidebarCollapsed">
              <div class="user-name">{{ user?.name || '用户' }}</div>
              <div class="user-email">{{ user?.email || 'user@example.com' }}</div>
            </div>
          </div>
          <div v-if="showUserMenu && !sidebarCollapsed" class="user-menu">
            <button class="user-menu-item" @click="handleLogout">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
              <span>退出登录</span>
            </button>
          </div>
        </div>
      </aside>
      
      <div class="sidebar-overlay" :class="{ 'overlay-open': sidebarOpen }" @click="toggleSidebar"></div>
      
      <!-- 左侧第二个边栏 - 订阅设置（仅在学术日报页面显示，始终展开） -->
      <aside 
        v-if="isDailySubscriptionActive"
        class="left-secondary-sidebar" 
        :class="{ 
          'left-secondary-sidebar-collapsed': sidebarCollapsed
        }"
        :style="{ left: sidebarCollapsed ? '80px' : '220px' }"
      >
        <div class="left-secondary-sidebar-header">
          <div class="left-secondary-sidebar-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M12 1v6m0 6v6M5.64 5.64l4.24 4.24m4.24 4.24l4.24 4.24M1 12h6m6 0h6M5.64 18.36l4.24-4.24m4.24-4.24l4.24-4.24"></path>
            </svg>
            <span>订阅设置</span>
          </div>
          <button class="create-subscription-btn" @click="openCreateDialog" type="button" title="创建新订阅">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>
        </div>
        <div class="left-secondary-sidebar-content">
          <Settings ref="settingsRef" />
        </div>
      </aside>

      <!-- 左侧第二个边栏 - 文献综述设置（仅在文献综述页面显示，始终展开） -->
      <aside 
        v-if="isLiteratureReviewActive"
        class="left-secondary-sidebar" 
        :class="{ 
          'left-secondary-sidebar-collapsed': sidebarCollapsed
        }"
        :style="{ left: sidebarCollapsed ? '80px' : '220px' }"
      >
        <div class="left-secondary-sidebar-header">
          <div class="left-secondary-sidebar-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
            <span>文献综述设置</span>
          </div>
        </div>
        <div class="left-secondary-sidebar-content">
          <LiteratureReviewSettings ref="literatureReviewSettingsRef" @generate="handleLiteratureReviewGenerate" />
        </div>
      </aside>

      <!-- 左侧第二个边栏 - 文献翻译设置（仅在文献翻译页面显示，始终展开） -->
      <aside 
        v-if="isLiteratureTranslationActive"
        class="left-secondary-sidebar" 
        :class="{ 
          'left-secondary-sidebar-collapsed': sidebarCollapsed
        }"
        :style="{ left: sidebarCollapsed ? '80px' : '220px' }"
      >
        <div class="left-secondary-sidebar-header">
          <div class="left-secondary-sidebar-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
            </svg>
            <span>翻译设置</span>
          </div>
        </div>
        <div class="left-secondary-sidebar-content">
          <LiteratureTranslationSettings ref="literatureTranslationSettingsRef" @translate="handleLiteratureTranslationTranslate" />
        </div>
      </aside>

      <!-- 左侧第二个边栏 - 文献检索设置（仅在文献检索页面显示，始终展开） -->
      <aside 
        v-if="isLiteratureSearchActive"
        class="left-secondary-sidebar" 
        :class="{ 
          'left-secondary-sidebar-collapsed': sidebarCollapsed
        }"
        :style="{ left: sidebarCollapsed ? '80px' : '220px' }"
      >
        <div class="left-secondary-sidebar-header">
          <div class="left-secondary-sidebar-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
            </svg>
            <span>检索设置</span>
          </div>
        </div>
        <div class="left-secondary-sidebar-content">
          <LiteratureSearchSettings ref="literatureSearchSettingsRef" @search="handleLiteratureSearch" />
        </div>
      </aside>
      
      <main class="main" :class="{ 
        'main-with-sidebar': sidebarOpen, 
        'main-collapsed': sidebarCollapsed, 
        'main-with-secondary-sidebar': isDailySubscriptionActive || isLiteratureReviewActive || isLiteratureTranslationActive || isLiteratureSearchActive
      }">
        <keep-alive>
          <router-view />
        </keep-alive>
      </main>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './composables/useAuth'
import { API_BASE_URL } from './config.js'
import Settings from './views/DailySubscription/Settings.vue'
import LiteratureReviewSettings from './views/LiteratureReview/Settings.vue'
import LiteratureTranslationSettings from './views/LiteratureTranslation/Settings.vue'
import LiteratureSearchSettings from './views/LiteratureSearch/Settings.vue'

const router = useRouter()
const { user, logout: authLogout } = useAuth()

const route = useRoute()
const sidebarOpen = ref(false)
const sidebarCollapsed = ref(false)
const showUserMenu = ref(false)
const settingsRef = ref(null)
const literatureReviewSettingsRef = ref(null)
const literatureTranslationSettingsRef = ref(null)
const literatureSearchSettingsRef = ref(null)

// 判断是否为登录页面
const isLoginPage = computed(() => route.path === '/login')

const isDailySubscriptionActive = computed(() => {
  return route.path.startsWith('/daily-subscription')
})

const isLiteratureReviewActive = computed(() => {
  return route.path.startsWith('/literature-review')
})

const isLiteratureTranslationActive = computed(() => {
  return route.path.startsWith('/literature-translation')
})

const isLiteratureSearchActive = computed(() => {
  return route.path.startsWith('/literature-search')
})

const literatureReviewResult = ref({
  review: '',
  knowledgeGraph: null,
  searchResults: null, // 搜索结果数据
  options: null
})

const literatureTranslationResult = ref({
  translation: '',
  originalText: '',
  options: null
})

const literatureSearchResult = ref({
  searchResults: null,
  options: null
})

// 提供给子组件
provide('literatureReviewResult', literatureReviewResult)
provide('literatureTranslationResult', literatureTranslationResult)
provide('literatureSearchResult', literatureSearchResult)

// 当进入学术日报、文献综述、文献翻译或文献检索页面时，自动折叠左侧侧栏
watch(() => route.path, (newPath, oldPath) => {
  if (newPath.startsWith('/daily-subscription') || newPath.startsWith('/literature-review') || newPath.startsWith('/literature-translation') || newPath.startsWith('/literature-search')) {
    sidebarCollapsed.value = true
  } else {
    // 当进入其他页面时，恢复侧边栏展开状态
    sidebarCollapsed.value = false
  }
  // 移除清理逻辑，保留数据以便页面切换时使用 keep-alive 缓存
}, { immediate: true })

const handleLiteratureTranslationTranslate = async (data) => {
  const { result, options } = data
  
  // 清除之前的结果
  literatureTranslationResult.value = {
    translation: '',
    originalText: '',
    options: null
  }

  try {
    // 处理后端返回的新格式
    // result 包含 text_translated 和 meta 字段
    const translatedText = result?.text_translated || ''
    
    // 更新结果
    literatureTranslationResult.value = {
      translation: translatedText,
      originalText: '',
      options: options || null
    }
  } catch (error) {
    console.error('处理翻译结果失败:', error)
    // 错误处理已在Settings组件中完成，这里只是记录日志
  }
}

const handleLiteratureReviewGenerate = async (data) => {
  const { result, options } = data
  
  // 清除之前的结果
  literatureReviewResult.value = {
    review: '',
    knowledgeGraph: null,
    searchResults: null,
    options: null
  }

  try {
    // 检查是否包含搜索结果（hits数据）
    if (result?.hits && Array.isArray(result.hits)) {
      // 如果有搜索结果，保存搜索结果数据
      literatureReviewResult.value.searchResults = {
        query: result.query || '',
        hits: result.hits || []
      }
    }
    
    // 从后端API返回的结果中提取报告内容
    const finalReport = result?.final_report || {}
    
    // 根据test_nexus_api.py中的格式，报告包含overview_md字段
    const reviewContent = finalReport.overview_md || finalReport.review || ''
    
    // 目前后端API可能不返回知识图谱数据，所以暂时设为null
    // 如果需要，可以后续添加知识图谱生成功能
    const knowledgeGraph = null

    // 更新结果
    literatureReviewResult.value = {
      review: reviewContent,
      knowledgeGraph: knowledgeGraph,
      searchResults: literatureReviewResult.value.searchResults,
      options: options
    }
  } catch (error) {
    console.error('处理文献综述结果失败:', error)
    // 错误处理已在Settings组件中完成，这里只是记录日志
  }
}

const handleLiteratureSearch = async (data) => {
  const { result, options } = data
  
  // 清除之前的结果
  literatureSearchResult.value = {
    searchResults: null,
    options: null
  }

  try {
    // 新的 API 直接返回结果对象，包含 query, hits, results 等字段
    // 直接使用 result 作为 searchResults
    literatureSearchResult.value = {
      searchResults: result || null,
      options: options
    }
  } catch (error) {
    console.error('处理文献检索结果失败:', error)
    // 错误处理已在Settings组件中完成，这里只是记录日志
  }
}

const openCreateDialog = () => {
  if (settingsRef.value) {
    settingsRef.value.openCreateDialog('journal')
  }
}

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const toggleCollapse = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const closeSidebarOnMobile = () => {
  if (window.innerWidth <= 1024) {
    sidebarOpen.value = false
  }
}

const handleResize = () => {
  if (window.innerWidth > 1024) {
    sidebarOpen.value = true
    // 在大屏幕上，如果侧边栏是打开的，保持折叠状态
  } else {
    sidebarOpen.value = false
    // 在小屏幕上，收起时自动展开侧边栏文本
    sidebarCollapsed.value = false
  }
}


const handleLogout = () => {
  authLogout()
  showUserMenu.value = false
  router.push('/login')
}

// 点击外部关闭用户菜单
const handleClickOutside = (event) => {
  if (!event.target.closest('.sidebar-footer')) {
    showUserMenu.value = false
  }
}

onMounted(() => {
  if (window.innerWidth > 1024) {
    sidebarOpen.value = true
  }
  // 如果当前在学术日报、文献综述、文献翻译或文献检索页面，折叠左侧栏
  if (route.path.startsWith('/daily-subscription') || route.path.startsWith('/literature-review') || route.path.startsWith('/literature-translation') || route.path.startsWith('/literature-search')) {
    sidebarCollapsed.value = true
  }
  window.addEventListener('resize', handleResize)
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  background-attachment: fixed;
}

.mobile-menu-btn {
  display: none;
  position: fixed;
  top: 20px;
  left: 20px;
  z-index: 300;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: none;
  color: #2563eb;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.mobile-menu-btn:hover {
  background: rgba(255, 255, 255, 1);
  transform: scale(1.05);
}

.app-layout {
  display: flex;
  flex: 1;
  position: relative;
}

.sidebar {
  width: 220px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 2px 0 20px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  z-index: 200;
  transition: width 0.3s ease, transform 0.3s ease;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-collapsed {
  width: 80px;
}

.sidebar-header {
  padding: 24px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 18px;
  font-weight: 600;
  color: #2563eb;
  flex: 1;
  min-width: 0;
}

.logo svg {
  color: #2563eb;
  flex-shrink: 0;
}

.logo-text {
  white-space: nowrap;
  opacity: 1;
  transition: opacity 0.3s ease;
}

.sidebar-collapsed .logo-text {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.05);
  color: #64748b;
  border: none;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
  margin-left: auto;
}

.sidebar-toggle:hover {
  background: rgba(0, 0, 0, 0.1);
}

.sidebar-collapsed .sidebar-toggle {
  margin-left: 0;
}

.sidebar-close {
  display: none;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.05);
  color: #64748b;
  border: none;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
  margin-left: 8px;
}

.sidebar-close:hover {
  background: rgba(0, 0, 0, 0.1);
}

.sidebar-nav {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.sidebar-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  color: #64748b;
  text-decoration: none;
  font-size: 15px;
  font-weight: 500;
  transition: all 0.3s ease;
  position: relative;
  justify-content: flex-start;
}

.sidebar-collapsed .sidebar-link {
  justify-content: center;
  padding: 12px;
}

.sidebar-link:hover {
  background: rgba(37, 99, 235, 0.08);
  color: #2563eb;
}

.sidebar-link.router-link-active {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.15) 0%, rgba(124, 58, 237, 0.15) 100%);
  color: #2563eb;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2);
}

.sidebar-link svg {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.link-text {
  white-space: nowrap;
  opacity: 1;
  transition: opacity 0.3s ease;
}

.sidebar-collapsed .link-text {
  opacity: 0;
  width: 0;
  overflow: hidden;
}


.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.5);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.8);
  transition: all 0.3s ease;
  cursor: pointer;
}

.user-info:hover {
  background: rgba(255, 255, 255, 1);
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  flex-shrink: 0;
}

.user-details {
  flex: 1;
  min-width: 0;
  opacity: 1;
  transition: opacity 0.3s ease;
}

.sidebar-collapsed .user-details {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 4px;
  line-height: 1.2;
}

.user-email {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-footer {
  position: relative;
}

.user-menu {
  position: absolute;
  bottom: 100%;
  left: 16px;
  right: 16px;
  margin-bottom: 8px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(0, 0, 0, 0.08);
  overflow: hidden;
  z-index: 10;
}

.user-menu-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: none;
  border: none;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  text-align: left;
}

.user-menu-item:hover {
  background: rgba(37, 99, 235, 0.08);
  color: #2563eb;
}

.user-menu-item svg {
  flex-shrink: 0;
}

.sidebar-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 190;
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

.overlay-open {
  opacity: 1;
  pointer-events: all;
}

.main {
  flex: 1;
  margin-left: 220px;
  max-width: calc(100% - 220px);
  padding: 48px 32px;
  transition: margin-left 0.3s ease, max-width 0.3s ease;
}

.main-with-sidebar {
  margin-left: 220px;
}

.main-collapsed {
  margin-left: 80px;
  max-width: calc(100% - 80px);
}

/* 订阅设置侧栏（始终展开） */
.main-with-secondary-sidebar {
  margin-left: 540px;
  max-width: calc(100% - 540px);
}

.main-collapsed.main-with-secondary-sidebar {
  margin-left: 400px;
  max-width: calc(100% - 400px);
}

/* 左侧第二个边栏 */
.left-secondary-sidebar {
  position: fixed;
  top: 0;
  width: 320px;
  height: 100vh;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 2px 0 20px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  z-index: 150;
  transition: left 0.3s ease;
  overflow-y: auto;
}

.left-secondary-sidebar-header {
  padding: 24px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(248, 250, 252, 0.5);
  position: sticky;
  top: 0;
  z-index: 10;
}

.create-subscription-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #ffffff;
  border: none;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(37, 99, 235, 0.3);
}

.create-subscription-btn:hover {
  background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
  transform: scale(1.1);
  box-shadow: 0 4px 8px rgba(37, 99, 235, 0.4);
}

.left-secondary-sidebar-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 18px;
  font-weight: 600;
  color: #2563eb;
}

.left-secondary-sidebar-title svg {
  color: #2563eb;
  flex-shrink: 0;
}


.left-secondary-sidebar-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}


@media (max-width: 1024px) {
  .mobile-menu-btn {
    display: flex;
  }
  
  .sidebar {
    transform: translateX(-100%);
    width: 240px;
  }
  
  .sidebar-open {
    transform: translateX(0);
  }

  .sidebar-collapsed {
    width: 240px;
  }
  
  .sidebar-close {
    display: flex;
  }
  
  .sidebar-overlay {
    display: block;
  }
  
  .main {
    margin-left: 0;
    max-width: 100%;
    padding: 32px 20px;
  }
  
  .main-with-sidebar {
    margin-left: 0;
  }

  .main-collapsed {
    margin-left: 0;
    max-width: 100%;
  }

  .main-with-secondary-sidebar {
    margin-left: 0;
    max-width: 100%;
  }

  .main-collapsed.main-with-secondary-sidebar {
    margin-left: 0;
    max-width: 100%;
  }

  .left-secondary-sidebar {
    left: 0 !important;
    width: 320px !important;
  }

}

@media (max-width: 768px) {
  .mobile-menu-btn {
    top: 16px;
    left: 16px;
    width: 44px;
    height: 44px;
  }
  
  .sidebar {
    width: 220px;
  }
  
  .logo span {
    font-size: 16px;
  }
  
  .user-details {
    display: block;
  }
  
  .user-name {
    font-size: 13px;
  }
  
  .user-email {
    font-size: 11px;
  }

  .left-secondary-sidebar {
    width: 280px;
  }

}
</style>
