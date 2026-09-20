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
      <nav v-if="productV2Enabled">
        <RouterLink to="/therapist"><Inbox :size="19"/>工作台</RouterLink>
        <RouterLink to="/therapist/patients"><Users :size="19"/>患者</RouterLink>
        <RouterLink to="/therapist/plans"><ClipboardList :size="19"/>训练方案</RouterLink>
      </nav>
      <nav v-else>
        <RouterLink to="/therapist">工作台</RouterLink><RouterLink to="/therapist/patients">患者</RouterLink><RouterLink to="/therapist/assessments">阶段评估</RouterLink><RouterLink to="/therapist/status">系统状态</RouterLink>
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
import { ClipboardList, Inbox, Users } from 'lucide-vue-next'
import { productV2Enabled } from '@/api/v2'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>
