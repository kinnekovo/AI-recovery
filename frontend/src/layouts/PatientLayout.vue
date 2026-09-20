<template>
  <div class="app-shell">
    <aside v-if="!focusMode" class="side-nav patient-v2-nav">
      <div class="brand">
        <span class="brand-mark">语</span>
        <div>
          <strong>言语康复智能体</strong>
          <p>患者端</p>
        </div>
      </div>
      <nav v-if="productV2Enabled">
        <RouterLink to="/home"><Home :size="20"/>首页</RouterLink>
        <RouterLink to="/training"><Mic2 :size="20"/>训练</RouterLink>
        <RouterLink to="/progress"><TrendingUp :size="20"/>我的进展</RouterLink>
        <RouterLink to="/me"><UserRound :size="20"/>我的</RouterLink>
      </nav>
      <nav v-else>
        <RouterLink to="/home">首页</RouterLink><RouterLink to="/agent/list">我的智能体</RouterLink><RouterLink to="/training">进入训练</RouterLink><RouterLink to="/evaluation">我的进步</RouterLink><RouterLink to="/patient/profile">能力画像</RouterLink><RouterLink to="/report">康复记录</RouterLink>
      </nav>
      <button class="logout-button" @click="logout">退出登录</button>
    </aside>
    <main class="main-panel" :class="{ 'focus-main': focusMode }">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Home, Mic2, TrendingUp, UserRound } from 'lucide-vue-next'
import { productV2Enabled } from '@/api/v2'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const focusMode = computed(() => Boolean(route.meta.focusMode))

function logout() {
  auth.logout()
  router.push('/login')
}
</script>
