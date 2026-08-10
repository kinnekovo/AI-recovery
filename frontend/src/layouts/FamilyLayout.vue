<template>
  <div class="app-shell">
    <aside class="side-nav family-nav">
      <div class="brand">
        <span class="brand-mark">家</span>
        <div>
          <strong>言语康复智能体</strong>
          <p>家属端</p>
        </div>
      </div>
      <nav>
        <RouterLink to="/family">陪伴概览</RouterLink>
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
