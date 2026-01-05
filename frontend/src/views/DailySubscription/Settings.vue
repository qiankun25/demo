<template>
  <div class="subscription-settings">
    <!-- 订阅分类下拉菜单 -->
    <div class="subscription-menu">
      <!-- 期刊订阅 -->
      <div class="menu-item">
        <div 
          class="menu-header"
          @click="toggleMenu('journal')"
        >
          <div class="menu-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
            <span>期刊订阅</span>
            <span class="menu-count">({{ journalSubscriptions.length }})</span>
          </div>
          <svg 
            class="menu-arrow"
            :class="{ expanded: expandedMenus.journal }"
            width="16" 
            height="16" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            stroke-width="2"
          >
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
        <div class="menu-content" v-show="expandedMenus.journal">
          <div
            v-for="sub in journalSubscriptions"
            :key="sub.id"
            class="subscription-item"
          >
            <span class="subscription-name">{{ getSubscriptionDisplayName(sub) }}</span>
            <button @click="deleteSubscription('journal', sub.id)" class="btn-delete" type="button" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div v-if="journalSubscriptions.length === 0" class="empty-item">
            暂无订阅
          </div>
        </div>
      </div>

      <!-- 学者订阅 -->
      <div class="menu-item">
        <div 
          class="menu-header"
          @click="toggleMenu('author')"
        >
          <div class="menu-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
            <span>学者订阅</span>
            <span class="menu-count">({{ authorSubscriptions.length }})</span>
          </div>
          <svg 
            class="menu-arrow"
            :class="{ expanded: expandedMenus.author }"
            width="16" 
            height="16" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            stroke-width="2"
          >
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
        <div class="menu-content" v-show="expandedMenus.author">
          <div
            v-for="sub in authorSubscriptions"
            :key="sub.id"
            class="subscription-item"
          >
            <span class="subscription-name">{{ getSubscriptionDisplayName(sub) }}</span>
            <button @click="deleteSubscription('author', sub.id)" class="btn-delete" type="button" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div v-if="authorSubscriptions.length === 0" class="empty-item">
            暂无订阅
          </div>
        </div>
      </div>

      <!-- 关键词订阅 -->
      <div class="menu-item">
        <div 
          class="menu-header"
          @click="toggleMenu('keyword')"
        >
          <div class="menu-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path>
              <line x1="7" y1="7" x2="7.01" y2="7"></line>
            </svg>
            <span>关键词订阅</span>
            <span class="menu-count">({{ keywordSubscriptions.length }})</span>
          </div>
          <svg 
            class="menu-arrow"
            :class="{ expanded: expandedMenus.keyword }"
            width="16" 
            height="16" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            stroke-width="2"
          >
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
        <div class="menu-content" v-show="expandedMenus.keyword">
          <div
            v-for="sub in keywordSubscriptions"
            :key="sub.id"
            class="subscription-item"
          >
            <span class="subscription-name">{{ getSubscriptionDisplayName(sub) }}</span>
            <button @click="deleteSubscription('keyword', sub.id)" class="btn-delete" type="button" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div v-if="keywordSubscriptions.length === 0" class="empty-item">
            暂无订阅
          </div>
        </div>
      </div>
    </div>

    <!-- 订阅设置弹窗 - 使用 Teleport 渲染到 body，实现全屏弹窗 -->
    <Teleport to="body">
      <div v-if="showCreateDialog" class="dialog-overlay" @click="closeCreateDialog">
        <div class="dialog-content" @click.stop>
          <div class="dialog-header">
            <h3>订阅设置</h3>
            <button @click="closeCreateDialog" class="dialog-close" type="button">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          
          <div class="dialog-body">
            <!-- 标签页切换 -->
            <div class="tabs">
              <button
                @click="activeTab = 'journal'"
                :class="['tab-button', { active: activeTab === 'journal' }]"
                type="button"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                </svg>
                <span>期刊订阅</span>
              </button>
              <button
                @click="activeTab = 'author'"
                :class="['tab-button', { active: activeTab === 'author' }]"
                type="button"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
                <span>学者订阅</span>
              </button>
              <button
                @click="activeTab = 'keyword'"
                :class="['tab-button', { active: activeTab === 'keyword' }]"
                type="button"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path>
                  <line x1="7" y1="7" x2="7.01" y2="7"></line>
                </svg>
                <span>关键词订阅</span>
              </button>
            </div>

            <div class="tab-content">
              <!-- 左侧：订阅列表 -->
              <div class="subscriptions-list">
                <div class="list-header">
                  <h4>{{ getTabLabel(activeTab) }}</h4>
                  <span class="list-count">({{ getSubscriptionsCount(activeTab) }})</span>
                </div>
                <div class="list-items">
                  <div
                    v-for="sub in getSubscriptions(activeTab)"
                    :key="sub.id"
                    class="list-item"
                  >
                    <span class="item-name">{{ getSubscriptionDisplayName(sub) }}</span>
                    <button @click="deleteSubscription(activeTab, sub.id)" class="item-delete" type="button" title="删除">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  </div>
                  <div v-if="getSubscriptions(activeTab).length === 0" class="empty-list">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                    </svg>
                    <p>暂无订阅</p>
                  </div>
                </div>
              </div>

              <!-- 右侧：添加订阅表单 -->
              <div class="add-subscription-form">
                <h4>添加新订阅</h4>
                <form @submit.prevent="handleSubscribe" class="form">
                  <!-- 期刊订阅表单 -->
                  <template v-if="activeTab === 'journal'">
                    <div class="form-group">
                      <label class="form-label">期刊名称</label>
                      <input
                        v-model="form.name"
                        type="text"
                        class="form-control"
                        placeholder="例如：Nature, Science, Cell"
                        required
                      />
                    </div>
                  </template>

                  <!-- 学者订阅表单 -->
                  <template v-if="activeTab === 'author'">
                    <div class="form-group">
                      <label class="form-label">学者姓名</label>
                      <input
                        v-model="form.name"
                        type="text"
                        class="form-control"
                        placeholder="例如：Yann LeCun, Geoffrey Hinton"
                        required
                      />
                    </div>
                  </template>

                  <!-- 关键词订阅表单 -->
                  <template v-if="activeTab === 'keyword'">
                    <div class="form-group">
                      <label class="form-label">关键词（用逗号分隔）</label>
                      <input
                        v-model="form.keywords"
                        type="text"
                        class="form-control"
                        placeholder="例如：deep learning, neural networks, transformer"
                        required
                      />
                    </div>
                  </template>

                  <div class="form-actions">
                    <button type="submit" class="btn btn-primary" :disabled="loading">
                      <span v-if="loading" class="spinner"></span>
                      {{ loading ? '添加中...' : '添加订阅' }}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useSubscriptions } from '../../composables/useSubscriptions'

