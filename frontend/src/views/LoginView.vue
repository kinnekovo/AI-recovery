<template>
  <main class="login-page">
    <section class="login-copy">
      <span class="kicker">言语康复支持平台</span>
      <h1>让每天的训练更清楚，让长期记录更连贯。</h1>
      <p>患者可完成日常训练并查看自己的长期能力记录；专业人员可在授权范围内复核证据与管理受控流程。</p>
    </section>
    <form class="auth-panel" @submit.prevent="submit">
      <h2>{{ mode === 'login' ? '登录' : '注册患者账号' }}</h2>
      <label>
        用户名
        <input v-model="username" autocomplete="username" placeholder="请输入用户名" required />
      </label>
      <label>
        密码
        <input v-model="password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" placeholder="至少 6 位" minlength="6" required />
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
import { toUserMessage } from '@/utils/errors'

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
    error.value = toUserMessage(err, '操作失败，请稍后再试')
  } finally {
    loading.value = false
  }
}
</script>
