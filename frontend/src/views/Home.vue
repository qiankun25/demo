<template>
  <div class="home">
    <div class="hero">
      <h1 class="hero-title">ResearchGO 学术助手</h1>
      <p class="hero-subtitle">订阅学术日报，生成文献综述，翻译学术文献，检索最新论文，让科研更高效</p>
    </div>

    <div class="features">
      <div class="feature-card" @click="$router.push('/daily-subscription')">
        <div class="feature-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
          </svg>
        </div>
        <h2 class="feature-title">学术日报订阅</h2>
        <p class="feature-desc">订阅您感兴趣领域的学术日报，每日推送最新研究动态和论文摘要，让您始终掌握前沿信息。</p>
        <div class="feature-footer">
          <button class="btn btn-primary">
            开始使用
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
        </div>
      </div>

      <div class="feature-card" @click="$router.push('/literature-review')">
        <div class="feature-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
        </div>
        <h2 class="feature-title">文献综述生成</h2>
        <p class="feature-desc">基于多篇文献自动生成高质量的文献综述，节省您的研究时间，提高学术写作效率。</p>
        <div class="feature-footer">
          <button class="btn btn-primary">
            开始使用
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
        </div>
      </div>

      <div class="feature-card" @click="$router.push('/literature-translation')">
        <div class="feature-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
          </svg>
        </div>
        <h2 class="feature-title">文献翻译</h2>
        <p class="feature-desc">快速准确地翻译学术文献，帮助您轻松阅读和理解国际前沿研究成果。</p>
        <div class="feature-footer">
          <button class="btn btn-primary">
            开始使用
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
        </div>
      </div>

      <div class="feature-card" @click="$router.push('/literature-search')">
        <div class="feature-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <path d="m21 21-4.35-4.35"></path>
          </svg>
        </div>
        <h2 class="feature-title">文献检索</h2>
        <p class="feature-desc">快速检索Minio里的学术论文，帮助您快速找到相关领域的研究成果和前沿文献。</p>
        <div class="feature-footer">
          <button class="btn btn-primary">
            开始使用
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineOptions({
  name: 'Home'
})
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
}

.hero {
  text-align: center;
  padding: 48px 0 64px 0;
  margin-bottom: 14px;
}

.hero-title {
  font-size: 48px;
  font-weight: 800;
  margin-bottom: 16px;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1.2;
}

.hero-subtitle {
  font-size: 20px;
  color: #64748b;
  font-weight: 400;
  max-width: 600px;
  margin: 0 auto;
}

.features {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}

.feature-card {
  background: #ffffff;
  border-radius: 20px;
  padding: 32px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: all 0.3s ease;
  border: 2px solid transparent;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.feature-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #2563eb 0%, #7c3aed 100%);
  transform: scaleX(0);
  transition: transform 0.3s ease;
}

.feature-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  border-color: #e2e8f0;
}

.feature-card:hover::before {
  transform: scaleX(1);
}

.feature-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.1) 0%, rgba(124, 58, 237, 0.1) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  color: #2563eb;
  flex-shrink: 0;
}

.feature-icon svg {
  width: 40px;
  height: 40px;
}

.feature-title {
  font-size: 20px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 10px;
  line-height: 1.3;
}

.feature-desc {
  font-size: 14px;
  color: #64748b;
  line-height: 1.6;
  margin-bottom: 20px;
  flex-grow: 1;
}

.feature-footer {
  margin-top: auto;
}

@media (max-width: 1200px) {
  .features {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .hero {
    padding: 32px 0 48px 0;
  }
  
  .hero-title {
    font-size: 36px;
  }
  
  .hero-subtitle {
    font-size: 18px;
  }
  
  .features {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  
  .feature-card {
    padding: 32px;
  }
}
</style>