const {
  subscriptions,
  loading,
  error,
  fetchSubscriptions,
  createSubscription,
  deleteSubscription: deleteSubscriptionAPI,
  getSubscriptionsByType,
  getSubscriptionDisplayName
} = useSubscriptions()

const showCreateDialog = ref(false)
const activeTab = ref('journal')

const expandedMenus = reactive({
  journal: true,
  author: true,
  keyword: true
})

const form = reactive({
  name: '',
  keywords: ''
})

// 计算属性：按类型筛选的订阅
const journalSubscriptions = computed(() => getSubscriptionsByType('journal'))
const authorSubscriptions = computed(() => getSubscriptionsByType('author'))
const keywordSubscriptions = computed(() => getSubscriptionsByType('keyword'))

const toggleMenu = (menuType) => {
  expandedMenus[menuType] = !expandedMenus[menuType]
}

const getTabLabel = (tabId) => {
  const labels = {
    journal: '期刊订阅',
    author: '学者订阅',
    keyword: '关键词订阅'
  }
  return labels[tabId] || '订阅'
}

const getSubscriptions = (tabId) => {
  return getSubscriptionsByType(tabId)
}

const getSubscriptionsCount = (tabId) => {
  return getSubscriptions(tabId).length
}

const openCreateDialog = (tabType = 'journal') => {
  activeTab.value = tabType
  showCreateDialog.value = true
}

const closeCreateDialog = () => {
  showCreateDialog.value = false
  form.name = ''
  form.keywords = ''
}

const handleSubscribe = async () => {
  let value = ''
  if (activeTab.value === 'keyword') {
    if (!form.keywords || !form.keywords.trim()) {
      return
    }
    value = form.keywords.trim()
  } else {
    if (!form.name || !form.name.trim()) {
      return
    }
    value = form.name.trim()
  }

  try {
    await createSubscription(activeTab.value, value)
    // 清空表单但不关闭弹窗
    form.name = ''
    form.keywords = ''
  } catch (err) {
    console.error('创建订阅失败:', err)
    alert(err.message || '创建订阅失败，请重试')
  }
}

const deleteSubscription = async (type, id) => {
  if (confirm('确定要删除这个订阅吗？')) {
    try {
      await deleteSubscriptionAPI(id)
    } catch (err) {
      console.error('删除订阅失败:', err)
      alert(err.message || '删除订阅失败，请重试')
    }
  }
}

// 组件挂载时获取订阅列表
onMounted(async () => {
  try {
    await fetchSubscriptions()
  } catch (err) {
    console.error('获取订阅列表失败:', err)
  }
})

// 暴露方法给父组件
defineExpose({
  openCreateDialog,
  fetchSubscriptions
})
</script>

