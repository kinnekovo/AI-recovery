<template>
  <div class="app-shell">
    <aside class="side-nav therapist-nav">
      <div class="brand">
        <span class="brand-mark">疗</span>
        <div>
          <strong>言语康复智能体</strong>
          <p>治疗师端</p>
        </div>
      </div>
      <nav>
        <RouterLink to="/therapist">工作台</RouterLink>
        <RouterLink to="/therapist/patients">患者</RouterLink>
        <RouterLink to="/therapist/assessments">阶段评估</RouterLink>
        <RouterLink to="/therapist/status">系统状态</RouterLink>
      </nav>
      <button class="logout-button" @click="logout">退出登录</button>
    </aside>
    <main class="main-panel">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>
