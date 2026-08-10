<template>
  <div class="app-shell">
    <aside class="side-nav">
      <div class="brand">
        <span class="brand-mark">语</span>
        <div>
          <strong>言语康复智能体</strong>
          <p>患者端</p>
        </div>
      </div>
      <nav>
        <RouterLink to="/home">首页</RouterLink>
        <RouterLink to="/agent/list">我的智能体</RouterLink>
        <RouterLink to="/training">进入训练</RouterLink>
        <RouterLink to="/evaluation">我的进步</RouterLink>
        <RouterLink to="/report">康复记录</RouterLink>
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
