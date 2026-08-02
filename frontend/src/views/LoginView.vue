<template>
  <main class="login-page">
    <section class="login-copy">
      <span class="kicker">MVP 第一阶段</span>
      <h1>用熟悉的声音，陪患者完成每天的言语训练。</h1>
      <p>先跑通注册、智能体创建、录音、Mock评分和记录保存闭环。</p>
    </section>
    <form class="auth-panel" @submit.prevent="submit">
      <h2>{{ mode === 'login' ? '登录' : '注册患者账号' }}</h2>
      <label>
        用户名
        <input v-model="username" autocomplete="username" placeholder="patient_demo" />
      </label>
      <label>
        密码
        <input v-model="password" type="password" autocomplete="current-password" placeholder="至少 6 位" />
      </label>
      <p v-if="error" class="error-text">{{ error }}</p>
      <AppButton variant="primary" :loading="loading">{{ mode === 'login' ? '登录' : '注册并登录' }}</AppButton>
      <button class="text-button" type="button" @click="toggleMode">
        {{ mode === 'login' ? '没有账号？注册' : '已有账号？登录' }}
      </button>
    </form>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    if (mode.value === 'login') await auth.login(username.value, password.value)
    else await auth.register(username.value, password.value)
    router.push('/home')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '操作失败，请稍后再试'
  } finally {
    loading.value = false
  }
}
</script>