<style scoped>
.subscription-settings {
  max-width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.subscription-menu {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.menu-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  background: #ffffff;
}

.menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.3s ease;
}

.menu-header:hover {
  background: #f8fafc;
}

.menu-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  font-size: 15px;
  font-weight: 500;
  color: #1e293b;
}

.menu-title svg {
  color: #2563eb;
  flex-shrink: 0;
}

.menu-count {
  color: #64748b;
  font-weight: 400;
  font-size: 14px;
}

.menu-arrow {
  color: #64748b;
  transition: transform 0.3s ease;
  flex-shrink: 0;
}

.menu-arrow.expanded {
  transform: rotate(180deg);
}

.menu-content {
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.subscription-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #ffffff;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.subscription-item:hover {
  background: #f1f5f9;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.subscription-name {
  font-size: 14px;
  color: #1e293b;
  flex: 1;
  word-break: break-word;
  padding-right: 8px;
}

.btn-delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  background: transparent;
  color: #94a3b8;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
  opacity: 0;
}

.subscription-item:hover .btn-delete {
  opacity: 1;
}

.btn-delete:hover {
  background: #fee2e2;
  color: #dc2626;
}

.empty-item {
  padding: 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

/* 弹窗样式 */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.dialog-content {
  background: #ffffff;
  border-radius: 20px;
  width: 100%;
  max-width: 1000px;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 32px;
  border-bottom: 1px solid #e2e8f0;
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
  flex-shrink: 0;
}

.dialog-header h3 {
  font-size: 24px;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.dialog-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.05);
  color: #64748b;
  border: none;
  cursor: pointer;
  transition: all 0.3s ease;
}

.dialog-close:hover {
  background: rgba(0, 0, 0, 0.1);
  color: #1e293b;
}

.dialog-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 标签页样式 */
.tabs {
  display: flex;
  gap: 8px;
  padding: 20px 32px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  flex-shrink: 0;
}

.tab-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 10px;
  background: transparent;
  border: none;
  color: #64748b;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.tab-button:hover {
  background: rgba(37, 99, 235, 0.08);
  color: #2563eb;
}

.tab-button.active {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #ffffff;
  box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3);
}

.tab-button svg {
  flex-shrink: 0;
}

.tab-content {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  overflow: hidden;
}

/* 订阅列表样式 */
.subscriptions-list {
  padding: 24px 32px;
  border-right: 1px solid #e2e8f0;
  overflow-y: auto;
  background: #ffffff;
}

.list-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.list-header h4 {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.list-count {
  font-size: 14px;
  color: #64748b;
}

.list-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 10px;
  transition: all 0.2s ease;
}

.list-item:hover {
  background: #f1f5f9;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.item-name {
  font-size: 14px;
  color: #1e293b;
  flex: 1;
  word-break: break-word;
  padding-right: 12px;
}

.item-delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.item-delete:hover {
  background: #fee2e2;
  color: #dc2626;
}

.empty-list {
  text-align: center;
  padding: 48px 20px;
  color: #94a3b8;
}

.empty-list svg {
  color: #cbd5e1;
  margin-bottom: 12px;
}

.empty-list p {
  font-size: 14px;
  margin: 0;
}

/* 添加订阅表单样式 */
.add-subscription-form {
  padding: 24px 32px;
  overflow-y: auto;
  background: #f8fafc;
}

.add-subscription-form h4 {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 24px 0;
}

.form {
  padding: 0;
}

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #475569;
  margin-bottom: 8px;
}

.form-control {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  color: #1e293b;
  font-size: 15px;
  transition: all 0.3s ease;
  background: #ffffff;
  box-sizing: border-box;
}

.form-control:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  outline: none;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 24px;
  font-size: 15px;
  font-weight: 500;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: none;
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

.btn-secondary {
  background: #ffffff;
  color: #475569;
  border: 2px solid #e2e8f0;
}

.btn-secondary:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
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

@media (max-width: 1024px) {
  .tab-content {
    grid-template-columns: 1fr;
  }

  .subscriptions-list {
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
    max-height: 300px;
  }
}

@media (max-width: 768px) {
  .dialog-content {
    max-width: 100%;
    max-height: 100vh;
    border-radius: 0;
    margin: 0;
  }

  .dialog-overlay {
    padding: 0;
  }

  .dialog-header {
    padding: 20px 24px;
  }

  .dialog-header h3 {
    font-size: 20px;
  }

  .tabs {
    padding: 16px 24px;
    overflow-x: auto;
  }

  .tab-button {
    padding: 10px 16px;
    font-size: 14px;
    white-space: nowrap;
  }

  .subscriptions-list,
  .add-subscription-form {
    padding: 20px 24px;
  }
}
</style>

