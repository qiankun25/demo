import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import Home from '../views/Home.vue'
import Login from '../views/Login.vue'
import DailySubscription from '../views/DailySubscription.vue'
import Updates from '../views/DailySubscription/Updates.vue'
import LiteratureReview from '../views/LiteratureReview.vue'
import LiteratureTranslation from '../views/LiteratureTranslation.vue'
import LiteratureSearch from '../views/LiteratureSearch.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { requiresAuth: true }
  },
  {
    path: '/daily-subscription',
    component: DailySubscription,
    redirect: '/daily-subscription/updates',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'updates',
        name: 'DailyUpdates',
        component: Updates
      }
    ]
  },
  {
    path: '/literature-review',
    name: 'LiteratureReview',
    component: LiteratureReview,
    meta: { requiresAuth: true }
  },
  {
    path: '/literature-translation',
    name: 'LiteratureTranslation',
    component: LiteratureTranslation,
    meta: { requiresAuth: true }
  },
  {
    path: '/literature-search',
    name: 'LiteratureSearch',
    component: LiteratureSearch,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const { checkAuth } = useAuth()
  
  // 检查认证状态
  const authenticated = checkAuth()
  
  // 如果路由需要认证
  if (to.meta.requiresAuth) {
    if (authenticated) {
      next()
    } else {
      // 未登录，重定向到登录页，并保存原始路径以便登录后跳转
      next({
        path: '/login',
        query: { redirect: to.fullPath }
      })
    }
  } else {
    // 如果已登录且访问登录页，重定向到首页或之前保存的路径
    if (to.path === '/login' && authenticated) {
      const redirect = to.query.redirect || '/'
      next(redirect)
    } else {
      next()
    }
  }
})

export default router
