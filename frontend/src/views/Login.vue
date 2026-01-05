<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <div class="logo">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <h1 class="login-title">ResearchGO</h1>
        </div>
        <p class="login-subtitle">欢迎回来，请登录您的账户</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>

        <div class="form-group">
          <label class="form-label" for="email">邮箱地址</label>
          <input
            id="email"
            v-model="email"
            type="email"
            class="form-control"
            placeholder="请输入您的邮箱"
            required
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="password">密码</label>
          <div class="password-input-wrapper">
            <input
              id="password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              class="form-control"
              placeholder="请输入您的密码"
              required
              :disabled="loading"
            />
            <button
              type="button"
              class="password-toggle"
              @click="showPassword = !showPassword"
              :disabled="loading"
            >
              <svg v-if="showPassword" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
              <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                <line x1="1" y1="1" x2="23" y2="23"></line>
              </svg>
            </button>
          </div>
        </div>

        <div class="form-options">
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model="rememberMe"
              :disabled="loading"
            />
            <span>记住我</span>
          </label>
          <a href="#" class="forgot-password" @click.prevent>忘记密码？</a>
        </div>

        <button
          type="submit"
          class="btn btn-primary login-btn"
          :disabled="loading"
        >
          <span v-if="loading" class="loading-spinner"></span>
          <span v-else>登录</span>
        </button>
      </form>

      <div class="login-footer">
        <p>还没有账户？ <a href="#" @click.prevent="showRegister = true">立即注册</a></p>
      </div>
    </div>

    <!-- 注册对话框（简化版） -->
    <div v-if="showRegister" class="register-overlay" @click.self="showRegister = false">
      <div class="register-card" @click.stop>
        <div class="register-header">
          <h2>创建账户</h2>
          <button class="close-btn" @click="showRegister = false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <form @submit.prevent="handleRegister" class="register-form">
          <div v-if="registerError" class="error-message">
            {{ registerError }}
          </div>
          <div class="form-group">
            <label class="form-label" for="reg-email">邮箱地址</label>
            <input
              id="reg-email"
              v-model="registerEmail"
              type="email"
              class="form-control"
              placeholder="请输入您的邮箱"
              required
              :disabled="registerLoading"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="reg-password">密码</label>
            <input
              id="reg-password"
              v-model="registerPassword"
              type="password"
              class="form-control"
              placeholder="请输入密码（至少6位）"
              required
              minlength="6"
              :disabled="registerLoading"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="reg-username">用户名</label>
            <input
              id="reg-username"
              v-model="registerUsername"
              type="text"
              class="form-control"
              placeholder="请输入用户名（3-50个字符）"
              required
              minlength="3"
              maxlength="50"
              :disabled="registerLoading"
            />
          </div>
          <button
            type="submit"
            class="btn btn-primary"
            :disabled="registerLoading"
          >
            <span v-if="registerLoading" class="loading-spinner"></span>
            <span v-else>注册</span>
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const route = useRoute()
const { login, register } = useAuth()

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const rememberMe = ref(false)
const loading = ref(false)
const errorMessage = ref('')

const showRegister = ref(false)
const registerEmail = ref('')
const registerPassword = ref('')
const registerUsername = ref('')
const registerLoading = ref(false)
const registerError = ref('')

const handleLogin = async () => {
  errorMessage.value = ''
  loading.value = true

  try {
    await login(email.value, password.value, rememberMe.value)
    // 登录成功后重定向到之前保存的路径或首页
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (error) {
    errorMessage.value = error.message || '登录失败，请检查您的邮箱和密码'
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  registerError.value = ''
  registerLoading.value = true

  try {
    await register(registerEmail.value, registerPassword.value, registerUsername.value)
    // 注册成功后自动登录
    await login(registerEmail.value, registerPassword.value, false)
    showRegister.value = false
    // 注册成功后重定向到之前保存的路径或首页
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (error) {
    registerError.value = error.message || '注册失败，请稍后重试'
  } finally {
    registerLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  background-attachment: fixed;
}

.login-card {
  width: 100%;
  max-width: 440px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 24px;
  padding: 48px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 16px;
  color: #2563eb;
}

.login-title {
  font-size: 32px;
  font-weight: 700;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.login-subtitle {
  font-size: 16px;
  color: #64748b;
  font-weight: 400;
}

.login-form {
  margin-bottom: 24px;
}

.error-message {
  background: #fef2f2;
  color: #991b1b;
  padding: 12px 16px;
  border-radius: 10px;
  margin-bottom: 24px;
  border-left: 4px solid #dc2626;
  font-size: 14px;
}

.password-input-wrapper {
  position: relative;
}

.password-toggle {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.3s ease;
}

.password-toggle:hover:not(:disabled) {
  color: #2563eb;
}

.password-toggle:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #475569;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #2563eb;
}

.forgot-password {
  font-size: 14px;
  color: #2563eb;
  text-decoration: none;
  transition: color 0.3s ease;
}

.forgot-password:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.login-btn {
  width: 100%;
  padding: 14px;
  font-size: 16px;
  font-weight: 600;
}

.loading-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.login-footer {
  text-align: center;
  padding-top: 24px;
  border-top: 1px solid #e2e8f0;
}

.login-footer p {
  font-size: 14px;
  color: #64748b;
}

.login-footer a {
  color: #2563eb;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.3s ease;
}

.login-footer a:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

/* 注册对话框 */
.register-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.register-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 24px;
  padding: 32px;
  width: 100%;
  max-width: 440px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.register-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.register-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: #0f172a;
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.05);
  color: #64748b;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.close-btn:hover {
  background: rgba(0, 0, 0, 0.1);
}

.register-form {
  margin-top: 24px;
}

@media (max-width: 768px) {
  .login-card {
    padding: 32px 24px;
  }

  .login-title {
    font-size: 28px;
  }

  .register-card {
    padding: 24px;
  }
}
</style>

